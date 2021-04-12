from distutils.core import setup
from gitlabsim.consts import VERSION

setup(
    name="gitlab-simulator",
    version=VERSION,
    description="Simulate gitlab pipelines",
    author="Ian Norton",
    author_email="inorton@gmail.com",
    url="https://gitlab.com/cunity/gitlab-emulator",
    packages=["gitlabsim"],
    install_requires=[
        "pyyaml>=5.1",
        "gitlab-emulator>=0.3.7",
        ],
    platforms=["any"],
    license="License :: OSI Approved :: MIT License",
    long_description="Simulate Gitlab pipelines and calculate the right runners to scale up/down"
)
