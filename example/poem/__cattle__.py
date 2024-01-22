#!/usr/bin/env python

"""
This example Cattle configuration installs the poem in poem.txt into /var/poems/poem.txt
"""

import os

from cattle.facility.file import InstallFile, MakeDir, Chmod, Chown

POEMS_DIR = "/var/poems"
POEM_FILE = os.path.join(POEMS_DIR, "poem.txt")

def cfg_relative(path):
    "Returns an absolute path for a path relative to this config."
    return os.path.join(os.path.dirname(__file__), path)

steps = [
    MakeDir(POEMS_DIR),
    InstallFile(cfg_relative("poem.txt"), dest=POEM_FILE),
    Chmod(POEM_FILE, mode=0o666),
    Chown(POEM_FILE, owner_name="root"),
]
