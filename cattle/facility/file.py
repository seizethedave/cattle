import filecmp
import os
import shutil

class Chmod:
    def __init__(self, path, mode):
        self.path = path
        self.mode = mode

    def should_run(self):
        return True # Chmod is always safe to reapply.

    def run(self):
        os.chmod(self.path, self.mode)

    def desc(self):
        return f"chmod({self.path}, {oct(self.mode)})"

class Chown:
    def __init__(self, path, owner_name=None, group_name=None):
        self.path = path
        self.owner_name = owner_name
        self.group_name = group_name

    def should_run(self):
        return True # Chown is always safe to reapply.

    def run(self):
        shutil.chown(self.path, self.owner_name, self.group_name)

    def desc(self):
        return f"chown({self.path} user={self.owner_name}, group={self.group_name})"

class MakeDir:
    def __init__(self, path):
        self.path = path

    def should_run(self):
        return True # Naively idempotent.

    def run(self):
        os.makedirs(self.path, exist_ok=True)

    def desc(self):
        return f"make directory {self.path}"

class InstallFile:
    def __init__(self, sourcefile, dest):
        """
        A file installation facility.
        >>> InstallFile("foo.txt", "/var/run/foo.txt")
        """
        self.sourcepath = sourcefile
        self.destpath = dest

    def should_run(self):
        # InstallFile should run only if there isn't an identical file already
        # at the destination path.
        filecmp.clear_cache()
        try:
            return not filecmp.cmp(self.sourcepath, self.destpath, shallow=False)
        except FileNotFoundError:
            return True

    def run(self):
        shutil.copyfile(self.sourcepath, self.destpath)

    def desc(self):
        return f"install file {self.destpath}"

class Symlink:
    def __init__(self, source, dest):
        self.source = source
        self.dest = dest

    def should_run(self):
        return True

    def run(self):
        try:
            os.symlink(self.source, self.dest)
        except FileExistsError:
            pass

    def desc(self):
        return f"symlink {self.source} -> {self.dest}"

class Unlink:
    def __init__(self, path):
        self.path = path

    def should_run(self):
        return True

    def run(self):
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass

    def desc(self):
        return f"unlink {self.path}"
