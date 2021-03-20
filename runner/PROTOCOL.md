# Gitlab Runner Research

## Polling for Jobs to Run

### Request Headers
```
POST /api/v4/jobs/request HTTP/1.1
Host: gitlab.zerg.mine.nu
User-Agent: gitlab-runner 11.4.2 (11-4-stable; go1.8.7; linux/amd64)
Content-Length: 360
Accept: application/json
Content-Type: application/json
Accept-Encoding: gzip
```
### Request Body
```
{
  "info": {
    "name": "gitlab-runner",
    "version": "11.4.2",
    "revision": "cf91d5e1",
    "platform": "linux",
    "architecture": "amd64",
    "executor": "shell",
    "shell": "bash",
    "features": {
      "variables": true,
      "image": false,
      "services": false,
      "artifacts": true,
      "cache": true,
      "shared": true,
      "upload_multiple_artifacts": true,
      "session": true,
      "terminal": true
    }
  },
  "token": "4db707c8422ee4b269bc9c7fcfd74c"
}
```

### Response Headers (no jobs pending)
```
HTTP/1.1 204 No Content
Server: nginx
Date: Wed, 24 Apr 2019 17:20:04 GMT
Cache-Control: no-cache
Gitlab-Ci-Builds-Polling: yes
Vary: Origin
X-Content-Type-Options: nosniff
X-Frame-Options: SAMEORIGIN
X-Gitlab-Last-Update: 30ca7d4332af8c1f0527ea0bfddb066f
X-Request-Id: 2b9174d5-1b5d-4309-895c-a2275fc053ed
X-Runtime: 0.041701
Strict-Transport-Security: max-age=31536000
Set-Cookie: b8a37d986345d6e111e8eab2f149e5ea=406390a5c34dc76f57644756105c36c3; path=/; HttpOnly
```

### Response Headers (run a job)
```
HTTP/1.1 201 Created
Server: nginx
Date: Wed, 24 Apr 2019 17:20:02 GMT
Content-Type: application/json
Content-Length: 3957
Cache-Control: max-age=0, private, must-revalidate
Etag: W/"1cf2be85ff692227c6124062b9457ca4"
Gitlab-Ci-Builds-Polling: yes
Vary: Origin
X-Content-Type-Options: nosniff
X-Frame-Options: SAMEORIGIN
X-Request-Id: c3319574-c65a-4cd2-bc0d-42fe8fe45cca
X-Runtime: 0.777427
Strict-Transport-Security: max-age=31536000
Set-Cookie: b8a37d986345d6e111e8eab2f149e5ea=406390a5c34dc76f57644756105c36c3; path=/; HttpOnly
```

```
{
  "id": 6,
  "token": "eX9zJy7UzLv4pWYg4wgj",
  "allow_git_fetch": true,
  "job_info": {
    "name": "job-one",
    "stage": "test",
    "project_id": 1,
    "project_name": "test"
  },
  "git_info": {
    "repo_url": "http://gitlab-ci-token:eX9zJy7UzLv4pWYg4wgj@gitlab.zerg.mine.nu/root/test.git",
    "ref": "master",
    "sha": "0d8be7bb54f72e7645746d4b8d43993f4cf929a7",
    "before_sha": "0000000000000000000000000000000000000000",
    "ref_type": "branch"
  },
  "runner_info": {
    "timeout": 3600,
    "runner_session_url": null
  },
  "variables": [
    {
      "key": "CI_PIPELINE_ID",
      "value": "6",
      "public": true
    },
    {
      "key": "CI_PIPELINE_URL",
      "value": "http://gitlab.zerg.mine.nu/root/test/pipelines/6",
      "public": true
    },
    {
      "key": "CI_JOB_ID",
      "value": "6",
      "public": true
    },
    {
      "key": "CI_JOB_URL",
      "value": "http://gitlab.zerg.mine.nu/root/test/-/jobs/6",
      "public": true
    },
    {
      "key": "CI_JOB_TOKEN",
      "value": "eX9zJy7UzLv4pWYg4wgj",
      "public": false
    },
    {
      "key": "CI_BUILD_ID",
      "value": "6",
      "public": true
    },
    {
      "key": "CI_BUILD_TOKEN",
      "value": "eX9zJy7UzLv4pWYg4wgj",
      "public": false
    },
    {
      "key": "CI_REGISTRY_USER",
      "value": "gitlab-ci-token",
      "public": true
    },
    {
      "key": "CI_REGISTRY_PASSWORD",
      "value": "eX9zJy7UzLv4pWYg4wgj",
      "public": false
    },
    {
      "key": "CI_REPOSITORY_URL",
      "value": "http://gitlab-ci-token:eX9zJy7UzLv4pWYg4wgj@gitlab.zerg.mine.nu/root/test.git",
      "public": false
    },
    {
      "key": "CI",
      "value": "true",
      "public": true
    },
    {
      "key": "GITLAB_CI",
      "value": "true",
      "public": true
    },
    {
      "key": "GITLAB_FEATURES",
      "value": "",
      "public": true
    },
    {
      "key": "CI_SERVER_NAME",
      "value": "GitLab",
      "public": true
    },
    {
      "key": "CI_SERVER_VERSION",
      "value": "11.2.3",
      "public": true
    },
    {
      "key": "CI_SERVER_REVISION",
      "value": "06cbee3",
      "public": true
    },
    {
      "key": "CI_JOB_NAME",
      "value": "job-one",
      "public": true
    },
    {
      "key": "CI_JOB_STAGE",
      "value": "test",
      "public": true
    },
    {
      "key": "CI_COMMIT_SHA",
      "value": "0d8be7bb54f72e7645746d4b8d43993f4cf929a7",
      "public": true
    },
    {
      "key": "CI_COMMIT_BEFORE_SHA",
      "value": "0000000000000000000000000000000000000000",
      "public": true
    },
    {
      "key": "CI_COMMIT_REF_NAME",
      "value": "master",
      "public": true
    },
    {
      "key": "CI_COMMIT_REF_SLUG",
      "value": "master",
      "public": true
    },
    {
      "key": "CI_BUILD_REF",
      "value": "0d8be7bb54f72e7645746d4b8d43993f4cf929a7",
      "public": true
    },
    {
      "key": "CI_BUILD_BEFORE_SHA",
      "value": "0000000000000000000000000000000000000000",
      "public": true
    },
    {
      "key": "CI_BUILD_REF_NAME",
      "value": "master",
      "public": true
    },
    {
      "key": "CI_BUILD_REF_SLUG",
      "value": "master",
      "public": true
    },
    {
      "key": "CI_BUILD_NAME",
      "value": "job-one",
      "public": true
    },
    {
      "key": "CI_BUILD_STAGE",
      "value": "test",
      "public": true
    },
    {
      "key": "CI_PROJECT_ID",
      "value": "1",
      "public": true
    },
    {
      "key": "CI_PROJECT_NAME",
      "value": "test",
      "public": true
    },
    {
      "key": "CI_PROJECT_PATH",
      "value": "root/test",
      "public": true
    },
    {
      "key": "CI_PROJECT_PATH_SLUG",
      "value": "root-test",
      "public": true
    },
    {
      "key": "CI_PROJECT_NAMESPACE",
      "value": "root",
      "public": true
    },
    {
      "key": "CI_PROJECT_URL",
      "value": "http://gitlab.zerg.mine.nu/root/test",
      "public": true
    },
    {
      "key": "CI_PROJECT_VISIBILITY",
      "value": "public",
      "public": true
    },
    {
      "key": "CI_PIPELINE_IID",
      "value": "6",
      "public": true
    },
    {
      "key": "CI_CONFIG_PATH",
      "value": ".gitlab-ci.yml",
      "public": true
    },
    {
      "key": "CI_PIPELINE_SOURCE",
      "value": "web",
      "public": true
    },
    {
      "key": "CI_COMMIT_MESSAGE",
      "value": "Update .gitlab-ci.yml",
      "public": true
    },
    {
      "key": "CI_COMMIT_TITLE",
      "value": "Update .gitlab-ci.yml",
      "public": true
    },
    {
      "key": "CI_COMMIT_DESCRIPTION",
      "value": "",
      "public": true
    },
    {
      "key": "CI_RUNNER_ID",
      "value": "1",
      "public": true
    },
    {
      "key": "CI_RUNNER_DESCRIPTION",
      "value": "carrot",
      "public": true
    },
    {
      "key": "CI_RUNNER_TAGS",
      "value": "carrot-shell",
      "public": true
    },
    {
      "key": "GITLAB_USER_ID",
      "value": "1",
      "public": true
    },
    {
      "key": "GITLAB_USER_EMAIL",
      "value": "admin@example.com",
      "public": true
    },
    {
      "key": "GITLAB_USER_LOGIN",
      "value": "root",
      "public": true
    },
    {
      "key": "GITLAB_USER_NAME",
      "value": "Administrator",
      "public": true
    }
  ],
  "steps": [
    {
      "name": "script",
      "script": [
        "echo before",
        "echo script",
        "date > date.txt"
      ],
      "timeout": 3600,
      "when": "on_success",
      "allow_failure": false
    },
    {
      "name": "after_script",
      "script": [
        "echo after"
      ],
      "timeout": 3600,
      "when": "always",
      "allow_failure": true
    }
  ],
  "image": null,
  "services": [],
  "artifacts": null,
  "cache": [
    null
  ],
  "credentials": [],
  "dependencies": [],
  "features": {
    "trace_sections": true
  }
}
```

## Upload Console Logs

### Request Headers

```
PATCH /api/v4/jobs/6/trace HTTP/1.1
Host: gitlab.zerg.mine.nu
User-Agent: gitlab-runner 11.4.2 (11-4-stable; go1.8.7; linux/amd64)
Content-Length: 1229
Content-Range: 0-1228
Content-Type: text/plain
Job-Token: eX9zJy7UzLv4pWYg4wgj
Accept-Encoding: gzip
```

### Request Body
```
.[0KRunning with gitlab-runner 11.4.2 (cf91d5e1)
.[0;m.[0K  on http-test 4db707c8
.[0;m.[0KUsing Shell executor...
.[0;msection_start:1556126402:prepare_script
.[0KRunning on ea4c543a2f27...
section_end:1556126402:prepare_script
.[0Ksection_start:1556126402:get_sources
.[0K.[32;1mCloning repository....[0;m
Cloning into '/home/gitlab-runner/builds/4db707c8/0/root/test'...
.[32;1mChecking out 0d8be7bb as master....[0;m
.[32;1mSkipping Git submodules setup.[0;m
section_end:1556126402:get_sources
.[0Ksection_start:1556126402:restore_cache
.[0Ksection_end:1556126402:restore_cache
.[0Ksection_start:1556126402:download_artifacts
.[0Ksection_end:1556126402:download_artifacts
.[0Ksection_start:1556126402:build_script
.[0K.[32;1m$ echo before.[0;m
before
.[32;1m$ echo script.[0;m
script
.[32;1m$ date > date.txt.[0;m
section_end:1556126402:build_script
.[0Ksection_start:1556126402:after_script
.[0K.[32;1mRunning after script....[0;m
.[32;1m$ echo after.[0;m
after
section_end:1556126402:after_script
.[0Ksection_start:1556126402:archive_cache
.[0Ksection_end:1556126402:archive_cache
.[0Ksection_start:1556126402:upload_artifacts_on_success
.[0Ksection_end:1556126402:upload_artifacts_on_success
.[0K.[32;1mJob succeeded
.[0;m
```

### Response Headers

```
HTTP/1.1 202 Accepted
Server: nginx
Date: Wed, 24 Apr 2019 17:20:02 GMT
Content-Type: application/json
Content-Length: 8
Cache-Control: no-cache
Job-Status: running
Range: 0-1229
Vary: Origin
X-Content-Type-Options: nosniff
X-Frame-Options: SAMEORIGIN
X-Request-Id: 21a2afbe-f6d7-4f3c-836f-8cbc1f3adcf4
X-Runtime: 0.196916
Set-Cookie: b8a37d986345d6e111e8eab2f149e5ea=406390a5c34dc76f57644756105c36c3; path=/; HttpOnly
```
### Response Body

```
"0-1229"
```

## Job Complete (success)

### Request Headers

```
PUT /api/v4/jobs/6 HTTP/1.1
Host: gitlab.zerg.mine.nu
User-Agent: gitlab-runner 11.4.2 (11-4-stable; go1.8.7; linux/amd64)
Content-Length: 368
Content-Type: application/json
Accept-Encoding: gzip
```

### Request Body
```
{
  "info": {
    "name": "gitlab-runner",
    "version": "11.4.2",
    "revision": "cf91d5e1",
    "platform": "linux",
    "architecture": "amd64",
    "executor": "shell",
    "shell": "bash",
    "features": {
      "variables": true,
      "image": false,
      "services": false,
      "artifacts": true,
      "cache": true,
      "shared": true,
      "upload_multiple_artifacts": true,
      "session": true,
      "terminal": true
    }
  },
  "token": "eX9zJy7UzLv4pWYg4wgj",
  "state": "success"
}
```

### Response Headers
```
HTTP/1.1 200 OK
Server: nginx
Date: Wed, 24 Apr 2019 17:20:02 GMT
Content-Type: application/json
Content-Length: 4
Cache-Control: max-age=0, private, must-revalidate
Etag: W/"b326b5062b2f0e69046810717534cb09"
Vary: Origin
X-Content-Type-Options: nosniff
X-Frame-Options: SAMEORIGIN
X-Request-Id: 9dae26bd-7b65-4d08-a4c5-64035d485f20
X-Runtime: 0.125307
Strict-Transport-Security: max-age=31536000
Set-Cookie: b8a37d986345d6e111e8eab2f149e5ea=406390a5c34dc76f57644756105c36c3; path=/; HttpOnly
Cache-control: private
```

### Response Body

```
true
```