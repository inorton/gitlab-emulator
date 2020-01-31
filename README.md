# Run Gitlab Jobs without Gitlab

Supported Gitlab features:

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
