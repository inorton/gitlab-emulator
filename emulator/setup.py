from distutils.core import setup

VERSION = "0.8.11"

setup(
    name="gitlab-emulator",
    version=VERSION,
    description="Run a subset of .gitlab-ci.yml jobs locally",
    author="Ian Norton",
    author_email="inorton@gmail.com",
    url="https://gitlab.com/cunity/gitlab-emulator",
    packages=[
        "gitlabemu",
        "gitlabemu.gitlab",
    ],
    scripts=["locallab.py"],
    install_requires=[
        "pyyaml>=3.13",
        "docker>=5.0.2; platform_system=='Linux'",
        "docker>=5.0.2; platform_system=='Darwin'",
        "docker>=5.0.2; platform_system=='Windows'",
    ],
    platforms=["any"],
    license="License :: OSI Approved :: MIT License",
    long_description="Run a subset of .gitlab-ci.yml jobs locally using docker",
    entry_points={
        "console_scripts": [
            "gle=gitlabemu.runner:run",
        ]
    }
)
