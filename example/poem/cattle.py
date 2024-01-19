#!/usr/bin/env python

"""
This example Cattle configuration installs the poem in poem.txt into /var/poems/poem.txt
"""

import os

from cattle.facility.file import InstallFile, MakeDir, Chmod, Chown

POEMS_DIR = "/var/poems"
POEM_FILE = os.path.join(POEMS_DIR, "poem.txt")

deps = [
    "poem.txt",
]

steps = [
    MakeDir(POEMS_DIR),
    InstallFile("poem.txt", dest=POEM_FILE),
    Chmod(POEM_FILE, mode=0o666),
    Chown(POEM_FILE, owner_name="root"),
]
