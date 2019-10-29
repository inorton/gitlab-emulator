# Run Gitlab Jobs without Gitlab

Should understand:

 * docker builds on linux and windows
 * shell builds on linux and windows
 * services and service aliases

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

## Run all required jobs (dependency order)

```
cd my-gitlab-repo
python -m gitlabemu --full JOBNAME
```
