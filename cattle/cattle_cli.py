import argparse

parser = argparse.ArgumentParser(
    prog="cattle",
    description="cattle: the server configurer.",
)
subparsers = parser.add_subparsers()

parser_exec = subparsers.add_parser("exec")
parser_exec.add_argument("config_filename")
parser_exec.add_argument("servers")
parser_exec.add_argument("-u", "--username", action="store")
parser_exec.add_argument("-d", "--dry-run",
                        help="if set, prints the hypothetical rather than running anything",
                        action="store_true")

def main() -> int:
    args = parser.parse_args()
    return 0
