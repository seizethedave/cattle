"""
Command line and tools for running Cattle configs.
"""

import argparse
import importlib
import pathlib
import os
import sys
import tarfile
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
    subparsers = parser.add_subparsers(required=True)
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

def exec_config(args):
    config_dir = args.config_dir.rstrip("/")
    config_abs = os.path.abspath(config_dir)

    # Make the config/__cattle__.py importable:
    sys.path.append(os.path.dirname(config_abs))
    pathlib.Path(os.path.join(config_abs, "__init__.py")).touch()

    config_pkg = os.path.basename(config_dir)
    mod = f"{config_pkg}.{args.config_module}"
    if mod.endswith(".py"):
        mod = mod[:-3]

    # The last bit is kind of an unfortunate snag from using zipapp: We want
    # customer configs to refer to facilities via "import cattle.facility.foo"
    # but we no longer have a top-level cattle package due to us zipapping the
    # cattle folder contents. So we're going to kind of rewrite imports for
    # facility.* to cattle.facility.*.

    import facility
    assert "facility" in sys.modules
    sys.modules["cattle.facility"] = sys.modules["facility"]

    try:
        config_module = importlib.import_module(mod)
    except ModuleNotFoundError as e:
        print(f"couldn't load config: {e}", file=sys.stderr)
        return 1

    if args.dry_run:
        dry_run_config(config_module)
    else:
        run_config(config_module)

    return 0

if __name__ == "__main__":
    sys.exit(main())
