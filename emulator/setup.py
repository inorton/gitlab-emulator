from distutils.core import setup

VERSION = "1.5.4"

requirements = [
    "pyyaml>=5.1",
    "requests>=2.25.0",
    "requests-toolbelt>=0.9.1",
    "python-gitlab>=3.2.0; python_version>='3.7'",
    "python-gitlab==2.10.1; python_version<='3.6'",
    "certifi>=2022.6",
    "antlr4-python3-runtime==4.11.1",
]
requirements.extend([f"gitpython>=3.1; platform_system=='{p}'" for p in ["Darwin", "Windows", "Linux"]])

setup(
    name="gitlab-emulator",
    version=VERSION,
    description="Run/Inspect a .gitlab-ci.yml jobs and pipelines locally",
    author="Ian Norton",
    author_email="inorton@gmail.com",
    url="https://gitlab.com/cunity/gitlab-emulator",
    packages=[
        "gitlabemu",
        "gitlabemu.rules",
        "gitlabemu.genericci",
        "gitlabemu.gitlab",
        "gitlabemu.glp",
    ],
    scripts=["locallab.py"],
    install_requires=requirements,
    platforms=["any"],
    license="License :: OSI Approved :: MIT License",
    long_description="Run a subset of .gitlab-ci.yml jobs locally using docker",
    entry_points={
        "console_scripts": [
            "gle=gitlabemu.runner:run",
            "gle-config=gitlabemu.configtool:main",
            "glp=gitlabemu.glp.tool:run",
        ]
    }
)
