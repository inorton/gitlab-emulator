import argparse
import os
import sys

from gitlabemu.configloader import Loader
from . import simulator
from .simulator import SimulatedResources


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", "-c", dest="config", default=".gitlab-ci.yml", type=str,
                        help="Path to the folder containing a pipeline configuration")
    parser.add_argument("--repeat", "-n", dest="pipelines", default=1, metavar="N", type=int,
                        help="Queue up N pipelines (default = 1)")
    parser.add_argument("--profile", dest="profile", type=str, default=None,
                        help="Load a resource profile YAML file")
    opts = parser.parse_args()

    profile = opts.profile
    if not profile:
        profile = os.path.join(os.path.dirname(opts.config), simulator.PROFILE_FILENAME)
    console_run(opts.config, profile, pipelines=opts.pipelines)


def console_run(ci_file, profile_file, pipelines=1):
    sim = SimulatedResources()
    loader = Loader()
    print(f"Parsing {ci_file}..", flush=True)
    loader.load(ci_file)
    sys.stderr.flush()
    print("CI file parsed.", flush=True)
    if os.path.exists(profile_file):
        print(f"Loading resource profile {profile_file}..")
        with open(profile_file, "rb") as profile_yml:
            sim.load(profile_yml)
    else:
        print(f"Warning, there was no {profile_file} profile file")

    print(f"Loading tasks into simulator..")
    for i in range(pipelines):
        print(f"Enqueue pipeline {i}")
        sim.load_tasks(loader)
    print("Simulator loaded")
    print("-" * 50)
    total_time, tasks = sim.run()
    print(f"{ci_file} will take {total_time} minutes to run {pipelines} concurrent pipelines")
    build_order = sorted(tasks, key=lambda t: t.started)
    print("-" * 50)
    print("The build order: ( :: = time waiting for runner,  ## = time building )")
    print("-" * 50)
    delays = 0
    for task in build_order:
        label = f"{task.pipeline} {task.name}"
        left = " " * (24 - len(label))
        delayed = 0
        for cause, cost in task.get_delays().items():
            if cause == "runner":
                delayed += cost
        delay = ":" * delayed
        duration = "=" * task.cost
        indent = " " * (task.started - delayed)
        print(f"{label} {left} |{indent}{delay}{duration}")
    print("-" * 50)

    print("The runner usage was:")
    print("-" * 50)
    for runner in sim.runners:
        jobs_done = len(runner.tasks)
        print(f"{runner.name} {jobs_done} jobs")

    print("-" * 50)
    if delays:
        print(f"There were resource related delays during the simulation")
        print("-" * 50)

    for i in range(pipelines):
        id = i + 1
        duration = sim.pipeline_duration(id)
        print(f"pipeline {id} took {duration} mins")
    print("-" * 50)

