from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts"
TOOLS_BIN = ROOT / ".tools" / "bin"
SECRETS = ROOT / ".secrets"
POLICIES = ROOT / "policies"
FIXTURES = ROOT / "tests" / "fixtures"
KUBECONFIG = ROOT / ".kube" / "deployproof.yaml"
CLUSTER_CONFIG = ROOT / "kind" / "cluster.yaml"

CLUSTER_NAME = "deployproof"
KUBE_CONTEXT = "kind-deployproof"
NAMESPACE = "deployproof"
RELEASE_NAME = "deployproof"
HOST_PORT = 18082
NODE_PORT = 30082
ROLLOUT_TIMEOUT = "180s"

KIND_VERSION = "v0.31.0"
KUBERNETES_VERSION = "1.35.0"
KIND_NODE_IMAGE = (
    "kindest/node:v1.35.0@sha256:452d707d4862f52530247495d180205e029056831160e22870e37e3f6c1ac31f"
)
HELM_IMAGE = (
    "alpine/helm:4.2.0@sha256:af08f75a3130d666a50b9fc150f40987ef20b885cf67659aabf4b83a5f2c5501"
)
KUBECONFORM_IMAGE = (
    "ghcr.io/yannh/kubeconform:v0.7.0@sha256:"
    "85dbef6b4b312b99133decc9c6fc9495e9fc5f92293d4ff3b7e1b30f5611823c"
)
KYVERNO_IMAGE = (
    "ghcr.io/kyverno/kyverno-cli:v1.18.1@sha256:"
    "b7e272572d244ddec0b83469f7200ba883555bf69de4b294cee52a197c8c6590"
)
K6_IMAGE = (
    "grafana/k6:2.0.0@sha256:a33a0cfdc4d2483d6b7a3a22e726a499ff2831a671a49239104cd34a9937523c"
)

APP_IMAGE_REPOSITORY = "deployproof-api"
APP_VERSION = "0.1.0"
