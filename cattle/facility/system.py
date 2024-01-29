"""
Facilities related to Linux system stuff. Packages, systemd services, etc.
"""

import subprocess
from typing import List

class InstallDebPackages:
    def __init__(self, packages: List[str]):
        if isinstance(packages, str):
            packages = [packages]
        self.packages = packages

    def should_run(self):
        return True # It's naively idempotent.

    def run(self):
        subprocess.run(["apt-get", "update", "-y"], check=True)
        subprocess.run(["apt-get", "install", "-y"] + self.packages, check=True)

    def dry_run(self):
        return [f"apt-get update && apt-get install -y {self.package_name}"]

class RestartSystemdService:
    def __init__(self, service):
        self.service = service

    def should_run(self):
        return True

    def run(self):
        # Unmask first, as the service could be masked and unstartable from
        # prior events.
        subprocess.run(["systemctl", "unmask", self.service])
        subprocess.run(["systemctl", "restart", self.service], check=True)

    def dry_run(self):
        return [
            f"systemctl unmask {self.service}",
            f"systemctl restart {self.service}",
        ]
