"""
Various useful common funcs
"""
import sys
import platform
import subprocess


def communicate(process, stdout=sys.stdout, script=None, throw=False):
    """
    Write output incrementally to stdout
    :param process: a POpen child process
    :type Popen
    :param stdout: a file-like object to write to
    :param script: a script (ie, bytes) to stream to stdin
    :param throw: raise an exception if the process exits non-zero
    :return:
    """
    windows = platform.system() == "Windows"

    if script is not None:
        process.stdin.write(script)
        process.stdin.flush()
        process.stdin.close()

    while process.poll() is None:
        try:
            data = process.stdout.readline()
        except ValueError:
            pass

        if data:
            stdout.write(data.decode())

    # child has exited now, get any last output if there is any
    if not process.stdout.closed:
        stdout.write(process.stdout.read().decode())

    if hasattr(stdout, "flush"):
        stdout.flush()

    if throw:
        if process.returncode != 0:
            args = []
            if hasattr(process, "args"):
                args = process.args
            raise subprocess.CalledProcessError(process.returncode, cmd=args)
