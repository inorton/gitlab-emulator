"""
Various useful common funcs
"""
import sys


def communicate(process, stdout=sys.stdout, script=None):
    """
    Write output incrementally to stdoute
    :param process: a POpen child process
    :param stdout: a file descriptor
    :param script: a script (ie, bytes) to stream to stdin
    :return:
    """
    if script is not None:
        process.stdin.write(script)
        process.stdin.flush()
        process.stdin.close()

    while not process.poll():
        data = process.stdout.read(100)
        if data:
            stdout.write(data.decode())
            stdout.flush()
        else:
            process.stdout.close()
            process.wait()
