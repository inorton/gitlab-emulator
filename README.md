# Gitlab Emulator and Gitlab Python Runner

[![pipeline status](https://gitlab.com/cunity/gitlab-emulator/badges/master/pipeline.svg)](https://gitlab.com/cunity/gitlab-emulator/-/commits/master)
[![coverage report](https://gitlab.com/cunity/gitlab-emulator/badges/master/coverage.svg)](https://gitlab.com/cunity/gitlab-emulator/-/commits/master)

Supported Gitlab v11 and v12 features:

 * docker (windows and linux)
 * `include` and `extends` keywords
 * `needs` (DAG-ordered builds)
 * `timeout` for jobs

Supported Platforms:

| Emulator                         | Runner OSs                     |
| -------------------------------- | ------------------------------ |
| Windows (shell + docker)         | AIX                            |
| Linux (shell + docker)           | HP-UX                          |
| Mac (shell + docker)             | Solaris                        |
|                                  | Windows + Linux (testing only) |

## Emulator Installation

Installing from source:
```
cd emulator
python3 -m pip install .
```

Installing from PyPi
```
python3 -m pip install gitlab-emulator
```

# Examples

The tool can be executed as a module, or if your python is setup, using the `locallab.py` script:

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

# Gitlab Python Runner

The Python runner lets you use Gitlab with machines that can't run the
official gitlab-runner (usually systems that can't support Golang) such
as HP-UX, AIX and Solaris but also others that can run modern Python 3.

For more info and instructions, see the `runner` folder `README.md` file
