"""
Test the gitlab response data types
"""

from gitlabemu.gitlab.types import Image, Step, JobVariables


def test_image():
    """
    Test the Image type
    :return:
    """
    image = Image.from_value("alpine:3.18")
    assert image.name == "alpine:3.18"

    image = Image.from_value(
        {
            "name": "image:tag",
            "alias": "fred",
            "entrypoint": ["/bin/sh"],
            "ports": [1234, 2234]
        })
    assert image.name == "image:tag"
    assert image.alias == "fred"
    assert image.entrypoint[0] == "/bin/sh"
    assert image.ports[0] == 1234
    assert image.ports[1] == 2234


def test_step():
    """Test the step type"""
    step = Step()
    assert step.name is None
    assert step.when == "always"
    assert not step.allow_failure
    assert step.timeout == 0
    assert len(step.script) == 0

    step = Step({
        "name": "script",
        "script": [
            "echo hello",
            "df -h"
        ],
        "timeout": 32,
        "allow_failure": True,
    })

    assert step.name == "script"
    assert step.script[1] == "df -h"
    assert step.timeout == 32
    assert step.allow_failure


def test_variables():
    """Test the JobVariables type"""
    variables = JobVariables()
    assert len(variables.vars) == 0
    assert len(variables.public_vars) == 0
    variables.from_list([{
        "key": "FRED",
        "value": "drop",
        "public": True
    }])
    assert variables.vars["FRED"] == "drop"
    assert "FRED" in variables.public_vars
