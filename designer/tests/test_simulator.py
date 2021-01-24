import os
from gitlabemu.configloader import Loader
from PipelineDesigner import simulator

HERE = os.path.abspath(os.path.dirname(__file__))
PIPELINES = os.path.join(os.path.dirname(HERE), "pipelines")


def load_project(folder):
    sim = simulator.SimulatedResources()
    ciconfig = os.path.join(folder, ".gitlab-ci.yml")
    simconfig = os.path.join(folder, ".gitlab-emulator-profile.yml")
    if os.path.exists(simconfig):
        with open(simconfig, "rb") as yamlsim:
            sim.load(yamlsim)

    loader = Loader()
    loader.load(ciconfig)
    sim.load_tasks(loader)

    return sim


def task_by_name(tasks, name):
    found = [task for task in tasks if task.name == name]
    assert found
    return found[0]


def test_simulate_basic_project():
    sim = load_project(os.path.join(PIPELINES, "basic-project"))
    timed, tasks = sim.run()
    assert timed == 24
    assert len(tasks) == 6

    windows_tools = task_by_name(tasks, "windows-tools")
    delays = windows_tools.get_delays()
    assert len(delays) == 1
    assert delays["runner"] == 3

    installer = task_by_name(tasks, "installer")
    delays = installer.get_delays()
    assert len(delays) == 2
    assert delays["runner"] == 2
    assert delays["inherited windows-tools"] == 3


def test_simulate_needless():
    sim = load_project(os.path.join(PIPELINES, "needless"))
    timed, tasks = sim.run()
    assert timed == 14
    assert len(tasks) == 4

    test_linux = task_by_name(tasks, "test-linux")
    test_linux_delays = test_linux.get_delays()
    assert len(test_linux_delays) == 1
    assert test_linux_delays["stage"] == 10

    release_linux = task_by_name(tasks, "release-linux")
    release_linux_delays = release_linux.get_delays()
    assert len(release_linux_delays) == 1
    assert release_linux_delays["stage"] == 12




