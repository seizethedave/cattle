import argparse
import concurrent.futures
import getpass
import importlib
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from typing import Dict, NamedTuple, Union
import zipapp

import paramiko
import scp

class ExecResult(NamedTuple):
    exit_code: int
    result_vars: Dict[str, str] = None

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

class RemoteHostConduit:
    """
    Implements file transfers and command execution for a remote host.
    """
    def __init__(self, host, port, username, password):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.ssh_client = None

    def _connect(self):
        """Establish a connected SSH client, if one isn't already connected."""
        if self.ssh_client is not None:
            return
        c = paramiko.SSHClient()
        c.load_system_host_keys()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(self.host, self.port, self.username, self.password)
        self.ssh_client = c

    def transfer(self, archive, executable, exec_dir):
        self._connect()
        self.exec_command(f"mkdir -p {exec_dir}")
        with scp.SCPClient(self.ssh_client.get_transport()) as scp_client:
            scp_client.put(archive, exec_dir)
            scp_client.put(executable, exec_dir)

    def exec_command(self, cmd: str):
        """Execute command, make sure it's a success, and return stdout as a string."""
        self._connect()
        _, cmd_out, cmd_err = self.ssh_client.exec_command(cmd)
        exit_code = cmd_out.channel.recv_exit_status()
        if exit_code != 0:
            raise Exception(
                f"Execute failed with code {exit_code}: "
                f"stdout={cmd_out.read().decode()} stderr={cmd_err.read().decode()}"
            )
        return cmd_out.read().decode().strip()

class LocalHostConduit:
    """
    A conduit for localhost. Rather than transferring and executing via SSH/SCP,
    we do the local analogs.
    """
    def transfer(self, archive: str, executable: str, exec_dir: str):
        self.exec_command(f"mkdir -p {exec_dir}")
        shutil.copy(archive, exec_dir)
        shutil.copy(executable, exec_dir)

    def exec_command(self, cmd: str):
        proc = subprocess.run(cmd, capture_output=True, check=True, shell=True)
        return proc.stdout.decode().strip()

class HostRunner:
    """
    HostRunner handles all remote host communication: transferring files, running
    the remote cattle module, peeking at statuses, etc.
    """
    def __init__(self, execution_id: str, exec_dir: str, hostdesc: str, conduit: Union[RemoteHostConduit, LocalHostConduit]):
        self.execution_id = execution_id
        self.exec_dir = exec_dir
        self.hostdesc = hostdesc
        self.conduit = conduit

    def transfer(self, archive, executable):
        self.conduit.transfer(archive, executable, self.exec_dir)

    def execute(self, archive, executable):
        archive_filename = os.path.basename(archive)
        executable_filename = os.path.basename(executable)
        config_filename = os.path.join(self.exec_dir, "config")
        script = (
            "set -euxo pipefail && "
            f"cd '{self.exec_dir}' && "
            f"python3 '{executable_filename}' init '{archive_filename}' && "
            f"python3 '{executable_filename}' exec '{config_filename}'"
        )
        self.conduit.exec_command(f"nohup bash -c \"{script}\"")

    def status(self):
        exec_status = os.path.join(self.exec_dir, "STATUS")
        return self.conduit.exec_command(f"cat {exec_status} || echo 'UNKNOWN'")

    def clean(self):
        assert self.exec_dir is not None and self.exec_dir != "/", "exec_dir should not be empty or dangerous-looking"
        self.conduit.exec_command(f"rm -rf {self.exec_dir}")

    def log(self):
        exec_log = os.path.join(self.exec_dir, "exec.log")
        return self.conduit.exec_command(f"cat {exec_log} || echo '<not found>'")

def map_runners(fn, runners):
    """Call `fn` with each of the given runners in a thread pool."""
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_map = {executor.submit(fn, r): r for r in runners}
        for future in concurrent.futures.as_completed(future_map):
            future.result()

def main() -> int:
    return main_args(sys.argv[1:])

def main_args_inner(argv) -> ExecResult:
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("-l", "--local", action="store_true")
    common_parser.add_argument("-ho", "--host", dest="hosts", action="append")
    common_parser.add_argument("-p", "--port", type=int, default=22)
    common_parser.add_argument("-u", "--username", action="store")
    common_parser.add_argument("-rr", "--run-root", action="store", type=str, default="/var/run/cattle",
                               help="allows overriding where the Cattle run dir will be rooted on the target filesystem. (default /var/run/cattle)")

    parser = argparse.ArgumentParser(
        prog="cattle",
        description="cattle: the server configurer.",
    )
    subparsers = parser.add_subparsers()
    parser_exec = subparsers.add_parser(
        "exec",
        help="Execute a Cattle config.",
        parents=[common_parser],
    )
    parser_exec.set_defaults(func=run_exec_config)
    parser_exec.add_argument("config_dir")
    parser_exec.add_argument("-m", "--config-module", default="__cattle__",
                            help="name of the config module. defaults to __cattle__.")
    parser_exec.add_argument("-v", "--verbose", action="store_true")
    parser_exec.add_argument("-d", "--dry-run",
                            help="if set, prints the hypothetical rather than running anything",
                            action="store_true")

    parser_status = subparsers.add_parser(
        "status",
        help="Enquire about the remote status of an execution.",
        parents=[common_parser],
    )
    parser_status.set_defaults(func=run_status)
    parser_status.add_argument("execution_id")

    parser_clean = subparsers.add_parser(
        "clean",
        help="Clean remote resources associated with an execution.",
        parents=[common_parser],
    )
    parser_clean.set_defaults(func=run_clean)
    parser_clean.add_argument("execution_id")

    parser_log = subparsers.add_parser(
        "log",
        help="View remote logs for an execution.",
        parents=[common_parser],
    )
    parser_log.set_defaults(func=run_log)
    parser_log.add_argument("execution_id")

    args = parser.parse_args(argv)
    res: ExecResult = args.func(args)
    return res

def main_args(argv) -> int:
    return main_args_inner(argv).exit_code

def runners_from_args(args, execution_id):
    exec_dir = os.path.join(args.run_root, execution_id)

    if args.local:
        return [HostRunner(execution_id, exec_dir=exec_dir, hostdesc="[local]", conduit=LocalHostConduit())]

    if not args.hosts:
        raise Exception("require at least one host when run in remote mode.")
    if not args.username:
        raise Exception("username required in remote mode.")
    password = (
        os.getenv("SSH_SPECIAL_PASS")
        or getpass.getpass("Please enter the password for these hosts: ")
    )

    return [
        HostRunner(
            execution_id=execution_id,
            exec_dir=exec_dir,
            hostdesc=h,
            conduit=RemoteHostConduit(h, args.port, args.username, password),
        )
        for h in args.hosts
    ]

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
        importlib.import_module(importable_module)
    except ModuleNotFoundError as e:
        print(f"couldn't load config: {e}", file=sys.stderr)
        return ExecResult(1)

    # Package up the customer configs and a zipapp package and transfer these to
    # the remote hosts.

    execution_id = f"cattle.{time.monotonic()}"
    print("Running execution ID:", execution_id)

    try:
        runners = runners_from_args(args, execution_id)
    except Exception as e:
        print(e.msg, file=sys.stderr)
        return ExecResult(1)

    archive = make_archive(config_abs)
    executable = make_executable()
    if args.verbose:
        print("archive:", archive)
        print("executable:", executable)

    def transfer_and_exec(runner):
        runner.transfer(archive, executable)
        runner.execute(archive, executable)
        print(f"Host {runner.hostdesc} finished with status '{runner.status()}'.")

    map_runners(transfer_and_exec, runners)
    print("Completed execution ID", execution_id)
    return ExecResult(0, {"execution_id": execution_id})

def run_status(args):
    try:
        runners = runners_from_args(args, args.execution_id)
    except Exception as e:
        print(e.msg, file=sys.stderr)
        return ExecResult(1)

    def status(runner):
        print(f"Host {runner.hostdesc} status = {runner.status()}")

    map_runners(status, runners)
    return ExecResult(0)

def run_clean(args):
    try:
        runners = runners_from_args(args, args.execution_id)
    except Exception as e:
        print(e.msg, file=sys.stderr)
        return ExecResult(1)

    def clean(runner):
        runner.clean()
        print(f"Host {runner.hostdesc} cleaned.")

    map_runners(clean, runners)
    print(f"Cleaned execution from {len(runners)} hosts.")
    return ExecResult(0)

def run_log(args):
    try:
        runners = runners_from_args(args, args.execution_id)
    except Exception as e:
        print(e.msg, file=sys.stderr)
        return ExecResult(1)

    lock = threading.Lock()

    def clean(runner):
        log = runner.log()
        # (Don't interleave the logs from different hosts.)
        with lock:
            print(f"Host {runner.hostdesc} log:")
            print(log)

    map_runners(clean, runners)
    return ExecResult(0)
