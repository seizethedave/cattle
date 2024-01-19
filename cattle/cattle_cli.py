import argparse
import importlib
import sys

from cattle import cattle

parser = argparse.ArgumentParser(
    prog="cattle",
    description="cattle: the server configurer.",
)
subparsers = parser.add_subparsers()
parser_exec = subparsers.add_parser("exec")
parser_exec.add_argument("config_filename")
parser_exec.add_argument("-hf", "--hostsfile")
parser_exec.add_argument("-l", "--local", action="store_true")
parser_exec.add_argument("-u", "--username", action="store")
parser_exec.add_argument("-d", "--dry-run",
                        help="if set, prints the hypothetical rather than running anything",
                        action="store_true")

def main() -> int:
    args = parser.parse_args()
    print(args)

    mod = args.config_filename.replace("/", ".")
    if mod.endswith(".py"):
        mod = mod[:-3]

    try:
        config_module = importlib.import_module(mod)
    except ModuleNotFoundError as e:
        print(f"couldn't load config_filename: {e}", file=sys.stderr)
        return 1

    if args.local:
        cattle.run_config(config_module, args.dry_run)
    else:
        assert(False)

    return 0
