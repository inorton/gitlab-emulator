from distutils.core import setup

VERSION = "0.1.0"

setup(
    name="gitlab-pipeline-designer",
    version=VERSION,
    description="Explore, simulate and develop gitlab pipelines",
    author="Ian Norton",
    author_email="inorton@gmail.com",
    url="https://gitlab.com/cunity/gitlab-emulator",
    packages=["PipelineDesigner"],
    install_requires=["gitlab-emulator>=0.3.1", "Flask>=1.1.2"],
    platforms=["any"],
    license="License :: OSI Approved :: MIT License",
    long_description="Render a full gitlab pipeline and estimate build timings",
    entry_points={
        "console_scripts": [
            "pipeline-designer=PipelineDesigner.console:run"
        ]
    }
)
