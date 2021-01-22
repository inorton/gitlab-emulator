"""
Tools for analysis for a build pipeline
"""

from .output_helpers import hline
from .simulator import SimulatedResources, SimulatedTask

from criticalpath import Node


def get_task_costs(sim: SimulatedResources):
    """
    Return a sorted list of cloned tasks, ordered with the most expensive task first
    :param sim:
    :return:
    """
    costly = sorted(sim.tasks, key=lambda x: x.runner_occupancy * x.cost, reverse=True)
    return [x.clone() for x in costly]


def get_runner_costs(sim: SimulatedResources):
    usage = {}
    runners = {}
    tasks = get_task_costs(sim)
    for task in tasks:
        runner_name = task.runner.name
        runners[task.runner.name] = task.runner
        if runner_name not in usage:
            usage[runner_name] = 0
        usage[runner_name] += task.runner_occupancy

    costly = []
    for name in usage:
        costly.append({
            "name": name,
            "runner": runners[name],
            "usage": usage[name]
        })

    return sorted(costly, key=lambda x: x["usage"], reverse=True)


def print_highest_costs(sim: SimulatedResources):
    hline()
    print("Highest job costs for runners with low resource were:")
    hline()
    costly = get_task_costs(sim)
    highest_costs = costly[:12]
    for task in highest_costs:
        runner_pct: int = int(task.runner_occupancy * 100)
        print(f"{task.name:32} used {runner_pct:-3}% of {task.runner.name:32} capacity for {task.cost:3} mins")
    return costly


def increase_pipelines(sim, tasks, pipeline):
    for task in tasks:
        sim.add_task(task.name, task.image, task.cost, task.needs, task.tags, task.stage, pipeline=pipeline)


def increase_runner(sim: SimulatedResources, runner: SimulatedTask, minimum=1):
    assert minimum > 0
    increase = int(max(1.1 * runner.concurrent, minimum + runner.concurrent))
    additional = increase - runner.concurrent
    runner.concurrent = increase
    new_duration, _ = sim.run()
    return new_duration, additional


def discover_resource_increase(sim: SimulatedResources, aim=1):
    """
    Given a configured and complete simulation, suggest where additional resources could make the best difference
    :param sim:
    :param aim: aim for us to be able to do this many pipelines concurrently in an acceptable timeframe
    :return:
    """
    # capture the costs for 1 pipeline
    single_costs = get_task_costs(sim)
    single_duration = sim.duration()

    cpath = critical_path(sim)

    print("The critical path of the pipeline is:")
    for item in cpath:
        print(f" - {item}")

    hline()

    # see how many pipelines we can run concurrently before the slowest is more than 30% longer (or 40 mins, whichever is most)
    # then use that as the basis for improvement
    pipelines = 1
    max_acceptable_duration = max(1.3 * single_duration, 40 + single_duration)
    duration = single_duration

    while True:
        increase_pipelines(sim, single_costs, (1 + pipelines))

        previous_duration = duration
        duration, tasks = sim.run()
        difference = duration - single_duration
        print(f"{pipelines + 1:-3} completes in {duration} mins ({difference} min slowdown)")
        if duration > max_acceptable_duration:
            break
        pipelines += 1

    slowdown = previous_duration - single_duration
    current_pipelines = pipelines
    current_duration = previous_duration
    hline()
    print(f"We can run {pipelines} concurrent pipelines with a {slowdown} min maximum slowdown")
    hline()

    # at this point, the simulator is populated with one more pipeline than was acceptable for a total wait time
    new_pipelines = 1 + pipelines

    added = {}
    for runner in sim.runners:
        added[runner.name] = 0

    # add our aimed pipelines
    while pipelines < aim - 1:
        increase_pipelines(sim, single_costs, (1 + pipelines))
        new_pipelines += 1
        pipelines += 1

    last_duration, tasks = sim.run()
    new_duration = 0
    hline(letter="=")
    print(f"Without additional resources {aim} pipelines will take {last_duration} mins")
    hline()

    print(f"Aim is to build {aim} in less than {max_acceptable_duration} mins")

    passes = 1
    while True:
        hline()
        print(f"Simulated session {passes} ..")
        passes += 1
        # start adding 4 runners on the early passes
        eary_additional_runners = max(1, 4 - passes)
        c_runners, s_runners, rb_tasks = get_contended_runners(cpath, sim)

        helped = False
        # try adding one runner type at a time, this generally has the best effect on throughput

        for runner in s_runners:
            while True:
                # keep adding instances fo this runner until it has no effect,
                # bump the runner capacity by 10% (or 1), and retest
                new_duration, additional = increase_runner(sim, runner, minimum=eary_additional_runners)
                difference = last_duration - new_duration
                if new_duration < last_duration:
                    added[runner.name] += additional
                    last_duration = new_duration
                    print(
                        f"... {additional} extra {runner.name} saved {difference} mins ({last_duration} mins)")
                    helped = True
                else:
                    runner.concurrent -= additional
                    break

        # we are in the state where only adding 1 type of runner doesn't help (perhaps a job is stuck depending
        # on two others)
        if not helped:
            hline("@")
            print("can't find an improvement using single runner strategy, trying last tasks")
            # which tasks ended last?
            last_tasks = sorted(sim.tasks, reverse=True, key=lambda x: x.ended())
            end = last_tasks[0].ended()
            stuck_tasks = [x for x in last_tasks if x.ended() == end]
            for task in stuck_tasks:
                print(f"Scaling runner {task.runner.name} for stuck task {task.name}")
                new_duration, additional = increase_runner(sim, task.runner, minimum=1)
                difference = last_duration - new_duration
                print(f"... {additional} extra {runner.name} executors saved {difference} mins ({last_duration} mins)")
                added[task.runner.name] += additional
                last_duration = new_duration

        if new_duration < max_acceptable_duration:
            # we did it, we are fast enough!
            break

    hline()
    print(f"Adding the following extra resources:-")
    for runner in added:
        if added[runner]:
            print(f"{added[runner]} x {runner}")
    print()
    print(f"We can run {new_pipelines} pipelines concurrently in {new_duration} mins")
    print(f"Previously {current_pipelines} pipelines concurrently in {current_duration} mins")

    old_throughput = 60 * current_pipelines / current_duration
    new_throughput = 60 * new_pipelines / new_duration
    throughput_bonus = 100 * (new_throughput - old_throughput) / old_throughput

    print(
        f"{new_throughput:.2f} pipelines / hr increase from {old_throughput:.2f} pipelines / hr ({throughput_bonus:.1f}% increase)")
    hline()


def get_contended_runners(cpath, sim):
    stressed_runners = set()
    delayed_tasks = (x for x in sim.tasks if x.delays)
    delayed_tasks_count = 0
    runner_delayed_tasks = []
    critical_runners = set()
    for task in delayed_tasks:
        delayed_tasks_count += 1
        delays = task.get_delays()
        for item in delays:
            if "runner" in item:
                if task.runner not in stressed_runners:
                    stressed_runners.add(task.runner)
                    runner_delayed_tasks.append(task)
            if task.name in cpath:
                if task.runner not in critical_runners:
                    critical_runners.add(task.runner)
    return critical_runners, stressed_runners, runner_delayed_tasks


def critical_path(sim):
    """
    For a single pipeline in the loaded sim, work out the critical path
    :param sim:
    :return:
    """
    p = Node("start")
    e = Node("end", duration=0)
    p.add(e)
    nodes = {}
    seen = set()

    tasks = {}

    for task in sim.tasks:
        if task.name not in nodes:
            tasks[task.name] = task
            t = p.add(Node(task.name, duration=task.cost, lag=0))
            nodes[task.name] = t
            t.link(e)

    for task in sim.tasks:
        if task.name not in seen:
            seen.add(task.name)
            tasknode = nodes[task.name]
            for need in task.needs:
                need_node = nodes[need.name]
                need_node.link(tasknode)

    path = p.get_critical_path()
    return [x.name for x in path if x.name in tasks]
