import argparse
import getpass
import importlib
import os
import sys
import tarfile
import tempfile
import time
import zipapp

import paramiko
import scp

from cattle import cattle
from cattle.runtime import cattle_remote

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
parser_exec.add_argument("-p", "--port", default=22)
parser_exec.add_argument("-l", "--local", action="store_true")
parser_exec.add_argument("-u", "--username", action="store")
parser_exec.add_argument("-d", "--dry-run",
                        help="if set, prints the hypothetical rather than running anything",
                        action="store_true")


def make_archive(execution_id, cfg_dir):
    def add_filter(item: tarfile.TarInfo):
        return item if "__pycache__" not in item.name else None
    with tempfile.NamedTemporaryFile(prefix="cattle_cfg_", delete=False) as t:
        with tarfile.open(mode="w:gz", fileobj=t) as tar:
            tar.add(cfg_dir, arcname="config", recursive=True, filter=add_filter)
            return t.name

def make_executable():
    exclude = {
        "cattle.py",
        "cattle_cli.py",
    }
    def exec_filter(path):
        return path not in exclude

    with tempfile.NamedTemporaryFile(prefix="cattle_runtime_", delete=False) as t:
        zipapp.create_archive(
            os.path.dirname(__file__),
            target=t,
            main="cattle.runtime.cattle_remote:main",
            filter=exec_filter,
        )
        return t.name

class HostRunner:
    def __init__(self, execution_id, archive, host, port, username, password):
        self.execution_id = execution_id
        self.archive = archive
        self.host = host
        self.port = port
        self.username = username
        self.password = password

    def transfer(self):
        dest_dir = f"/var/run/cattle/{self.execution_id}"
        with paramiko.SSHClient() as ssh_client:
            ssh_client.load_system_host_keys()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client.connect(self.host, self.port, self.username, self.password)
            ssh_client.exec_command(f"mkdir -p {dest_dir}")
            with scp.SCPClient(ssh_client.get_transport()) as scp_client:
                scp_client.put(self.archive, dest_dir)

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
        if args.dry_run:
            cattle_remote.dry_run_config(config_module)
        else:
            cattle_remote.run_config(config_module)
        return 0

    if not args.hosts:
        print("require at least one host when run in remote mode.", file=sys.stderr)
        return 1
    if not args.username:
        print("username required in remote mode.", file=sys.stderr)
        return 1

    # Otherwise, we're in remote mode.

    execution_id = "cattle_exec_{}".format(time.monotonic())
    archive = make_archive(execution_id, args.config_dir)
    password = getpass.getpass("Please enter the password for these hosts: ")
    executable = make_executable()
    print(executable)

    runners = []

    for h in args.hosts:
        runner = HostRunner(execution_id, archive, h, args.port, args.username, password)
        runner.transfer()
        runners.append(runner)

    return 0
