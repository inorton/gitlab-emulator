"""Test that we can get artifacts"""

from ..artifacts import GitlabArtifacts


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
