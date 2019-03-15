from distutils.core import setup

setup(
    name="gitlab-emulator",
    version="0.0.1",
    description="Run a subsect of .gitlab-ci.yml jobs locally",
    author="Ian Norton",
    author_email="inorton@gmail.com",
    url="https://gitlab.com/cunity/gitlab-emulator",
    packages=["gitlabemu"],
    scripts=["locallab.py"],
    platforms=["any"],
    license="License :: OSI Approved :: MIT License",
    long_description="Run a subsect of .gitlab-ci.yml jobs locally using docker"
)
