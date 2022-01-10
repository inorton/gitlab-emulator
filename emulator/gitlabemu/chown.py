#!/usr/bin/python3
import os
import time
import argparse
import subprocess

parser = argparse.ArgumentParser(description="Change all files in the current working directory to be owned by the given UID/GID")
parser.add_argument("UID", type=int, help="UID to set")
parser.add_argument("GID", type=int, help="GID to set")


def run():
    opts = parser.parse_args()
    # run find and get it to do all the heavy work
    started = time.time()
    # find files here not owned by the given user and group
    cmdline = ["find", ".", "!", "-user", str(opts.UID), "-a", "!", "-group", str(opts.GID)]
    # and chown them
    cmdline.extend(["-exec", "chown", f"{str(opts.UID)}.{str(opts.GID)}", '{}', ';'])
    print(f"Restoring ownership of {os.getcwd()} to {str(opts.UID)}.{str(opts.GID)}..")
    subprocess.check_call(cmdline, shell=False)
    ended = time.time()
    print(f"Ownerships restored ({int(ended - started)} sec).")


if __name__ == "__main__":
    run()
