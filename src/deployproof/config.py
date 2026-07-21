from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts"
TOOLS_BIN = ROOT / ".tools" / "bin"
SECRETS = ROOT / ".secrets"

CLUSTER_NAME = "deployproof"
KUBE_CONTEXT = "kind-deployproof"
NAMESPACE = "deployproof"
RELEASE_NAME = "deployproof"
HOST_PORT = 18082
NODE_PORT = 30082

KIND_VERSION = "v0.31.0"
KIND_NODE_IMAGE = (
    "kindest/node:v1.35.0@sha256:452d707d4862f52530247495d180205e029056831160e22870e37e3f6c1ac31f"
)
HELM_IMAGE = "alpine/helm:4.2.0"
KUBECONFORM_IMAGE = "ghcr.io/yannh/kubeconform:v0.7.0"
KYVERNO_IMAGE = "ghcr.io/kyverno/kyverno-cli:v1.18.1"
K6_IMAGE = "grafana/k6:2.0.0"

APP_IMAGE_REPOSITORY = "deployproof-api"
APP_VERSION = "0.1.0"
