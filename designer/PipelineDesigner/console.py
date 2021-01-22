import argparse
import os
import sys

import yaml

from gitlabemu.configloader import Loader
from . import simulator, analysis
from .output_helpers import hline
from .simulator import SimulatedResources


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", "-c", dest="config", default=".gitlab-ci.yml", type=str,
                        help="Path to the folder containing a pipeline configuration")
    parser.add_argument("--repeat", "-n", dest="pipelines", default=1, metavar="N", type=int,
                        help="Queue up N pipelines (default = 1)")
    parser.add_argument("--profile", dest="profile", type=str, default=None,
                        help="Load a resource profile YAML file")
    parser.add_argument("--target", dest="target", default=1, type=int,
                        help="Attempt to discover how many runners of each type need "
                             "to be added to service this many pipelines without significant slowdowns")
    parser.add_argument("--dump-profile", dest="dump_profile", default=False, action="store_true",
                        help="Overwrite the profile file with auto-detected jobs and runners")

    opts = parser.parse_args()

    profile = opts.profile
    if not profile:
        profile = os.path.join(os.path.dirname(opts.config), simulator.PROFILE_FILENAME)

    if opts.target > 1:
        opts.pipelines = 1

    sim = console_run(opts.config, profile, pipelines=opts.pipelines)
    if opts.target > 1:
        analysis.discover_resource_increase(sim, aim=opts.target)
        return

    if opts.dump_profile:
        print(f"Dumping new profile file..")
        data = {}
        timings = {}
        for job in sim.tasks:
            timings[job.name] = sim.profile.get_cost(job.name)

        runners = []
        for runner in sim.runners:
            runners.append({
                runner.name: {
                    "images": runner.images,
                    "tags": runner.tags,
                    "runners": runner.concurrent
                }
            })
        data["timings"] = timings
        data["runners"] = runners

        with open(profile, "w") as profile_file:
            yaml.safe_dump(data, profile_file)


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
    hline()
    while True:
        try:
            total_time, tasks = sim.run()
            break
        except simulator.NoRunnerError as nre:
            print(f"Warning: No runner defined in the profile with tags: {nre.task.tags}, adding 2")
            sim.add_runner(images=nre.task.image,
                           name=f"missing runner {nre.task.tags}",
                           tags=nre.task.tags, concurrent=2)

    print(f"{ci_file} will take {total_time} minutes to run {pipelines} concurrent pipelines")
    build_order = sorted(tasks, key=lambda t: t.started)
    hline()
    print("The build order: ( :: = time waiting for runner,  ## = time building )")
    hline()
    delays = 0

    labelsize = 20
    for task in build_order:
        label = f"{task.pipeline} {task.name}"
        if len(label) > labelsize:
            labelsize = len(label)

    for task in build_order:
        label = f"{task.pipeline} {task.name}"
        left = " " * (labelsize - len(label))
        delayed = 0
        for cause, cost in task.get_delays().items():
            if cause == "runner":
                delayed += cost
        delay = ":" * delayed
        duration = "=" * task.cost
        indent = " " * (task.started - delayed)
        print(f"{label} {left} |{indent}{delay}{duration}")
    hline()

    print("The runner usage was:")
    hline()
    for runner in sim.runners:
        jobs_done = len(runner.tasks)
        if jobs_done:
            print(f"{runner.name} {jobs_done} jobs")

    analysis.print_highest_costs(sim)

    hline()
    if delays:
        print(f"There were resource related delays during the simulation")
        hline()

    for i in range(pipelines):
        id = i + 1
        duration = sim.pipeline_duration(id)
        print(f"pipeline {id} took {duration} mins")
    hline()

    return sim
