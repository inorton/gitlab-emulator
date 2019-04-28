"""
Various useful common funcs
"""
import sys
import subprocess


def communicate(process, stdout=sys.stdout, script=None, throw=False):
    """
    Write output incrementally to stdout
    :param process: a POpen child process
    :type Popen
    :param stdout: a file descriptor
    :param script: a script (ie, bytes) to stream to stdin
    :param throw: raise an exception if the process exits non-zero
    :return:
    """

    if script is not None:
        process.stdin.write(script)
        process.stdin.flush()
        process.stdin.close()

    while True:
        try:
            data = process.stdout.read(50)
        except ValueError:
            pass
        if data:
            stdout.write(data.decode())
            stdout.flush()
        else:
            process.stdout.close()
            process.wait()
        if process.poll() is not None:
            break

    if throw:
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd=process.args)
