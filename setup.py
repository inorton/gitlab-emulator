from distutils.core import setup

VERSION = "0.0.16"

setup(
    name="gitlab-emulator",
    version=VERSION,
    description="Run a subset of .gitlab-ci.yml jobs locally",
    author="Ian Norton",
    author_email="inorton@gmail.com",
    url="https://gitlab.com/cunity/gitlab-emulator",
    packages=["gitlabemu"],
    scripts=["locallab.py"],
    install_requires=["pyyaml"],
    platforms=["any"],
    license="License :: OSI Approved :: MIT License",
    long_description="Run a subset of .gitlab-ci.yml jobs locally using docker"
)
