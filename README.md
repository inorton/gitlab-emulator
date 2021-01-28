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


Installing from source:
```
python3 -m pip install .
```

Installing from PyPi
```
python3 -m pip install gitlab-emulator
```

# Examples

The tool can be executed as a module, or if your python is setup, using the `locallab.py` script:

```
locallab.py --help
```
or
```
python3 -m gitlabemu --help
```

## List Possible Jobs

```
cd my-gitlab-repo
python3 -m gitlabemu --list
```

## Run a single job

```
cd my-gitlab-repo
python3 -m gitlabemu JOBNAME
```

## Run all required jobs (dependency / needs order)

```
cd my-gitlab-repo
python3 -m gitlabemu --full JOBNAME
```
