# Run Gitlab Jobs without Gitlab

Supported Gitlab v11 and v12 features:

 * docker (windows and linux)
 * `include` and `extends` keywords
 * `needs` (DAG-ordered builds)
 * `timeout` for jobs

Supported Platforms:

 * Executors:
   * shell:
     * windows
     * linux
     * MacOS X
     * unix (any modern supported python platform - eg solaris, AIX)
   * docker
     * linux
     * windows
     * Docker Desktop on Mac
   * services and service aliases
     * linux
     * linux services with Docker Desktop on MAc
     * windows (untested)

## Installation

```
python -m pip install .
```

or
```
python -m pip install gitlab-emulator
```

# Examples

## List Possible Jobs

```
cd my-gitlab-repo
python -m gitlabemu --list
```

## Run a single job

```
cd my-gitlab-repo
python -m gitlabemu JOBNAME
```

## Run all required jobs (dependency / needs order)

```
cd my-gitlab-repo
python -m gitlabemu --full JOBNAME
```
