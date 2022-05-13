import os
import yaml
from gitlabemu import configloader
cfg = configloader.find_ci_config(os.getcwd())
loader = configloader.Loader()
loader.load(cfg)
for jobname in loader.get_jobs():
    print(jobname)
    job = loader.get_job(jobname)
    assert job
    # job is a dictionary of the job image, stage, steps, artifacts etc
