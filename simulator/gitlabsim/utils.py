"""
General utilities
"""


class RunnerTagCombo(object):
    def __init__(self, tags):
        self.tags = set(tags)

    def __eq__(self, other):
        return self.tags == other.tags

    def __hash__(self):
        x = 0
        for tag in self.tags:
            x += hash(tag)
        return x

    def __str__(self):
        return "({})".format(",".join(self.tags))

    def __repr__(self):
        return str(self)


def unique_runner_profiles(runners):
    """
    Given a list of all runner tag combinations, return a unique set of them
    :param runners:
    :return:
    """
    unique = set()
    for item in runners:
        combo = RunnerTagCombo(item)
        unique.add(combo)
    return unique


def runners_template(runners):
    """
    Generate a runner configuration template
    :param runners:
    :return:
    """
    unique = unique_runner_profiles(runners)
    data = {
        "runners": []
    }
    count = 0
    for runner in unique:
        untagged = "~untagged" in runner.tags
        image = "~image" in runner.tags
        tags = [tag for tag in runner.tags if not tag.startswith("~")]
        data["runners"].append({
            "name": f"generated-{count}",
            "image": image,
            "run-untagged": untagged,
            "tags": tags,
            "concurrent": 1,
        })

        count += 1
    return data


def profile_template(pipeline, default_time=5):
    """
    Given a pipeline, produce a profile template for all jobs
    :param pipeline:
    :param default_time: the number of minutes for each job
    :return:
    """
    data = {"jobs": []}

    for job in pipeline.jobs:
        data["jobs"].append({
            "name": job.name,
            "time": default_time,
        })
    return data
