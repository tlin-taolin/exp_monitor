# -*- coding: utf-8 -*-
import re
import os
import time
from typing import Dict, List

import tools.file_io as file_io
import parameters as para
import tmux_cluster.tmux as tx


def read_hostfile(file_path) -> Dict[str, str]:
    def _parse(line):
        matched_line = re.findall(r"^(.*?) slots=(.*?)$", line, re.DOTALL)
        matched_line = [x.strip() for x in matched_line[0]]
        return matched_line

    # read file
    lines = file_io.read_txt(file_path)

    # use regex to parse the file.
    ip2slots = dict(_parse(line) for line in lines)
    return ip2slots


def map_slot(ip2slots) -> List[str]:
    ip_slot = []
    for ip, slots in ip2slots.items():
        for _ in range(int(slots)):
            ip_slot += [ip]
    return ip_slot


def run_cmd(cmd) -> None:
    # run the cmd.
    print("\nRun the following cmd:\n" + cmd)
    os.system(cmd)


def build_mpi_script(conf, replacement: Dict[str, str] = None):
    # get prefix_cmd.
    conf.timestamp = str(int(time.time()))

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
    cmd = " {} main.py ".format(conf.python_path)
    for k, v in conf.__dict__.items():
        if replacement is not None and k in replacement:
            cmd += " --{} {} ".format(k, replacement[k])
        elif v is not None:
            cmd += " --{} {} ".format(k, v)
    return prefix_cmd + cmd


def create_job_on_nodes(conf, tasks: Dict[str, str]) -> None:
    # rebuild tasks for each script.
    node_tasks = []
    for ip, _tasks in tasks.items():
        _tasks = "  &  ".join(_tasks)
        node_tasks += [(ip, _tasks)]

    if (not conf.remote_exec) or "localhost" in tasks:
        run_cmd(node_tasks[0][1])
    else:
        print("\nrun the job on the remote host.\n")

        for ip, _tasks in node_tasks:
            tx.Run(name=f"{conf.experiment}", job_node=ip).make_job(
                job_name="job", task_scripts=[_tasks]
            )


def main_mpi(conf, ip2slot: Dict) -> None:
    # build scripts for distributed world
    tasks = dict()
    if conf.clean_python:
        cmd = "pkill -9 python"
    else:
        # build runnable script for a single machine.
        cmd = build_mpi_script(conf)

    tasks[ip2slot[0]] = [
        (
            "cd {work_dir} && ".format(work_dir=conf.work_dir)
            if conf.work_dir is not None
            else ""
        )
        + cmd
    ]

    # run cmd.
    create_job_on_nodes(conf, tasks)


if __name__ == "__main__":
    # parse the arguments.
    conf = para.get_args()

    # get ip and the corresponding # of slots.
    ip2slots = read_hostfile(conf.hostfile)
    ip2slot = map_slot(ip2slots)

    # run the main script.
    main_mpi(conf, ip2slot)
