import tarfile
import tempfile

import paramiko
import scp

def make_archive(execution_id, cfg_dir):
    def add_filter(item: tarfile.TarInfo):
        return item if "__pycache__" not in item.name else None
    with tempfile.NamedTemporaryFile(mode="w+b", delete=False) as t:
        with tarfile.open(mode="w:gz", fileobj=t) as tar:
            tar.add(cfg_dir, arcname="config", recursive=True, filter=add_filter)
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
