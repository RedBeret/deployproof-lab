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
- isolated cluster lifecycle with a three-part identity check before any destructive action
- live deployment with a bounded, ordered rollout
- 13 declared-versus-observed release comparisons written to a JSON report
- failure diagnostics collected automatically when a deploy fails
- unit, cluster, certification, and project-contract tests

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

## Deploy and certify

```bash
./scripts/lab.sh deploy
```

`deploy` creates the isolated cluster if it is absent, runs the static gate, builds and
loads the image, applies the namespace and database secret, revalidates the rendered
release, asks the API server to validate it without persisting it, installs the chart,
and waits for the database, the migration Job, and the API in that order. It finishes by
running certification, so a deploy that installs cleanly but produces the wrong state
still fails.

`./scripts/lab.sh certify` runs the comparisons on their own against an already deployed
release.

Cluster commands act only on the `deployproof` cluster:

```bash
./scripts/lab.sh cluster status
./scripts/lab.sh cluster delete
```

## What certification compares

`release/contract.yaml` declares the expected release. Certification reads live
Kubernetes, application, and database state and produces 13 comparisons:

| Area | Comparisons |
| --- | --- |
| Release identity | application, version, source revision |
| Kubernetes | deployment image, ConfigMap contents, API replicas, database replicas, completed migration Jobs |
| Configuration | declared values, configuration fingerprint |
| Database | migration version, table row counts, canonical data hash |

Every comparison records the expected value, the observed value, and a pass field to
`artifacts/state/live-certification.json`. A reading the cluster does not supply compares
unequal and fails, so a missing observation is not a pass.

When a deploy fails, Helm status, cluster resources, events, and each pod's description
and logs are written to `artifacts/state/deploy-diagnostics.txt`.

## Isolation

Every kubectl invocation is built by one wrapper that pins the project kubeconfig, the
`kind-deployproof` context, and the `deployproof` namespace, so no command inherits an
ambient context. Before any cluster-scoped or destructive action, kind must report a
cluster named `deployproof`, the kubeconfig must resolve to context `kind-deployproof`,
and the Docker node must carry the label `io.x-k8s.kind.cluster=deployproof`. Teardown
removes only the `deployproof` cluster.

## Challenges and resolutions

Defects found while bringing up the first live deployment. Each is covered by a test.

**PostgreSQL never initialized.** The data volume was mounted with `subPath: pgdata`.
Kubernetes creates a `subPath` directory as root, so `initdb` running as UID 10001 could
not `chmod` it and failed with `Operation not permitted`. The migration Job and the API
then waited on a database that never started. The volume root is now mounted directly
and `PGDATA` points at a child directory PostgreSQL creates and owns.

**Database authentication failed with a correct-looking password.** The generated
credential was written with a trailing newline, and `kubectl create secret --from-file`
stores file bytes verbatim, so the newline became part of the password. Hashing the local
file and the Kubernetes Secret showed them identical, which ruled out a mismatch and
pointed at the bytes themselves. Bootstrap now writes the credential without a trailing
newline and normalizes an existing file, `doctor` fails on a credential that is empty or
contains a line ending, and `deploy` refuses to apply one.

**Every deploy after the first failed its server-side dry run.** The dry run used its own
field manager, so the API server reported ownership conflicts against fields Helm already
owned. It now uses Helm's field manager.

**A timed-out install blocked retries.** The first failed attempt left the release in
`pending-install`, and later attempts were refused for the release state rather than any
new problem. Check `helm status` and `helm history` before retrying.

**Diagnostics failed while reporting a failure.** The collector passed a `helm status`
flag the pinned Helm version rejects, so a failed deploy was reported without the
evidence needed to diagnose it.

## Status

Stages 1 through 4 of [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) are complete. Smoke,
integration, load, failure-injection, and rollback gates, the GitLab pipeline, and the
Markdown and JUnit evidence formats are the remaining work.
