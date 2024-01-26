"""
Command line and tools for running Cattle configs.
"""

import argparse
import importlib
import logging
import os
import pathlib
import sys
import tarfile
from typing import Callable, NoReturn

RETRIES = 3

STATUS_PROGRESS = "PROGRESS"
STATUS_ERROR = "ERROR"
STATUS_DONE = "DONE"

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
    logging.info("running in dry run mode")

    try:
        steps = cfg.steps
    except AttributeError:
        logging.exception("The config file doesn't define a steps attribute.")
        raise

    for step in steps:
        logging.info(f"> {step.__class__.__name__}:")
        for c in step.dry_run():
            logging.info(f"   > {c}")

def run_config(cfg):
    logging.info("running in real mode")

    try:
        steps = cfg.steps
    except AttributeError:
        logging.exception("The config file doesn't define a steps attribute.")
        raise

    for i, step in enumerate(steps, start=1):
        try:
            logging.info(f"Running step {i} ({step.__class__.__name__})")
            call_with_retry(step.run)
        except Exception as e:
            logging.exception(f"aborting config at step {i} ({step.__class__.__name__})")
            raise
        else:
            logging.info(f"Step {i} completed successfully.")
    else:
        logging.info("config executed successfully.")

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="cattle-run",
        description="runner program for __cattle: the server configurer__.",
    )
    subparsers = parser.add_subparsers()
    parser_init = subparsers.add_parser(
        "init",
        help="initializes a remote Cattle runtime environment given a tar file",
    )
    parser_init.set_defaults(func=init)
    parser_init.add_argument("tar_file")
    parser_init.add_argument("-m", "--config-module", default="__cattle__",
                            help="name of the config module. defaults to __cattle__.")
    parser_init.add_argument("-d", "--dry-run",
                            help="if set, prints the hypothetical rather than running anything",
                            action="store_true")

    parser_exec = subparsers.add_parser("exec")
    parser_exec.set_defaults(func=exec_config)
    parser_exec.add_argument("config_dir")
    parser_exec.add_argument("-m", "--config-module", default="__cattle__",
                            help="name of the config module. defaults to __cattle__.")
    parser_exec.add_argument("-p", "--with-path")
    parser_exec.add_argument("-v", "--verbose", action="store_true")
    parser_exec.add_argument("-d", "--dry-run",
                            help="if set, prints the hypothetical rather than running anything",
                            action="store_true")

    args = parser.parse_args()
    return args.func(args)

def init(args):
    """
    The remote init routine.
    This takes a tar file and initializes the runtime directory structure.
    """
    with tarfile.open(args.tar_file) as t:
        t.extractall()
    return 0

def rewrite_status(status_file: str, status: str):
    with open(status_file, 'w') as f:
        f.write(status)

def exec_config(args):
    config_dir = args.config_dir.rstrip("/")
    config_abs = os.path.abspath(config_dir)
    exec_dir = os.path.dirname(config_abs)

    # Make config/__cattle__.py importable:
    sys.path.append(os.path.dirname(config_abs))
    try:
        pathlib.Path(os.path.join(config_abs, "__init__.py")).touch()
    except FileNotFoundError:
        pass

    config_pkg = os.path.basename(config_dir)
    mod = f"{config_pkg}.{args.config_module}"
    if mod.endswith(".py"):
        mod = mod[:-3]

    # The last bit is kind of an unfortunate snag from using zipapp: We want
    # customer configs to refer to facilities via "import cattle.facility.foo"
    # but we no longer have a top-level cattle package due to us zipapping the
    # cattle folder contents. So we're going to kind of rewrite imports for
    # cattle.facility.* to facility.*.

    import facility
    assert "facility" in sys.modules
    sys.modules["cattle.facility"] = sys.modules["facility"]

    try:
        config_module = importlib.import_module(mod)
    except ModuleNotFoundError as e:
        print(f"couldn't load config: {e}", file=sys.stderr)
        return 1

    log_file = os.path.join(exec_dir, "exec.log")
    status_file = os.path.join(exec_dir, "STATUS")

    logging.basicConfig(filename=log_file, level=logging.INFO)

    rewrite_status(status_file, STATUS_PROGRESS)

    try:
        if args.dry_run:
            dry_run_config(config_module)
        else:
            run_config(config_module)
    except:
        # An unrecoverable error after performing retries.
        rewrite_status(status_file, STATUS_ERROR)
    else:
        rewrite_status(status_file, STATUS_DONE)

    return 0

if __name__ == "__main__":
    sys.exit(main())
