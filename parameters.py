# -*- coding: utf-8 -*-
import argparse


def get_args():
    # feed them to the parser.
    parser = argparse.ArgumentParser(description="PyTorch training.")

    # add arguments.
    parser.add_argument("--work_dir", default=None, type=str)
    parser.add_argument("--remote_exec", default=False, type=str2bool)

    # general.
    parser.add_argument("--root_path", type=str, default="./")
    parser.add_argument("--data_dir", default="/mlodata1/tlin/dataset")

    # parse conf.
    conf = parser.parse_args()
    return conf


def str2bool(v):
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise ValueError("Boolean value expected.")


if __name__ == "__main__":
    args = get_args()
