# Gitlab Emulator and Gitlab Python Runner

[![pipeline status](https://gitlab.com/cunity/gitlab-emulator/badges/master/pipeline.svg)](https://gitlab.com/cunity/gitlab-emulator/-/commits/master)
[![coverage report](https://gitlab.com/cunity/gitlab-emulator/badges/master/coverage.svg)](https://gitlab.com/cunity/gitlab-emulator/-/commits/master)

Supported Gitlab v14.2 features:

 * `needs` can use any job regardless of the `stage` value

Supported Gitlab v14.1 (and earlier) features:

 * docker on windows, linux and mac.
 * `include` and `extends` keywords
 * `needs` (DAG-ordered builds)
 * `timeout` for jobs

Requirements:

 * Python 3.7 or later (preferrably 3.8+)
 * requests
 * pyyaml

Supported Platforms:

| Emulator                         | Runner OSs                     |
| -------------------------------- | ------------------------------ |
| Windows (shell + docker)         | AIX                            |
| Linux (shell + docker)           | HP-UX                          |
| Mac (shell + docker)             | Solaris                        |
|                                  | Windows + Linux (testing only) |

_Note. Runner support on AIX, HP-UX and Solaris is experimental_

## Emulator Installation

Installing from source:
```
cd emulator
sudo python3 -m pip install .
```

Installing from PyPi
```
sudo python3 -m pip install gitlab-emulator
```

# Examples

The tool can be executed as a module, or if your python is setup, using the `locallab.py` script:

(`gle` will usually only be on your `PATH` if you install using `pip` with `sudo`)

```
gle --help
```
or
```
python3 -m gitlabemu --help
```

## List Possible Jobs

```
cd my-gitlab-repo
gle --list
```

## Run a single job

```
cd my-gitlab-repo
gle JOBNAME
```

## Run all required jobs (dependency / needs order)

```
cd my-gitlab-repo
gle --full JOBNAME
```

## Enter a docker container for a job

```
gle -i JOBNAME
```

## Run a job with additional docker mounted paths

The following will mount the `/mnt/caches` path into the container as `/caches`.  You can also append `:ro` to force
the bind mount to be read-only.

```
export GLE_DOCKER_VOLUMES="/mnt/caches:/caches"
gle JOBNAME
```

## User Settings file

Now some options such as default docker volumes or the version of gitlab to support can be
defined in a configuration file that gitlab-emulator will load by default.

On linux, gitlab-emulator will load the file `~/.gle/emulator.yml` on windows `%LOCALAPPDATA%\\.gle\\emulator.yml` or the file set in the `GLE_CONFIG` environment variable.

eg:

```
emulator:
  gitlab:
    version: 14.2.  # target gitlab 14.2 (the default)
  docker:
    volumes:
      # add extra docker volumes to be automatically added to docker jobs
      - /home/inb/gle-caches:/caches:rw
```


# Gitlab Python Runner

The Python runner lets you use Gitlab with machines that can't run the
official gitlab-runner (usually systems that can't support Golang) such
as HP-UX, AIX and Solaris but also others that can run modern Python 3.

For more info and instructions, see the `runner` folder `README.md` file
