"""
Simulate pipelines
"""
import os
import sys
import uuid
import yaml
from gitlabemu.configloader import Loader


class NoRunnerError(Exception):
    def __init__(self, message):
        super(NoRunnerError, self).__init__(message)


class Delay(object):
    def __init__(self, cause, cost):
        self.cause = cause
        self.cost = cost

    def __str__(self):
        if self.cost == 0:
            return ""
        return f"{self.cause} {self.cost}"


class SimulatedTask(object):
    def __init__(self, name, image, ticks, needs, tags, pipeline):
        self.name = name
        self.image = image
        self.cost = ticks
        self.remaining = ticks
        self.needs = needs
        self.tags = tags
        self.pipeline = pipeline
        self.started = 0
        self.delays = []

    def get_delays(self):
        reasons = {}
        for item in self.delays:
            if item.cause not in reasons:
                reasons[item.cause] = 0
            if item.cost > 0:
                reasons[item.cause] += item.cost

        for need in self.needs:
            needed_delays = need.get_delays()
            for reason, cost in needed_delays.items():
                source = f"inherited {need.name}"
                if source not in reasons:
                    reasons[source] = 0
                reasons[source] += cost

        return reasons

    def add_delay(self, reason, cost):
        self.delays.append(Delay(reason, cost))

    def ready(self):
        for task in self.needs:
            if not task.ready():
                return False
        return True

    def reset(self):
        self.remaining = self.cost
        self.delays.clear()
        self.started = 0

    def __str__(self):
        if self.remaining == 0:
            progress = "done"
        else:
            progress = int(100.0 * (self.cost - self.remaining) / self.cost)
            progress = f"{progress}%"
        return f"{self.pipeline} {self.name} {progress}"


class SimulatedRunner(object):
    def __init__(self, images=True, name="runner", tags=[], concurrent=1):
        self.id = str(uuid.uuid4())
        self.name = name
        self.tags = tags
        self.images = images
        self.concurrent = concurrent
        self.time = 0
        self.tasks = []

    def __str__(self):
        running = len(self.active_tasks())
        return f"runner {self.name} concurrent={self.concurrent}, running={running}"

    def reset(self):
        self.tasks.clear()
        self.time = 0

    def active_tasks(self):
        return [task for task in self.tasks if task.started and task.remaining > 0]

    def can_execute(self, task):
        running = self.active_tasks()
        if self.concurrent > len(running):
            if task.image != self.images:
                return False
            for tag in task.tags:
                if tag not in self.tags:
                    return False
            return True
        return False

    def tick(self):
        for task in self.tasks:
            if task.remaining > 0:
                task.remaining -= 1

    def execute(self, task, now):
        task.started = now
        self.tasks.append(task)


class CostProfile(object):
    """
    Build Times for jobs
    """

    def __init__(self, jobs={}):
        self.jobs = jobs

    def has_cost(self, jobname):
        return jobname in self.jobs

    def get_cost(self, jobname):
        return self.jobs.get(jobname, 1)


class SimulatedResources(object):
    def __init__(self):
        self.runners = []
        self.tasks = []
        self.pipelines = []
        self.profile = CostProfile()

    def load(self, yamlfile):
        """
        Load the environment sim from a yaml file
        :param yamlfile:
        :return:
        """
        data = yaml.safe_load(yamlfile)
        self.profile.jobs = data.get("timings", {})
        runners = data.get("runners", [])
        for runner in runners:
            name = list(runner.keys())[0]
            content = runner[name]
            self.add_runner(
                images=content.get("images", False),
                name=name,
                tags=content.get("tags", []),
                concurrent=content.get("runners", 1)
            )

    def add_runner(self, images=True, name=None, tags=[], concurrent=1):
        """
        Add a runner to the build resources
        :param images:
        :param name:
        :param tags:
        :param concurrent:
        :return:
        """
        self.runners.append(SimulatedRunner(images=images, name=name, tags=tags, concurrent=concurrent))

    def add_task(self, name, image=True, cost=1, needs=[], tags=[], pipeline=0):
        """
        Add a task
        :param name:
        :param image:
        :param cost:
        :param needs:
        :param pipeline:
        :return:
        """
        task = SimulatedTask(name, image=image, ticks=cost, needs=needs, tags=tags, pipeline=pipeline)
        self.tasks.append(task)
        return task

    def load_tasks(self, loader):
        """
        Populat the task list from the emulator loader
        :param loader:
        :return:
        """
        pipeline = 1 + len(self.pipelines)
        jobs = dict()
        for jobname in loader.get_jobs():
            if jobname.startswith("."):
                continue
            job = loader.get_job(jobname)
            jobs[jobname] = job
        tasks = {}

        while len(jobs) > len(tasks):
            for jobname, job in jobs.items():
                need_jobs = job.get("needs", [])
                need_tasks = []
                for need in need_jobs:
                    if need not in tasks:
                        continue
                    need_tasks.append(tasks[need])
                added = self.add_task(jobname,
                                      image=loader.get_docker_image(jobname) is not None,
                                      cost=self.profile.get_cost(jobname),
                                      needs=need_tasks,
                                      tags=job.get("tags", []),
                                      pipeline=pipeline
                                      )
                tasks[jobname] = added

    def _pipeline(self, id):
        return (task for task in self.tasks if task.pipeline == id)

    def _task_needs(self, task):
        return (item for item in self._pipeline(task.pipeline) if item.name in task.needs and item.remaining > 0)

    def run(self):
        for runner in self.runners:
            runner.reset()
        for task in self.tasks:
            task.reset()

        # check all tags exist
        for task in self.tasks:
            can_execute = 0
            for runner in self.runners:
                if runner.can_execute(task):
                    can_execute += 1

            if can_execute == 0:
                raise NoRunnerError(str(task.tags))

        ticks = 0
        while True:
            for task in self.tasks:
                started = False
                if task.started:
                    continue
                # find out if everything this task needs is done
                if not task.ready():
                    continue
                for runner in self.runners:
                    if runner.can_execute(task):
                        runner.execute(task, ticks)
                        started = True
                        break
                if not started:
                    task.add_delay("runner", 1)
            ticks += 1

            for runner in self.runners:
                runner.tick()
            remaining = 0
            for task in self.tasks:
                if task.remaining > 0:
                    remaining += 1
            if remaining == 0:
                break

        return ticks, self.tasks


def console_run(ci_file, profile_file):
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
    sim.load_tasks(loader)
    print("Simulator loaded")
    print("-" * 50)
    total_time, tasks = sim.run()
    print(f"Pipeline {ci_file} will take {total_time} minutes")
    build_order = sorted(tasks, key=lambda t: t.started)
    print("-" * 50)
    print("The build order was:")
    print("-" * 50)
    delays = 0
    for task in build_order:
        print(f"{task.name}")
        for cause, cost in task.get_delays().items():
            delays += cost
    print("-" * 50)

    print("The runner usage was:")
    print("-" * 50)
    for runner in sim.runners:
        jobs_done = len(runner.tasks)
        print(f"{runner.name} {jobs_done} jobs")

    print("-" * 50)
    if delays:
        print(f"There were delays totalling {delays} mins over the course of the pipeline")
        print("-" * 50)
        for task in build_order:
            print(f"{task.name}:")
            task_delays = task.get_delays()
            for cause in sorted(task_delays.keys()):
                delay = task_delays[cause]
                print(f"   {delay} mins {cause}")
        print("-" * 50)