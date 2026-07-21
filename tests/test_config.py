from deployproof import __version__
from deployproof.config import (
    CLUSTER_NAME,
    HOST_PORT,
    KUBE_CONTEXT,
    NAMESPACE,
    NODE_PORT,
)


def test_release_identity() -> None:
    assert __version__ == "0.1.0"
    assert CLUSTER_NAME == "deployproof"
    assert KUBE_CONTEXT == "kind-deployproof"
    assert NAMESPACE == "deployproof"


def test_reserved_ports_are_distinct() -> None:
    assert HOST_PORT == 18082
    assert NODE_PORT == 30082
