# Cattle

## Quick overview

* Cattle is a server configurer.
* Cattle applies a configuration to a set of hosts.
* A Cattle configuration file describes a linear set of steps to perform. Each step in the configuration
    selects a facility and what to do with it. (A facility might be `File`, and
    the action might be `Copy` along with the particulars of the `Copy` action.)

* Cattle has a small selection of built-in facilities. (General things like writing a file.)
* You will no doubt need facilities that don't exist yet. You can author your own facilities and either maintain them in your own private repository or contribute them to Cattle's built-in facilities.

## Installation

aa

### Installation in a disposable Python virtual env

Need to run Cattle once and then destroy all traces of it? Use Poetry in a venv.

``` bash
% python3 -m venv /tmp/cattle-env
% source /tmp/cattle-env/bin/activate
(cattle-env) % pip install poetry
(cattle-env) % cd /path/to/cattle/repo
(cattle-env) % poetry install
(cattle-env) % cattle --help
```

## How Cattle works:

_TODO_