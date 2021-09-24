"""
Docker support proxy module.

Importable even if the docker package is missing
"""
try:
    import docker
except ImportError:
    docker = None

