"""Get/Record basic statistics for jobs run on this machine"""
try:
    import taskstats
except ImportError:
    taskstats = None


def get_duration(jobname: str) -> int:
    """Get the expected duration required for the named job"""
    if taskstats is not None:
        timing = taskstats.get_task_timing(jobname)
        return int(timing.mean())
    return 0


def put_duration(jobname: str, seconds: int) -> None:
    """Record how many seconds we took to run this job here"""
    if taskstats is not None:
        taskstats.record_task_timing(jobname, seconds)
