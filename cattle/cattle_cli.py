import argparse
import getpass
import importlib
import os
import pathlib
import sys
import tarfile
import tempfile
import time
import zipapp

import paramiko
import scp

from . import cattle_remote

def make_archive(cfg_dir):
    def add_filter(item: tarfile.TarInfo):
        return item if "__pycache__" not in item.name else None
    with tempfile.NamedTemporaryFile(prefix="cattle_cfg_", delete=False) as t:
        with tarfile.open(mode="w:gz", fileobj=t) as tar:
            tar.add(cfg_dir, arcname="config", recursive=True, filter=add_filter)
            return t.name

def make_executable():
    this_file = pathlib.Path(__file__)
    with tempfile.NamedTemporaryFile(prefix="cattle_runtime_", delete=False) as t:
        zipapp.create_archive(
            this_file.absolute().parent,
            target=t,
            main="cattle_remote:main",
            # Leave out this script.
            filter=lambda p: p != this_file.name,
        )
        return t.name

class HostRunner:
    def __init__(self, execution_id, host, port, username, password):
        self.execution_id = execution_id
        self.exec_dir = f"/var/run/cattle/{self.execution_id}"
        self.host = host
        self.port = port
        self.username = username
        self.password = password

    def connect(self):
        c = paramiko.SSHClient()
        c.load_system_host_keys()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(self.host, self.port, self.username, self.password)
        self.ssh_client = c

    def transfer(self, archive, executable):
        self.ssh_client.exec_command(f"mkdir -p {self.exec_dir}")
        with scp.SCPClient(self.ssh_client.get_transport()) as scp_client:
            scp_client.put(archive, self.exec_dir)
            scp_client.put(executable, self.exec_dir)

    def execute(self, archive, executable):
        archive_filename = os.path.basename(archive)
        executable_filename = os.path.basename(executable)
        config_filename = os.path.join(self.exec_dir, "config")
        _, cmd_out, cmd_err = self.ssh_client.exec_command(
            f"cd {self.exec_dir} && "
            f"python3 {executable_filename} init {archive_filename} && "
            f"python3 {executable_filename} exec {config_filename}"
        )
        exit_code = cmd_out.channel.recv_exit_status()
        if exit_code != 0:
            raise Exception(
                f"Execute failed with code {exit_code}: "
                f"stdout={cmd_out.read().decode()} stderr={cmd_err.read().decode()}"
            )

    def status(self):
        exec_status = os.path.join(self.exec_dir, "STATUS")
        _, cat_out, _ = self.ssh_client.exec_command(
            f"cat {exec_status} || echo 'UNKNOWN'"
        )
        return cat_out.read().decode()

    def clean(self):
        _, cmd_out, cmd_err = self.ssh_client.exec_command(f"rm -rf {self.exec_dir}")
        exit_code = cmd_out.channel.recv_exit_status()
        if exit_code != 0:
            raise Exception(
                f"Clean failed with code {exit_code}: "
                f"stdout={cmd_out.read().decode()} stderr={cmd_err.read().decode()}"
            )

def main() -> int:
    hostinfo_parser = argparse.ArgumentParser(add_help=False)
    hostinfo_parser.add_argument("-ho", "--host", dest="hosts", action="append")
    hostinfo_parser.add_argument("-p", "--port", type=int, default=22)
    hostinfo_parser.add_argument("-u", "--username", action="store")

    parser = argparse.ArgumentParser(
        prog="cattle",
        description="cattle: the server configurer.",
    )
    subparsers = parser.add_subparsers()
    parser_exec = subparsers.add_parser(
        "exec",
        help="Execute a Cattle config against remote hosts.",
        parents=[hostinfo_parser],
    )
    parser_exec.set_defaults(func=run_exec_config)
    parser_exec.add_argument("config_dir")
    parser_exec.add_argument("-m", "--config-module", default="__cattle__",
                            help="name of the config module. defaults to __cattle__.")
    parser_exec.add_argument("-l", "--local", action="store_true")
    parser_exec.add_argument("-v", "--verbose", action="store_true")
    parser_exec.add_argument("-d", "--dry-run",
                            help="if set, prints the hypothetical rather than running anything",
                            action="store_true")

    parser_status = subparsers.add_parser(
        "status",
        help="Enquire about the remote status of an execution.",
        parents=[hostinfo_parser],
    )
    parser_status.set_defaults(func=run_status)
    parser_status.add_argument("execution_id")

    parser_clean = subparsers.add_parser(
        "clean",
        help="Clean remote resources associated with an execution.",
        parents=[hostinfo_parser],
    )
    parser_clean.set_defaults(func=run_clean)
    parser_clean.add_argument("execution_id")

    args = parser.parse_args()
    return args.func(args)

def run_exec_config(args):
    config_abs = os.path.abspath(args.config_dir.rstrip("/"))
    config_package = os.path.basename(config_abs)

    sys.path.append(os.path.dirname(__file__))

    # Put the parent dir of $config_dir in the import path.
    config_dir_parent = os.path.dirname(config_abs)
    sys.path.append(config_dir_parent)

    importable_module = f"{config_package}.{args.config_module}"
    if importable_module.endswith(".py"):
        importable_module = importable_module[:-3]

    try:
        config_module = importlib.import_module(importable_module)
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
    # Package up the customer configs and a zipapp package and transfer these to
    # the remote hosts.

    execution_id = f"cattle.{time.monotonic()}"
    archive = make_archive(config_abs)
    executable = make_executable()

    print("Running execution ID:", execution_id)

    if args.verbose:
        print("archive:", archive)
        print("executable:", executable)

    password = (
        os.getenv("SSH_SPECIAL_PASS")
        or getpass.getpass("Please enter the password for these hosts: ")
    )

    runners = []

    for h in args.hosts:
        runner = HostRunner(execution_id, h, args.port, args.username, password)
        runners.append(runner)
        runner.connect()
        runner.transfer(archive, executable)
        runner.execute(archive, executable)
        print(f"Host {h} finished with status '{runner.status()}'.")
    else:
        print("Completed execution ID", execution_id)

    return 0

def run_status(args):
    if not args.hosts:
        print("require at least one host when run in remote mode.", file=sys.stderr)
        return 1
    if not args.username:
        print("username required in remote mode.", file=sys.stderr)
        return 1

    password = (
        os.getenv("SSH_SPECIAL_PASS")
        or getpass.getpass("Please enter the password for these hosts: ")
    )

    runners = []

    for h in args.hosts:
        runner = HostRunner(args.execution_id, h, args.port, args.username, password)
        runners.append(runner)
        runner.connect()
        print(f"Host {h} status = {runner.status()}")

    return 0

def run_clean(args):
    if not args.hosts:
        print("require at least one host when run in remote mode.", file=sys.stderr)
        return 1
    if not args.username:
        print("username required in remote mode.", file=sys.stderr)
        return 1

    password = (
        os.getenv("SSH_SPECIAL_PASS")
        or getpass.getpass("Please enter the password for these hosts: ")
    )

    runners = []

    for h in args.hosts:
        runner = HostRunner(args.execution_id, h, args.port, args.username, password)
        runners.append(runner)
        runner.connect()
        runner.clean()
        print(f"Host {h} cleaned.")
    else:
        print(f"Cleaned execution from {len(runners)} hosts.")

    return 0
