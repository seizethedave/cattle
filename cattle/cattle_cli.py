import argparse
import getpass
import importlib
import os
import sys
import time

from cattle import cattle

parser = argparse.ArgumentParser(
    prog="cattle",
    description="cattle: the server configurer.",
)
subparsers = parser.add_subparsers()
parser_exec = subparsers.add_parser("exec")
parser_exec.add_argument("config_dir")
parser_exec.add_argument("-m", "--config-module", default="cattle",
                        help="name of the config module. defaults to cattle.")
parser_exec.add_argument("-ho", "--host", dest="hosts", action="append")
parser_exec.add_argument("-l", "--local", action="store_true")
parser_exec.add_argument("-u", "--username", action="store")
parser_exec.add_argument("-d", "--dry-run",
                        help="if set, prints the hypothetical rather than running anything",
                        action="store_true")

def main() -> int:
    args = parser.parse_args()

    config_dir_with_module = os.path.join(args.config_dir, args.config_module)
    mod = config_dir_with_module.replace("/", ".")
    if mod.endswith(".py"):
        mod = mod[:-3]

    try:
        config_module = importlib.import_module(mod)
    except ModuleNotFoundError as e:
        print(f"couldn't load config: {e}", file=sys.stderr)
        return 1

    if args.local:
        cattle.run_config(config_module, args.dry_run)
        return 0

    if not args.hosts:
        print("require at least one host when run in remote mode.", file=sys.stderr)
        return 1
    if not args.username:
        print("username required in remote mode.", file=sys.stderr)
        return 1

    # Otherwise, we're in remote mode.
    execution_id = "cattle_exec_{}".format(time.monotonic())
    print(execution_id)

    archive = cattle.make_archive(execution_id, args.config_dir)
    print(archive)
    runners = []

    password = getpass.getpass("Please enter the password for these hosts: ")

    for h in args.hosts:
        runner = cattle.HostRunner(execution_id, archive, h, args.username, password)
        runner.transfer()
        runners.append(runner)

    return 0
