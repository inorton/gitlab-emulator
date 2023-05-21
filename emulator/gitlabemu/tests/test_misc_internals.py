"""Tests for various internal functions"""
from ..resnamer import generate_resource_name, is_gle_resource, resource_owner_alive


def test_resnamer():
    """Test the resnamer module"""
    resource = generate_resource_name("program")
    assert is_gle_resource(resource)
    assert resource_owner_alive(resource)

    docker = generate_resource_name("docker")
    assert is_gle_resource(docker)