"""
Command line and tools for running Cattle configs.
"""

import argparse
import sys
from typing import Callable, NoReturn

RETRIES = 3

def call_with_retry(c: Callable[[], NoReturn]):
    e = None
    for _ in range(RETRIES):
        try:
            return c()
        except Exception as err:
            e = err
    else:
        raise Exception(f"unable to execute after {RETRIES} attempts. last err: {e}")

def dry_run_config(cfg):
    steps = getattr(cfg, 'steps', None)

    if steps is None:
        raise Exception("The config file doesn't define a steps attribute.")

    for step in steps:
        print(f"> {step.__class__.__name__}:")
        for c in step.dry_run():
            print(f"   > {c}")

def run_config(cfg):
    steps = getattr(cfg, 'steps', None)

    if steps is None:
        raise Exception("The config file doesn't define a steps attribute.")

    for i, step in enumerate(steps, start=1):
        try:
            call_with_retry(step.run)
        except Exception as e:
            raise Exception(f"aborting config at step {i} ({step.__class__.__name__}): {e}")

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="cattle-run",
        description="runner program for __cattle: the server configurer__.",
    )
    subparsers = parser.add_subparsers()
    parser_exec = subparsers.add_parser(
        "init",
        help="initializes a remote Cattle runtime environment given a tar file",
    )
    parser_exec.add_argument("tar_file")
    parser_exec.add_argument("-m", "--config-module", default="cattle",
                            help="name of the config module. defaults to cattle.")
    parser_exec.add_argument("-d", "--dry-run",
                            help="if set, prints the hypothetical rather than running anything",
                            action="store_true")

    args = parser.parse_args()

if __name__ == "__main__":
    sys.exit(main())
