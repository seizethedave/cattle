# Architectural decisions

## Optimize for retry

Configurations, their steps, and the hosts they run on are complex. They can
fail at various steps. Some steps may involve network operations such as
installing a package from a remote repository. The result of applying a step
could be failure, success, or simply "I don't know." With any non-success
outcome the default action should be to simply retry the step. Thus, any Cattle
facility's `run` function should be written in an idempotent fashion.

## Plan locally, drive remotely

Imagine this valid Cattle setup:
* A single orchestrator host.
* A configuration script with 100 steps that can take ~30 minutes to complete.
* 1000 hosts to configure.

The star formation of the orchestrator host along with the set of configured
servers is a distributed system with potentially 1000 different network routes
that can fail intermittently throughout the 30 minutes of configuration time.
Further, the orchestrator host may be an engineer's laptop sitting perilously
close to a tall tippy cup of coffee.

As much as possible, we'd like to eliminate the network and the orchestrator
host from being healthy in order for each configured host to make forward
progress in these 100 steps. So we'll avoid implementing Cattle in a way where
the orchestrator is the one issuing O(steps) network calls to each configured
host. Each configured host should be driving those steps to completion, and a
Cattle orchestrator can ask later about each host's completion status.

So we'll *plan locally, drive remotely*.
