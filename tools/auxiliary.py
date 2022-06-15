# -*- coding: utf-8 -*-
import os
import json
import contextlib
from datetime import datetime
from typing import Any

import torch

from parameters import str2bool
import tools.file_io as file_io


def is_float(value):
    try:
        float(value)
        return True
    except:
        return False


def dict_parser(values):
    local_dict = {}
    if values is None:
        return local_dict
    for kv in values.split(",,"):
        k, v = kv.split("=")
        try:
            local_dict[k] = float(v)
        except ValueError:
            try:
                local_dict[k] = str2bool(v)
            except ValueError:
                local_dict[k] = v
    return local_dict


def str2time(string, pattern):
    """convert the string to the datetime."""
    return datetime.strptime(string, pattern)


class dict2obj(object):
    def __init__(self, d):
        for a, b in d.items():
            if isinstance(b, (list, tuple)):
                setattr(self, a, [dict2obj(x) if isinstance(x, dict) else x for x in b])
            else:
                setattr(self, a, dict2obj(b) if isinstance(b, dict) else b)


@contextlib.contextmanager
def fork_rng_with_seed(seed):
    if seed is None:
        yield
    else:
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed)
            yield


@contextlib.contextmanager
def training_monitor(conf):
    conf.status = "started"
    save_arguments(conf)

    yield

    # update the training status.
    if conf.status == "started":
        conf.status = "finished"
    os.system(f"echo {conf.checkpoint_path} >> {conf.job_id}")
    save_arguments(conf)


def save_arguments(conf: Any, force: bool = True):
    # save the configure file to the checkpoint.
    if force:
        with open(os.path.join(conf.checkpoint_path, "arguments.json"), "w") as fp:
            json.dump(
                dict(
                    [
                        (k, v)
                        for k, v in conf.__dict__.items()
                        if file_io.is_jsonable(v) and type(v) is not torch.Tensor
                    ]
                ),
                fp,
                indent=" ",
            )
