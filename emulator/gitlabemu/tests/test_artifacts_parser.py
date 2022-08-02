"""Test that we can get artifacts"""
import pytest

from ..artifacts import GitlabArtifacts
from ..errors import BadSyntaxError


def test_parse_simple():
    """Test a normal artifacts set"""

    g = GitlabArtifacts()
    g.load({
        "paths": ["a.txt", "b.txt"],
        "reports": {
            "junit": [
                "foo.xml"
            ],
            "coverage_report": {
                "coverage_format": "cobertura",
                "path": "coverage.xml"
            }
        }
    })
    assert g.paths == ["a.txt", "b.txt"]
    assert g.reports["junit"] == ["foo.xml"]
    assert g.reports["coverage_report"] == {
        "coverage_format": "cobertura",
        "path": "coverage.xml"
    }


def test_parse_string_path():
    """Test parsing when given a path string instead of list"""
    g = GitlabArtifacts()
    with pytest.raises(BadSyntaxError):
        g.load({"paths": "file.xml"})


def test_junit_string_path():
    """Test junit reports when given a string instead of a list"""
    g = GitlabArtifacts()
    g.load({"reports": {
        "junit": "file.xml"
    }})

    assert g.reports["junit"] == ["file.xml"]

