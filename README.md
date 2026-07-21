# DeployProof Lab

DeployProof Lab is a Kubernetes release-certification project. It will prove that a
candidate release was configured, installed, loaded, exercised, and recoverable rather
than treating a successful `kubectl apply` as sufficient evidence.

The lab runs in native Ubuntu WSL with Docker and an isolated kind cluster. KubeDrift is
outside the project boundary and is never reused or modified.

## Current foundation

- project-local `deployctl` operator command
- checksum-verified kind bootstrap
- pinned containerized Helm, Kubeconform, Kyverno CLI, and k6 tools
- non-root FastAPI inventory service
- deterministic PostgreSQL schema and seed data
- Helm chart with a strict values schema
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
```

The complete deploy, certify, load, rollback, and evidence workflow will be added in the
next implementation stages. The design and acceptance criteria are recorded in
[docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md).
