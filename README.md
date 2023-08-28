# Gitlab Emulator (gle)

[![pipeline status](https://gitlab.com/cunity/gitlab-emulator/badges/main/pipeline.svg)](https://gitlab.com/cunity/gitlab-emulator/-/commits/main)
[![coverage report](https://gitlab.com/cunity/gitlab-emulator/badges/main/coverage.svg)](https://gitlab.com/cunity/gitlab-emulator/-/commits/main)

__gle__ lets you run many gitlab pipeline jobs and often entire pipeline graphs on your own machine directly. The goal of the project has been as an aid to local incremental work on pipeline logic (needs, docker services, rules) without consuming potentially scarce or expensive resources of gitlab runners.

For the most part, _gle_ is able to correctly execute jobs in pipelines that use `script`, `before_script`, `after_script`, `extends`, `include`, `variables` and `needs`. If you have docker installed and working you can execute jobs that make use of `image` and `services` too.

It has some preliminary understanding of rule expressions allowing you to develop rule expressions for `include` and `rules` for jobs without pushing pipelines.

__glp__ is a recent tool added to explore and manage real pipelines, it supports downloading of artifacts and triggering of pipelines on the server. It also supports generation of subsets of a pipeline and either running those on a temporary branch or outputting to a file.  Aside from this last feature, _glp_ has been surpassed by the recent _glab_ [glab CLI project](https://gitlab.com/gitlab-org/cli) which you should use if you want to manage pipelines on a real server.

Supported Gitlab v14.2+ features:

 * `needs` can use any job regardless of the `stage` value

Supported Gitlab v14.1+ features:

 * docker on windows, linux and mac.
 * `include` and `extends` keywords
 * `needs` (DAG-ordered builds)
 * `timeout` for jobs

Requirements:

 * Python 3.7 or later (preferrably 3.8+)
 * requests
 * pyyaml

Supported Platforms:

| Emulator                         |
| -------------------------------- |
| Windows (shell + docker)         |
| Linux (shell + docker)           |
| Mac (shell + docker)             |

_Note_ GitlabPythonRunner is no longer supported

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

The tool can be executed as a module, or if your python is setup, using the `gle` script:

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

Gitlab-emulator now contains a very basic (experimental) shell runner, aimed at use on systems that cannot run the official gitlab-runner
program such as those that have no Golang support.

The runner only supports the shell executor.  And uses a basic configuration file format:

```
ca_cert: /etc/gitlab/my-ca.crt
http_proxy: http://127.0.0.1:8080/
https_proxy: http://127.0.0.1:8080/
server: https://gitlab.com
token: runner-token-secret-string
builds_dir: /home/gitlab-runner/builds
```

`http_proxy`, `https_proxy` and `ca_cert` are optional. 

`token` is the string typically set in a `config.toml` files as `token` in the `[[runners]]` section after you have run `gitlab-runner register` on another system. Or if you have used the runner creation page on gitlab and have a new runner token, eg:

```
gitlab-py-runner register --token glrt-Cfx1-JPQzmhTuXNuR
```

You can then invoke the runner like so:

```
gitlab-py-runner run
```

```
python3 -m gitlabemu.cirunner 
```