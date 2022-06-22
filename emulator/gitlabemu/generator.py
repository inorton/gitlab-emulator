"""Generate sub-pipelines"""
import os.path
import subprocess
from typing import List, Dict, Optional
from contextlib import contextmanager
from .configloader import Loader, StringableOrderedDict
from .helpers import git_top_level, git_commit_sha, git_uncommitted_changes, git_current_branch


def generate_pipeline_yaml(loader: Loader, *goals: List[str]) -> dict:
    """"""
    generated = StringableOrderedDict()
    stages = loader.config.get("stages", [])
    needed = set(goals)

    while len(needed):
        for name in list(needed):
            needed.remove(name)
            job = loader.get_job(name)
            # strip out extends and rules
            for remove in ["extends", "when", "only", "rules", "except"]:
                if remove in job:
                    del job[remove]
            stage = job.get("stage", None)
            if stage:
                if stage not in stages:
                    stages.append(stage)
            generated[name] = job

            needs = job.get("needs", [])
            for item in needs:
                if isinstance(item, str):
                    if item not in generated:
                        # want it
                        needed.add(item)
                elif isinstance(item, dict):
                    need_job = item.get("job", None)
                    if need_job and need_job not in generated:
                        needed.add(need_job)

    if stages:
        generated["stages"] = list(stages)

    return generated


def create_pipeline_branch(repo: str,
                           remote: str,
                           new_branch: str,
                           commit_message: str,
                           files: Dict[str, str],
                           ) -> Optional[str]:
    """"""
    commit = None
    topdir = git_top_level(repo)
    original = git_current_branch(topdir)
    changes = git_uncommitted_changes(topdir)
    if not changes:
        try:
            subprocess.check_call(["git", "-C", topdir, "checkout", "-b", new_branch])
            for filename in files:
                filepath = os.path.join(topdir, filename)
                folder = os.path.dirname(filepath)
                if not os.path.exists(folder):
                    os.makedirs(folder)
                with open(filepath, "w") as fd:
                    fd.write(files[filename])
                subprocess.check_call(["git", "-C", topdir, "add", filepath])

            subprocess.check_call(["git", "-C", topdir, "commit", "-am", commit_message])
            subprocess.check_call(["git", "-C", topdir, "push", "-q", "--set-upstream", remote, new_branch])
            commit = git_commit_sha(topdir)
        finally:
            subprocess.check_call(["git", "-C", topdir, "checkout", "-qf", original])
    return commit
