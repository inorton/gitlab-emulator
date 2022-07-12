from distutils.core import setup

VERSION = "1.0.4"

requirements = [
    "pyyaml>=5.1",
    "requests>=2.23.0",
    "requests-toolbelt>=0.9.1",
    "python-gitlab>=3.2.0; python_version>='3.7'",
    "python-gitlab==2.10.1; python_version<='3.6'",
]
requirements.extend([f"gitpython>=3.1; platform_system=='{p}'" for p in ["Darwin", "Windows", "Linux"]])
requirements.extend([f"docker>=5.0.2; platform_system=='{p}'" for p in ["Darwin", "Windows", "Linux"]])

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
    install_requires=requirements,
    platforms=["any"],
    license="License :: OSI Approved :: MIT License",
    long_description="Run a subset of .gitlab-ci.yml jobs locally using docker",
    entry_points={
        "console_scripts": [
            "gle=gitlabemu.runner:run",
            "gle-config=gitlabemu.configtool:main",
        ]
    }
)
