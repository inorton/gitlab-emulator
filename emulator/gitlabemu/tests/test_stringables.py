import os.path
from io import StringIO
from ..yamlloader import ordered_load, ordered_dump

HERE = os.path.abspath(os.path.dirname(__file__))


def test_yaml_roundtrips():
    services = os.path.join(HERE, "test-services.yaml")
    with open(services, "rb") as fd:
        loaded = ordered_load(fd)

    output = ordered_dump(loaded, default_flow_style=False, indent=4, width=120)

    assert output.startswith("stages:\n")
    buf = StringIO(output)

    reloaded = ordered_load(buf)
    assert reloaded == loaded
