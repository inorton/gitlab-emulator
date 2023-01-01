"""
See https://gitlab.com/gitlab-org/gitlab-runner/-/blob/main/common/network.go for reference
"""



RESERVED_TOP_KEYS = ["stages",
                     "services",
                     "image",
                     "cache",
                     "before_script",
                     "after_script",
                     "pages",
                     "variables",
                     "include",
                     "workflow",
                     "default",
                     ".gitlab-emulator-workspace"
                     ]

DEFAULT_JOB_KEYS = [
    "after_script",
    "artifacts",
    "before_script",
    "cache",
    "image",
    "interruptible",
    "retry",
    "services",
    "tags",
    "timeout",
]