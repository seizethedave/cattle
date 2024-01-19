import filecmp
import os
import shutil

from cattle.facility.facility import Facility

class Chmod(Facility):
    def __init__(self, path, mode):
        super(Facility).__init__()
        self.path = path
        self.mode = mode

    def should_run(self):
        return True # Chmod is always safe to reapply.

    def run(self):
        os.chmod(self.path, self.mode)

    def dry_run(self):
        return [f"chmod({self.path}, {oct(self.mode)})"]

class Chown(Facility):
    def __init__(self, path, owner_name=None, group_name=None):
        super(Facility).__init__()
        self.path = path
        self.owner_name = owner_name
        self.group_name = group_name

    def should_run(self):
        return True # Chown is always safe to reapply.

    def run(self):
        shutil.chown(self.path, self.owner_name, self.group_name)

    def dry_run(self):
        return [f"chown({self.path} user={self.owner_name}, group={self.group_name})"]

class MakeDir(Facility):
    def __init__(self, path):
        super(Facility).__init__()
        self.path = path

    def should_run(self):
        return True # Naively idempotent.

    def run(self):
        os.makedirs(self.path, exist_ok=True)

    def dry_run(self):
        return [f"make directory {self.path}"]

class InstallFile(Facility):
    def __init__(self, sourcefile, dest):
        """
        A file installation facility.
        >>> InstallFile("foo.txt", "/var/run/foo.txt")
        """
        super(Facility).__init__()
        self.sourcepath = sourcefile
        self.destpath = dest

    def should_run(self):
        filecmp.clear_cache()
        try:
            return not filecmp.cmp(self.sourcepath, self.destpath, shallow=False)
        except FileNotFoundError:
            return True

    def run(self):
        shutil.copyfile(self.sourcepath, self.destpath)

    def dry_run(self) -> str:
        return [f"install file {self.destpath}"]
