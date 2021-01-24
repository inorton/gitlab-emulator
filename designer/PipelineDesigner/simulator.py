"""
Simulate pipelines
"""
import uuid
import yaml

PROFILE_FILENAME = ".gitlab-emulator-profile.yml"


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
    def __init__(self, name, image, ticks, needs, tags, stage, pipeline):
        self.name = name
        self.stage = stage
        self.image = image
        self.cost = ticks
        self.remaining = ticks
        self.needs = needs
        self.tags = tags
        self.pipeline = pipeline
        self.started = 0
        self.delays = []

    def ended(self):
        return self.cost + self.started

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
        return f"[{self.pipeline}] {self.name} {progress}"


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
        tasks = [task for task in self.tasks if task.remaining > 0]
        return tasks

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
        self.loader = None

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

    def add_task(self, name, image=True, cost=1, needs=[], tags=[], stage="test", pipeline=0):
        """
        Add a task
        :param stage:
        :param tags:
        :param name:
        :param image:
        :param cost:
        :param needs:
        :param pipeline:
        :return:
        """
        task = SimulatedTask(name, image=image, ticks=cost, needs=needs, tags=tags, stage=stage, pipeline=pipeline)
        self.tasks.append(task)
        return task

    def load_tasks(self, loader):
        """
        Populat the task list from the emulator loader
        :param loader:
        :return:
        """
        self.loader = loader
        pipe = set()
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
                                      stage=job.get("stage", "test"),
                                      pipeline=pipeline
                                      )
                tasks[jobname] = added
                pipe.add(added)
        self.pipelines.append(pipe)

    def pipeline_duration(self, pipeline):
        tasks = self._pipeline(pipeline)
        ended = 0
        for task in tasks:
            if task.ended() > ended:
                ended = task.ended()
        return ended

    def _pipeline(self, id):
        return (task for task in self.tasks if task.pipeline == id)

    def _task_needs(self, task):
        return (item for item in self._pipeline(task.pipeline) if item.name in task.needs and item.remaining > 0)

    def _stage_needs(self, task):
        """
        Get the tasks in earlier stages
        :param task:
        :return:
        """
        stage = task.stage
        need_stages = []
        stages = self.loader.get_stages()
        for item in stages:
            if item == stage:
                break
            need_stages.append(item)

        earlier_stage_tasks = (task for task in self._pipeline(task.pipeline)
                               if task.stage in need_stages and task.remaining > 0)
        return list(earlier_stage_tasks)

    def run(self):
        started_tasks = set()
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
                if task in started_tasks:
                    continue
                # find out if everything this task needs is done
                if not task.ready():
                    continue

                # if the task has no needs, it must wait for earlier stages to finish
                if not task.needs:
                    stage_needs = self._stage_needs(task)
                    if len(stage_needs):
                        # waiting for an earlier stage
                        task.add_delay("stage", 1)
                        continue

                for runner in self.runners:
                    if runner.can_execute(task):
                        runner.execute(task, ticks)
                        started = True
                        started_tasks.add(task)
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


