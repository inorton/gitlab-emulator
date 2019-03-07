# Run Gitlab Jobs without Gitlab

Should understand:

 * docker builds on linux
 * shell builds on linux and windows

## List Possible Jobs

```
cd my-gitlab-repo
python /home/inb/gitlabemu/locallab.py --list
```

## Run a single job

```
cd my-gitlab-repo
python /home/inb/gitlabemu/locallab.py JOBNAME
```

## Run all required jobs (dependency order)

```
cd my-gitlab-repo
python /home/inb/gitlabemu/locallab.py --full JOBNAME
```
