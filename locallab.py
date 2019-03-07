#!/usr/bin/env python
"""
Run a job from a .gitlab-ci.yml file
"""

import sys

from gitlabemu import configloader, job

yamlfile = sys.argv[1]
jobname = sys.argv[2]
config = configloader.read(yamlfile)

jobitem = configloader.get_job(config, jobname)

jobobj = job.load(config, jobname)

jobobj.run()


