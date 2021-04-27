import argparse
from .sim import Pipeline


parser = argparse.ArgumentParser()
parser.add_argument("PIPELINE",
                    help="Load and simulate the given pipeline configuration", type=str)
parser.add_argument("--profile", "-p",
                    help="Load a timing profile. Without this all jobs take 12 minutes", type=str)
parser.add_argument("--runners", "-r",
                    help="Load the runners list")
parser.add_argument("--new-profile", dest="newprofile",
                    help="Generate a new profile file from the pipeline", type=str)
parser.add_argument("--new-runners", dest="newrunners",
                    help="Generate a new runners file from the pipeline", type=str)


def run():
    opts = parser.parse_args()

    pipe = Pipeline()
    pipe.load(opts.PIPELINE)

    if opts.newrunners:
        runners = list()
        for job in pipe.jobs:
            runners.append(job.runner_detail())

        print(runners)


if __name__ == "__main__":
    run()
