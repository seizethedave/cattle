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

def make_archive(execution_id, cfg_dir):
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
    def __init__(self, execution_id, archive, executable, host, port, username, password):
        self.execution_id = execution_id
        self.archive = archive
        self.executable = executable
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

    def transfer(self):
        dest_dir = f"/var/run/cattle/{self.execution_id}"
        self.ssh_client.exec_command(f"mkdir -p {dest_dir}")
        with scp.SCPClient(self.ssh_client.get_transport()) as scp_client:
            scp_client.put(self.archive, dest_dir)
            scp_client.put(self.executable, dest_dir)

    def execute(self, dry_run: bool):
        dest_dir = f"/var/run/cattle/{self.execution_id}"
        archive_filename = os.path.basename(self.archive)
        executable_filename = os.path.basename(self.executable)
        self.ssh_client.exec_command(f"cd {dest_dir} && python3 {executable_filename} init {archive_filename}")
        config_filename = os.path.join(dest_dir, "config")
        self.ssh_client.exec_command(f"cd {dest_dir} && python3 {executable_filename} exec {config_filename}")

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="cattle",
        description="cattle: the server configurer.",
    )
    subparsers = parser.add_subparsers()
    parser_exec = subparsers.add_parser("exec")
    parser_exec.set_defaults(func=exec_config)
    parser_exec.add_argument("config_dir")
    parser_exec.add_argument("-m", "--config-module", default="__cattle__",
                            help="name of the config module. defaults to __cattle__.")
    parser_exec.add_argument("-ho", "--host", dest="hosts", action="append")
    parser_exec.add_argument("-p", "--port", default=22)
    parser_exec.add_argument("-l", "--local", action="store_true")
    parser_exec.add_argument("-u", "--username", action="store")
    parser_exec.add_argument("-v", "--verbose", action="store_true")
    parser_exec.add_argument("-d", "--dry-run",
                            help="if set, prints the hypothetical rather than running anything",
                            action="store_true")

    args = parser.parse_args()
    return args.func(args)

def exec_config(args):
    config_dir_with_module = os.path.join(args.config_dir, args.config_module)
    mod = config_dir_with_module.replace("/", ".")
    if mod.endswith(".py"):
        mod = mod[:-3]

    sys.path.append(os.path.dirname(__file__))

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
    # Package up the customer configs and a zipapp package and transfer these to
    # the remote hosts.

    execution_id = "cattle_exec_{}".format(time.monotonic())
    archive = make_archive(execution_id, args.config_dir)
    executable = make_executable()

    if args.verbose:
        print("archive:", archive)
        print("executable:", executable)

        # For my testing:
        import shutil
        shutil.copy(archive, "/Users/dgrant/dev/remote-test/")
        shutil.copy(executable, "/Users/dgrant/dev/remote-test/")
        return

    password = (
        os.getenv("SSH_SPECIAL_PASS")
        or getpass.getpass("Please enter the password for these hosts: ")
    )

    runners = []

    for h in args.hosts:
        runner = HostRunner(execution_id, archive, executable, h, args.port, args.username, password)
        runners.append(runner)
        runner.connect()
        runner.transfer()
        runner.execute(args.dry_run)

    return 0
