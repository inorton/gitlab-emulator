"""
Data classes for gitlab simulations
"""

from gitlabemu import configloader

RUNNING = "running"   # a job being executed
PENDING = "pending"   # a job waiting for another to finish
FINISHED = "finished"


class SimRunner(object):
    """
    A runner capable of running SimJobs
    """
    def __init__(self, *, name=None, images=False, tags=None, concurrent=1):
        if tags is None:
            tags = set()
        self.tags = set(tags)
        self.concurrent = concurrent
        self.images = images
        self.name = name
        self.jobs = []
        self.run_count = 0

    def reset(self):
        self.jobs.clear()
        self.run_count = 0

    def tick(self):
        for job in list(self.jobs):
            if job.finished:
                self.jobs.remove(job)

    def match(self, job):
        """
        Return True if we can run this job
        :param job:
        :return:
        """
        if len(self.jobs) < self.concurrent:
            tags = set(job.tags)
            match_tags = tags.intersection(self.tags) == tags
            match_image = self.images and job.image
            return match_image and match_tags
        return False

    def start(self, job):
        """
        Try to start a job, if this runner can, return True and occupy this runner
        :param job:
        :return:
        """
        if self.match(job):
            self.jobs.append(job)
            self.run_count += 1
            return True
        return False


class SimJob(object):
    """
    Represent a job to be run
    """
    def __init__(self, *, name=None, stage=None, tags=None, image=None, depends=None, duration=10):
        if not tags:
            tags = set()
        if not depends:
            depends = []

        self.runner = None
        self.done = False
        self.stage = stage
        self.name = name
        self.tags = tags
        self.image = image
        self.depends = depends
        self.pipeline = None

        self.duration = duration
        self.remaining = duration
        self.started = None
        self.finished = None

    def __str__(self):
        return f"{self.stage} - {self.name}"

    def __repr__(self):
        return str(self)

    def tick(self, time):
        if self.remaining:
            assert time <= self.remaining
            self.remaining -= time
            if self.remaining == 0:
                self.finished = self.started + self.duration
                self.done = True

    def state(self):
        if self.started is not None:
            if self.remaining == 0:
                return RUNNING
            return FINISHED
        return PENDING

    def clone(self):
        """
        Duplicate this job
        :return:
        """
        job = SimJob(name=self.name,
                     stage=self.stage,
                     tags=self.tags,
                     image=self.image,
                     depends=list(self.depends),
                     duration=self.duration)
        return job

    def get_needed(self):
        """
        Get the jobs this job needs to wait for
        :return:
        """
        assert self.pipeline
        assert self.pipeline.jobs

        depends = (dep for dep in self.pipeline.jobs if dep.name in self.depends)
        awaiting = [x for x in depends if not x.done]
        return awaiting

    def ready(self):
        """
        Return True if this job can run
        :return:
        """
        if not self.done:
            is_ready = self.started is None and len(self.get_needed()) == 0
            return is_ready
        return False


class Pipeline(object):
    """
    Represent a pipeline to be run
    """
    def __init__(self):
        self.jobs = []
        self.submitted = 0
        self.finished = 0
        self.server = None

    def clone(self):
        """
        Duplicate the pipeline
        :return:
        """
        pipe = Pipeline()
        for job in self.jobs():
            pipe.jobs.append(job.clone())
            job.pipeline = pipe
        return pipe

    def add_job(self, job):
        """
        Add a job to this pipeline
        :param job:
        :return:
        """
        job.pipeline = self
        self.jobs.append(job)

    def load(self, configfile):
        """
        Read a pipeline starting at the given gitlab file
        :param configfile:
        :return:
        """
        loader = configloader.Loader()
        loader.load(configfile)

        for job in loader.get_jobs():
            item = SimJob(name=job.name,
                          stage=job.stage,
                          tags=job.tags,
                          depends=job.dependencies,
                          image=configloader.job_docker_image(loader.config, job.name))
            self.add_job(item)


class Server(object):
    """
    Represent the server
    """
    def __init__(self):
        self.time = 0
        self.runners = []
        self.pipelines = []

        self.jobs = []
        self.ready_jobs = set()
        self.running_jobs = set()
        self.finished_jobs = set()

    def add_runner(self, runner):
        """
        Add a runner
        :param runner:
        :return:
        """
        self.runners.append(runner)

    def add_pipeline(self, pipeline):
        """
        Add a pipeline
        :param pipeline:
        :return:
        """
        self.pipelines.append(pipeline)
        for job in pipeline.jobs:
            self.jobs.append(job)

    def tick(self):
        """
        Start all the jobs that can be started right now. Return the length of the tick
        """
        tick_start = self.time
        fastest = None
        for job in self.jobs:
            if job not in self.ready_jobs:
                if job.ready():
                    self.ready_jobs.add(job)

        for job in list(self.ready_jobs):
            if job not in self.running_jobs:
                for runner in self.runners:
                    if runner.start(job):
                        self.ready_jobs.remove(job)
                        self.running_jobs.add(job)
                        job.started = self.time
                        break

        # find the first running job to finish
        for job in self.running_jobs:
            if not fastest:
                fastest = job
            else:
                if fastest.remaining > job.remaining:
                    fastest = job

        if fastest:
            timeshift = fastest.remaining
            # move time forward on all jobs
            for job in self.running_jobs:
                job.tick(timeshift)
            self.time += timeshift

        # update job status
        for job in list(self.running_jobs):
            if job.finished:
                self.running_jobs.remove(job)
                self.finished_jobs.add(job)

        # update runner status
        for runner in self.runners:
            runner.tick()

        return self.time - tick_start


class Simulation(object):
    def __init__(self):
        self.server = Server()
        self.time = 0

    def add_pipeline(self, pipeline):
        """
        Enqueue a pipeline to run
        :param pipeline:
        :return:
        """
        self.server.add_pipeline(pipeline)

    def tick(self):
        """
        Process the next stage in the simulation
        :return:
        """

        timeshift = self.server.tick()
        self.time += timeshift
        return timeshift

    def run(self):
        while self.tick():
            pass
        return self.time