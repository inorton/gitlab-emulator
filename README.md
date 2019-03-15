# Run Gitlab Jobs without Gitlab

Should understand:

 * docker builds on linux and windows
 * shell builds on linux and windows
 * services and service aliases

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
