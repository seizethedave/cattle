import scp
import tarfile
import tempfile

import paramiko

def createSSHClient(server, port, user, password):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(server, port, user, password)
    return client

def run_config(cfg, dry_run):
    steps = getattr(cfg, 'steps', None)

    if steps is None:
        raise Exception("The config file doesn't define a steps attribute.")

    if dry_run:
        for step in steps:
            print(f"> {step.__class__.__name__}:")
            for c in step.dry_run():
                print(f"   > {c}")
    else:
        for step in steps:
            step.run()

def make_archive(execution_id, cfg_dir):
    def add_filter(item: tarfile.TarInfo):
        return item if "__pycache__" not in item.name else None
    with tempfile.NamedTemporaryFile(mode="w+b", delete=False) as t:
        with tarfile.open(mode="w:gz", fileobj=t) as tar:
            tar.add(cfg_dir, arcname="config", recursive=True, filter=add_filter)
            return t.name

class HostRunner:
    def __init__(self, execution_id, archive, host, username, password):
        self.execution_id = execution_id
        self.archive = archive
        self.host = host
        self.username = username
        self.password = password

    def transfer(self):
        dest_dir = f"/var/run/cattle/{self.execution_id}"
        ssh = createSSHClient(self.host, 22, self.username, self.password)
        ssh.exec_command(f"mkdir -p {dest_dir}")
        with scp.SCPClient(ssh.get_transport()) as scp_client:
            scp_client.put(self.archive, dest_dir)
