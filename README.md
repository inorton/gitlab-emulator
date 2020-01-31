# Run Gitlab Jobs without Gitlab

Supported Gitlab v11 and v12 features:

 * docker (windows and linux)
 * `include` and `extends` keywords
 * `needs` (DAG-ordered builds)

Supported Platforms:

 * Executors:
   * shell:
     * windows
     * linux
     * unix (any modern supported python platform - eg solaris, OSX, AIX)
   * docker
     * linux
     * windows
   * services and service aliases
     * linux
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
