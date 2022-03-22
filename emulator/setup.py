from distutils.core import setup

VERSION = "0.9.3"

primary_platforms = "platform_system=='Linux' or platform_system=='Darwin' or platform_system=='Windows'"

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
        "docker>=5.0.2; " + primary_platforms,
        "python-gitlab>=3.2.0; python_version>='3.7' and ({})".format(primary_platforms),
        "python-gitlab==2.10.1; python_version=='3.6' and ({})".format(primary_platforms),
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
