"""
Simulate pipelines
"""
import uuid
import yaml
from gitlabemu.configloader import Loader


class NoRunnerError(Exception):
    def __init__(self, message):
        super(NoRunnerError, self).__init__(message)


class SimulatedTask(object):
    def __init__(self, name, image, ticks, needs, tags):
        self.name = name
        self.image = image
        self.cost = ticks
        self.remaining = ticks
        self.needs = needs
        self.tags = tags
        self.started = 0

    def reset(self):
        self.remaining = self.cost
        self.started = 0


class SimulatedRunner(object):
    def __init__(self, images=True, name="runner", tags=[], concurrent=1):
        self.id = str(uuid.uuid4())
        self.name = name
        self.tags = tags
        self.images = images
        self.concurrent = concurrent
        self.time = 0
        self.tasks = []

    def reset(self):
        self.tasks.clear()
        self.time = 0

    def active_tasks(self):
        return [task for task in self.tasks if task.remaining > 0]

    def can_execute(self, task):
        if self.concurrent > len(self.active_tasks()):
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

    def execute(self, task):
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

    def add_task(self, name, image=True, cost=1, needs=[], tags=[]):
        """
        Add a task
        :param name:
        :param image:
        :param cost:
        :param needs:
        :return:
        """
        task = SimulatedTask(name, image=image, ticks=cost, needs=needs, tags=tags)
        self.tasks.append(task)
        return task

    def load_tasks(self, loader):
        """
        Populat the task list from the emulator loader
        :param loader:
        :return:
        """
        for jobname in loader.get_jobs():
            job = loader.get_job(jobname)
            self.add_task(jobname,
                          image=loader.get_docker_image(jobname) is not None,
                          cost=self.profile.get_cost(jobname),
                          needs=job.get("needs", []),
                          tags=job.get("tags", [])
                          )

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

        remaining_tasks = len(self.tasks)
        ticks = 0
        while remaining_tasks > 0:
            remaining_tasks = 0
            for task in self.tasks:
                if task.remaining > 0:
                    remaining_tasks += 1
                for runner in self.runners:
                    if runner.can_execute(task):
                        task.started = ticks
                        runner.execute(task)
            ticks += 1

            for runner in self.runners:
                runner.tick()

        return ticks, self.tasks

