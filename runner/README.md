# Gitlab Python Runner

Gitlab is brilliant, the official gitlab runner is pretty robust and supports all the best new features of gitlab.

But one thing that poses as a bit of an obstacle for those of us with fairly exotic build environments is that the
official gitlab runner is written in Go, and Go (or GCC-go) is not available on every platform.

So this project was born to fill this niche where you want to use gitlab on a system that simply can't run the official
gitlab-runner and where the ssh executor wont work.  You should be able to a "shell" executor on any system that can
run `git` and supports recent `python` (3.6+)

The runner is in active use on other projects:
  * CUnit - https://gitlab.com/cunity/cunit/pipelines
    * Windows Docker
    * Solaris 11 on AMD64
    * Linux Ubuntu 19.04 on Power9

Systems that are intended as targets are:

  * Windows + Docker (until official windows docker runner is ready for use)
  * Solaris 11 (patches to the official runner exist but are hard to apply)
  * HP-UX on Itanium (IA64)
  * AIX 6.1, 7.1 on POWER
  * Linux on POWER
  * x64/x86 Linux (but only for internal testing)

## Supported Systems

| *Platform*          | *Shell*     | *Docker*     | *Artifact Upload*   | *Artifact download/dependencies*   |
| ------------------- | ----------- | ------------ | ------------------- | ---------------------------------- |
| Linux (amd64)       | yes         | yes          | yes                 | yes                                |
| Linux (power)       | yes         | maybe        | yes                 | yes                                |
| Windows 10/2019     | yes         | yes          | yes                 | yes                                |
| Solaris 11 (amd64)  | yes         | n/a          | yes                 | yes                                |
| Solaris 11 (sparc)  | yes         | n/a          | yes                 | yes                                |
| AIX 7.1 (python3)   | yes         | n/a          | yes                 | yes                                |
| AIX 7.2 (python3)   | yes         | n/a          | yes                 | yes                                |
| HPUX-11.31 (python3)| yes         | n/a          | yes                 | yes                                |

There really is no sensible reason to use `gilab-python-runner` on x64 linux other than to test changes to the project.


# Setup and Deployment

## Register a Runner

At the very least you need to know the gitlab server address (eg `https://gitlab.com`) and the runner registration token
(you get this from your runners page on your server, project or group)

```
pip install gitlab-python-runner

mkdir gitlab
cd gitlab

gitlab-runner.py --register https://gitlab.com --regtoken xZ139xcd343424cd --type shell --tag mytag
```

This should exit without an error (TODO print more useful feedback) and have created a config file.

```
cat gitlab-runner.yml
dir: /home/inb/gitlab
executor: shell
server: https://gitlab.com
shell: /bin/sh
token: !!python/unicode 'guXssHacXXL6931Xn3Xx'
```

This will have created a new runner on your gitlab server with the tag given above by `--tag ARG`  It should also have
set a meaningful description for you.


## Starting the Runner

You can decide to start the runner as part of an init script, or within a screen session or maybe as the entrypoint in
a docker container.  You simply need to point it at the yaml file created by using `--register`

```
gitlab-runner.py --start /home/inb/gitlab/gitlab-runner.yml
```

Which should start to poll the server :

```
inb@carrot:~/gitlab$ gitlab-runner.py --start gitlab-runner.yml
2019-04-25 15:40:45,246 gitlab-emulator  Polling for jobs..
2019-04-25 15:40:55,742 gitlab-emulator  Polling for jobs..
```