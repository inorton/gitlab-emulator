"""
Main entrypoint tool for the pipeline simulator
"""
import argparse
from . import simulator


parser = argparse.ArgumentParser()
parser.add_argument("--config", dest="config", default=".gitlab-ci.yml", type=str,
                    help="Path to the folder containing a pipeline configuration")
parser.add_argument("--profile", dest="profile", type=str, default=".gitlab-emulator-profile.yml",
                    help="Load a resource profile YAML file")

if __name__ == "__main__":
    opts = parser.parse_args()
    simulator.console_run(opts.config, opts.profile)
