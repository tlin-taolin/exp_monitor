# -*- coding: utf-8 -*-
import sys
import random
import six
import time
import importlib
import itertools
import functools

import tmux_cluster.tmux as tx


def import_string(dotted_path):
    """
    Import a dotted module path and return the attribute/class designated by the
    last name in the path. Raise ImportError if the import failed.
    """
    try:
        module_path, class_name = dotted_path.rsplit(".", 1)
    except ValueError:
        msg = "%s doesn't look like a module path" % dotted_path
        six.reraise(ImportError, ImportError(msg), sys.exc_info()[2])

    module = importlib.import_module(module_path)

    try:
        return getattr(module, class_name)
    except AttributeError:
        msg = 'Module "%s" does not define a "%s" attribute/class' % (
            module_path,
            class_name,
        )
        six.reraise(ImportError, ImportError(msg), sys.exc_info()[2])


def read_replacements_from_python_class(python_file_path, script_class_name):
    # replace python_file_path.
    python_file_path = python_file_path.replace(".py", "").replace("/", ".") + (
        ".NewConf" if script_class_name is None else script_class_name
    )
    new_conf_object = import_string(python_file_path)

    if hasattr(new_conf_object, "to_be_replaced"):
        return new_conf_object.to_be_replaced
    else:
        return None


def build_script(conf, idx, replacement=None, job_id="/tmp/tmp"):
    # get prefix_cmd.
    conf.n_mpi_process = (
        conf.n_mpi_process
        if "n_mpi_process" not in replacement
        else replacement["n_mpi_process"]
    )
    conf.hostfile = (
        conf.hostfile if "hostfile" not in replacement else replacement["hostfile"]
    )
    conf.timestamp = str(int(time.time()) + random.randint(0, 1000) + idx)
    if conf.n_mpi_process > 1:
        prefix_cmd = f"mpirun -n {conf.n_mpi_process} --hostfile {conf.hostfile} --mca orte_base_help_aggregate 0 --mca btl_tcp_if_exclude docker0,lo --mca btl_smcuda_use_cuda_ipc {1 if conf.use_ipc else 0} --prefix {conf.mpi_path} "
        prefix_cmd += (
            f" -x {conf.mpi_env}"
            if conf.mpi_env is not None and len(conf.mpi_env) > 0
            else ""
        )
    else:
        prefix_cmd = ""

    # build complete script.
    cmd = f"OMP_NUM_THREADS={conf.num_cpus} MKL_NUM_THREADS={conf.num_cpus} {prefix_cmd} {conf.python_path} main.py "

    # update the job_id.
    conf.job_id = job_id
    # perform replacement.
    for k, v in conf.__dict__.items():
        if replacement is not None and k in replacement:
            cmd += " --{} {} ".format(k, replacement[k])
        elif v is not None:
            cmd += " --{} {} ".format(k, v)
    return cmd


def create_scripts(conf):
    # get the replacement list for each job.
    replacements = read_replacements_from_python_class(
        conf.script_path, conf.script_class_name
    )
    replacement_keys, replacement_values = (
        list(replacements.keys()),
        list(replacements.values()),
    )

    # build replacement combinations.
    if "coupled" not in replacement_keys:
        new_replacements = [
            dict(zip(replacement_keys, v))
            for v in itertools.product(*replacement_values)
        ]
    else:
        # check the job files.
        coupled_keys = replacements["coupled"] + ["coupled"]
        coupled_key_values = [
            (couple, replacements[couple]) for couple in replacements["coupled"]
        ]
        coupled_value_length = [len(values) for key, values in coupled_key_values]
        assert coupled_value_length.count(coupled_value_length[0]) == len(
            coupled_key_values
        )

        # for coupled keys, we ensure they are the same,
        # otherwise we use itertools.product over its values.
        excluded_replacement_keys = [
            key for key, value in replacements.items() if key not in coupled_keys
        ]
        excluded_replacement_values = [
            value for key, value in replacements.items() if key not in coupled_keys
        ]
        excluded_replacements = [
            dict(zip(excluded_replacement_keys, v))
            for v in itertools.product(*excluded_replacement_values)
        ]
        new_replacements = functools.reduce(
            lambda a, b: a + b,
            [
                [
                    list(excluded_replacement.items())
                    + [
                        (key, values[idx])
                        for key, values in coupled_key_values
                        if key != "coupled"
                    ]
                    for excluded_replacement in excluded_replacements
                ]
                for idx in range(coupled_value_length[0])
            ],
        )
        new_replacements = [dict(replacement) for replacement in new_replacements]

    # create job scripts.
    scripts = []
    job_id = f"/tmp/jobrun_logs_{str(int(time.time()))}"
    for idx, new_replacement in enumerate(new_replacements):
        print(f"{idx+1}-th replacement conf: {new_replacement}.")
        scripts.append(build_script(conf, idx, new_replacement, job_id))
    return scripts


def create_jobs_on_node(conf, scripts):
    def _query_job_status(log_path):
        try:
            with open(log_path, "rb") as f:
                lines = f.readlines()
            return list(set([line for line in lines if len(line) > 0]))
        except FileNotFoundError:
            return []

    print(f"\n\nRun jobs on the host with job_id={conf.job_id}.")
    is_complete = False
    num_finished_task = 0
    task_count = 0
    current_degree_parallelism = 0
    expected_degree_parallelism = conf.num_jobs_per_node

    while not is_complete:
        if current_degree_parallelism > 0:
            time.sleep(conf.wait_in_seconds_per_job)

        # run one new experiment, and update the counter.
        if (
            current_degree_parallelism < expected_degree_parallelism
            and task_count < len(scripts)
        ):
            new_task_script = scripts[task_count]
            print(
                f"\n\nlaunch new task@{task_count + 1} / {len(scripts)}: {new_task_script}."
            )
            tx.Run(name=f"{conf.job_name}", job_node="localhost").make_job(
                job_name=f"job-{task_count}", task_scripts=[new_task_script]
            )
            current_degree_parallelism += 1
            task_count += 1

        # update the counter.
        cur_num_finished_task = len(_query_job_status(conf.job_id))
        if cur_num_finished_task != num_finished_task:
            current_degree_parallelism -= cur_num_finished_task - num_finished_task
            num_finished_task = cur_num_finished_task

        if num_finished_task == len(scripts):
            is_complete = True

    # exit.
    sys.exit(0)


if __name__ == "__main__":
    from parameters import get_args

    conf = get_args()

    """workflow:
    1. we read the experiment setup from one py file,
    2. we create the exact experiment script
        (based on the default hyper-parameters as well as the new hyper-parameters).
    3. launch the experiments by feeding predefined num_jobs_per_node to the experiment queue.
    """
    scripts = create_scripts(conf)
    create_jobs_on_node(conf, scripts)
