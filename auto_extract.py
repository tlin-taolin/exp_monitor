# -*- coding: utf-8 -*-
import os
import argparse

import tools.file_io as file_io
from tools.show_results import load_raw_info_from_experiments
from parameters import str2bool

"""parse and define arguments for different tasks."""


def get_args():
    # feed them to the parser.
    parser = argparse.ArgumentParser(description="Extract results.")

    # add arguments.
    parser.add_argument("--in_dir", type=str)
    parser.add_argument("--out_name", type=str, default="summary.pickle")
    parser.add_argument("--folder_name", type=str, default=None)
    parser.add_argument("--parse_all", type=str2bool, default=False)

    # parse aˇˇrgs.
    args = parser.parse_args()

    # an argument safety check.
    check_args(args)
    return args


def check_args(args):
    assert args.in_dir is not None

    # define out path.
    args.out_path = os.path.join(args.in_dir, args.out_name)


"""write the results to path."""


def main(args):
    # save the parsed results to path.
    file_io.write_pickle(
        load_raw_info_from_experiments(
            args.in_dir, folder_name=args.folder_name, parse_all=args.parse_all
        ),
        args.out_path,
    )


if __name__ == "__main__":
    args = get_args()

    main(args)
