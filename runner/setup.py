from distutils.core import setup
from GitlabPyRunner import consts

setup(
    name="gitlab-python-runner",
    version=consts.VERSION,
    description="Pure python gitlab-runner",
    author="Ian Norton",
    author_email="inorton@gmail.com",
    url="https://gitlab.com/cunity/gitlab-python-runner",
    packages=["GitlabPyRunner"],
    include_package_data=True,
    scripts=["gitlab-runner.py"],
    install_requires=[
        "pyyaml>=5.1",
        "requests>=2.23.0",
        "gitlab-emulator>=0.5.0",
        "requests-toolbelt>=0.9.1", 
        "unidecode>=1.1.1"],
    platforms=["any"],
    license="License :: OSI Approved :: MIT License",
    long_description="Gitlab compatible runner without Go or SSH"
)
