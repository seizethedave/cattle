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


## Remote execution

Someone calls `cattle exec somewhere/myconfig --host 10.10.10.10`. What has to happen?

* We create an execution ID.
* Create an archive of things the remote host will need:
    * The folder containing the given config.
    * Enough Python code to run that config. This will probably include the cattle stdlib and a runnable script.
    * A hash of the above.
* Transfer that archive to (each) remote host.
* Remotely:
    * Expand the archive to a well-known place, organized by execution ID.
    * Validate the archive against the hash.
    * Run it.
* After some time:
    * An operator can interrogate each host's status by issuing a status command given the execution ID, which can be used to reach out to each host and peer into the execution folder ...
    * We want a simple file-based protocol the orchestrator can use to understand
        the status of the execution, whether done, in-progress, or errored.
        Something not terribly prone to races.
    * We want each remote execution to have a local log that the operator can examine to understand
        what went wrong.
* Then, to clean up:
    * An operator can issue a cleanup command given an execution ID. This will go out to each host and clean the
        cattle state folder for that execution. This is optional - failure to do this will only eat up a small amount
        of drive space.
    * I think this should only succeeed if the execution isn't currently in progress.


## Privileges

For simplicity, for now, we're not going to implement any privilege escalation.
If you're running these locally, you can do this yourself with `sudo cattle exec
example/poem --local`. If you're running them remotely, the `--username`
specified for the remote hosts needs to have enough permissions to perform the
actions specified in your Cattle config.
