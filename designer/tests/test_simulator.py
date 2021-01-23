import os
from gitlabemu.configloader import Loader
from PipelineDesigner import simulator

HERE = os.path.abspath(os.path.dirname(__file__))
PIPELINES = os.path.join(os.path.dirname(HERE), "pipelines")


def test_simulate_basic_project():
    sim = simulator.SimulatedResources()
    folder = os.path.join(PIPELINES, "basic-project")

    ciconfig = os.path.join(folder, ".gitlab-ci.yml")
    simconfig = os.path.join(folder, ".gitlab-emulator-profile.yml")

    with open(simconfig, "rb") as yamlsim:
        sim.load(yamlsim)

    loader = Loader()
    loader.load(ciconfig)

    sim.load_tasks(loader)

    timed, tasks = sim.run()

