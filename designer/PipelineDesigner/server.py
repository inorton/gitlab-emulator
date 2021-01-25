"""
Flask server for the pipeline UI
"""
import os

from flask import Flask
from flask import jsonify

from gitlabemu.configloader import Loader, DEFAULT_CI_FILE
from .simulator import SimulatedResources, PROFILE_FILENAME

app = Flask("Pipeline Designer")


@app.route("/api/pipeline")
def pipeline():
    sim = SimulatedResources()
    loader = Loader()
    loader.load(DEFAULT_CI_FILE)
    if os.path.exists(PROFILE_FILENAME):
        with open(PROFILE_FILENAME, "r") as prof:
            sim.load(prof)

    sim.load_tasks(loader)

    resp = {
        "filename": os.path.abspath(DEFAULT_CI_FILE),
        "variables": {},
        "stages": [],
        "jobs": [],
    }
    variables = loader.config.get("variables", {})
    for varname in variables:
        resp["variables"][varname] = variables[varname]

    for stage in loader.get_stages():
        resp["stages"].append(stage)

    for jobname in sorted(loader.get_jobs()):
        if jobname.startswith("."):
            continue
        job = loader.get_job(jobname)
        resp["jobs"].append({
            "name": jobname,
            "stage": job.get("stage"),
            "needs": job.get("needs", []),
            "filename": loader.get_job_filename(jobname),
            "extends": loader.get_job_bases(jobname),
        })

    return jsonify(resp)


if __name__ == "__main__":
    app.run()
