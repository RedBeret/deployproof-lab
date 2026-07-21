# DeployProof Lab

DeployProof Lab is a Kubernetes release-certification project. It will prove that a
candidate release was configured, installed, loaded, exercised, and recoverable rather
than treating a successful `kubectl apply` as sufficient evidence.

The lab runs in native Ubuntu WSL with Docker and an isolated kind cluster. KubeDrift is
outside the project boundary and is never reused or modified.

## Current capabilities

- project-local `deployctl` operator command
- checksum-verified kind bootstrap
- pinned containerized Helm, Kubeconform, Kyverno CLI, and k6 tools
- non-root FastAPI inventory service
- deterministic PostgreSQL schema and seed data
- Helm chart with a strict values schema
- Kubernetes 1.35 schema validation with Kubeconform
- Kyverno workload security and immutable-release policy checks
- positive and negative fixtures that prove the gates can both pass and fail
- loopback-only kind port mapping
- unit and project-contract tests

## Bootstrap

From the repository root in WSL:

```bash
./scripts/bootstrap.sh
./scripts/lab.sh doctor
./scripts/lab.sh test
./scripts/lab.sh build
./scripts/lab.sh render
./scripts/lab.sh validate
```

`validate` renders the chart, checks every resource against Kubernetes 1.35 schemas,
and applies the repository's Kyverno policies. It also proves the validators are active
by requiring a malformed Deployment and an unsafe workload fixture to fail.

The complete deploy, certify, load, rollback, and evidence workflow will be added in the
next implementation stages. The design and acceptance criteria are recorded in
[docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md).
