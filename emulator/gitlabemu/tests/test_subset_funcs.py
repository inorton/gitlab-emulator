"""Test innards of the subset feature"""
from ..configloader import Loader
from ..generator import generate_artifact_fetch_job


def test_generate_artifact_fetcher_no_artifacts(in_tests):
    loader = Loader(emulator_variables=False)
    loader.load("needs.yml")
    generated = generate_artifact_fetch_job(loader, "start2",
                                            {})

    assert not generated

def test_generate_artifact_fetcher(in_tests):
    loader = Loader(emulator_variables=False)
    loader.load("needs.yml")
    generated = generate_artifact_fetch_job(loader, "middle",
                                            {
                                                "start2": "https://not.host/blaa/123456/job.zip"
                                            })

    assert generated
    assert "image" in generated
    assert "script" in generated
    assert "artifacts" in generated
    assert "variables" in generated
    assert "paths" in generated["artifacts"]
    assert "file.txt" in generated["artifacts"]["paths"]
