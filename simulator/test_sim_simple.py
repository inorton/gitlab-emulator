from gitlabsim import sim


def test_simple_tick():
    simulator = sim.Simulation()
    server = sim.Server()

    runner = sim.SimRunner(name="runner1", images=True, concurrent=1)
    server.add_runner(runner)

    simulator.server = server

    pipeline = sim.Pipeline()

    job1 = sim.SimJob(name="build", stage="build", image="ubuntu", duration=5)
    job2 = sim.SimJob(name="test", stage="test", image="ubuntu", duration=5, depends=["build"])
    job3 = sim.SimJob(name="scan", stage="test", image="ubuntu", duration=3, depends=["build"])
    job4 = sim.SimJob(name="release", stage="release", image="ubuntu", duration=6, depends=["test", "build"])

    pipeline.add_job(job1)
    pipeline.add_job(job2)
    pipeline.add_job(job3)
    pipeline.add_job(job4)

    server.add_pipeline(pipeline)

    # run the build job

    timespan = simulator.tick()

    assert timespan == 5

    assert len(simulator.server.finished_jobs) == 1
    assert list(simulator.server.finished_jobs)[0].name == "build"

    # run one of the two jobs that depends on build, there should be one ready job left after the tick

    timespan = simulator.tick()
    assert runner.run_count == 2
    assert timespan >= 3
    assert job2.done or job3.done
    assert len(server.ready_jobs) == 1

    # run another
    timespan = simulator.tick()
    assert timespan

    assert runner.run_count == 3

    # run the last job
    timespan = simulator.tick()
    assert timespan
    assert runner.run_count == 4

    # all should be done now
    assert job1.done and job2.done and job3.done and job4.done
    assert simulator.time == 19
    assert server.time == 19
    assert not server.ready_jobs
    assert not server.running_jobs

    timespan = simulator.tick()
    # next tick does nothing
    assert not timespan
    assert simulator.time == 19
    assert server.time == 19
