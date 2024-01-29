# Cattle

## Quick overview

* Cattle is a remote server configurer.
* Cattle applies a configuration to a set of hosts. Potentially many hosts!
* A Cattle configuration file describes a linear set of steps to perform. Each step in the configuration
    selects a facility and what to do with it. (Example facilities are `Symlink` and `RestartSystemdService`.)
* Cattle has a small selection of built-in facilities. You will no doubt need facilities that don't exist yet. You can author your own facilities and either maintain them in your own private repository or contribute them to Cattle's built-in facilities.

## Prerequisites

* Unix-like orchestrator and remote hosts.
* Python 3.6+ on the remote hosts.
* SSH access to the remote hosts.

## Installation

``` bash
% pip install git+https://github.com/seizethedave/cattle
```

### Installation in a disposable Python virtual env

Need to run Cattle once and then nuke it?

``` bash
% python3 -m venv /tmp/cattle-env
% source /tmp/cattle-env/bin/activate
(cattle-env) % pip install git+https://github.com/seizethedave/cattle
(cattle-env) % cattle --help
```

## Examples

There are a couple of example configs in /example. Here's how to run one on our
remote host (`rube`), interrogate the logs, and clean up:

``` bash
(cattle-env2) david@junker cattle % cattle exec example/poem --host rube --username root
Running execution ID: cattle.2068345.076157166
Host rube finished with status 'DONE'.
Completed execution ID cattle.2068345.076157166
(cattle-env2) david@junker cattle % cattle status cattle.2068345.076157166 --host rube --username root
Host rube status = DONE
(cattle-env2) david@junker cattle % cattle log cattle.2068345.076157166 --host rube --username root
Host rube log:
2024-01-29 18:59:20,027 INFO running execution at path /var/run/cattle/cattle.2068345.076157166
2024-01-29 18:59:20,027 INFO running in real mode
2024-01-29 18:59:20,027 INFO Running step 1: MakeDir (make directory /var/poems)
2024-01-29 18:59:20,027 INFO Step 1 completed successfully.
2024-01-29 18:59:20,027 INFO Running step 2: InstallFile (install file /var/poems/poem.txt)
2024-01-29 18:59:20,028 INFO should run = False; skipping.
2024-01-29 18:59:20,028 INFO Step 2 completed successfully.
2024-01-29 18:59:20,028 INFO Running step 3: Chmod (chmod(/var/poems/poem.txt, 0o666))
2024-01-29 18:59:20,028 INFO Step 3 completed successfully.
2024-01-29 18:59:20,028 INFO Running step 4: Chown (chown(/var/poems/poem.txt user=root, group=None))
2024-01-29 18:59:20,029 INFO Step 4 completed successfully.
2024-01-29 18:59:20,029 INFO config executed successfully.
(cattle-env2) david@junker cattle % ssh root@rube cat /var/poems/poem.txt
"In youth's sweet bloom, where fancy reigns,
Mirth abounds and joy sustains.
A realm of wonder, untarnished, bright, in every lad and lass, a delight."
(cattle-env2) david@junker cattle % cattle clean cattle.2068345.076157166 --host rube --username root
Host rube cleaned.
Cleaned execution from 1 hosts.
```

## Writing your own configs

A Cattle config is a directory containing a `__cattle__.py` file. This is
regular Python code that must contain a `steps` attribute with a list of
facility instances describing a linear set of steps Cattle will follow to set up
a remote host. You may reference any of the facilities that come with Cattle,
and you can also write your own facility types as shown in [example/flaky](example/flaky).

Your config directory can also include other arbitrary files that your config
makes use of. These files will all be schlepped over to the remote host(s) at
execution time. See [example/poem](example/poem).

## Writing your own facilities

You can author new facilities by writing a new class that provides at least
these `run` and `desc` methods:

``` python
class MyFacility:
    def __init__(self, my_arg):
        self.my_arg = my_arg

    def run(self):
        # (Carry out the action.)

    def desc(self):
        return f"install my facility with arg {self.my_arg}"
```

Cattle will assume it can blindly re-execute facilities that have failed before,
so you must design your facilities to be idempotent whenever possible. There's a
`should_run` method you can optionally implement if you want to keep an
expensive action from being re-applied fruitlessly. (Or if your run method is
for some reason unable to be idempotent.)

As facilities should be idempotent, they will also be simpler to reason about
and retry if they're brutally simple and single-purpose. For example, rather
than having a single `CreateFile` facility that includes optional parameters for
owner, group, mode, compression level and so on, it would be more
straightforward to reason about retries for a series of facility instances of
types [`CreateFile`, `Chown`, `Chgrp`, `Chmod`, `Compress`, ...] each doing one
thing.

## How Cattle works:

Cattle configs are orchestrated from one machine and run on many. Cattle does
not attempt to round-trip issue every command step of a config remotely, but
instead replicates the runnable parts of itself and everything else needed to
run a config to each destination machine. (That means you don't need to
pre-install a specific compatible version of Cattle on the remote host; the
current local version of Cattle will do that every single time!) When all the
files are there, it kicks off the config suite remotely, and parallelizes over
the potentially many hosts.

See more notes in [DESIGN.md](DESIGN.md).
