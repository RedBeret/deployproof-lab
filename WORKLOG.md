# Work log

## 2026-07-20 - Stage 1

- Selected the project name `deployproof-lab`.
- Confirmed the native WSL target did not already exist.
- Confirmed Ubuntu WSL, Docker 29.1.3, kubectl 1.36.2, cgroup v2, 13 GiB available
  memory, and sufficient disk space.
- Confirmed KubeDrift is the only running container and uses context
  `kind-kubedrift`.
- Reserved cluster `deployproof`, context `kind-deployproof`, namespace `deployproof`,
  host port 18082, and NodePort 30082.
- Chose kind 0.31.0 with its supported Kubernetes 1.35.0 node image rather than using
  the current kubectl context or KubeDrift node.
- Chose project-local pinned tools so the first version does not require global Helm,
  kind, Kyverno, Kubeconform, k6, or GitLab Runner installation.
- Defined testable completion, release, evidence, and safety contracts before code.

## 2026-07-20 - Stage 2

- Added the FastAPI inventory service and deterministic PostgreSQL schema and seed
  migrations.
- Added a non-root application image with a read-only runtime-compatible layout.
- Added a Helm chart for the API, PostgreSQL, migration job, configuration, storage,
  resource limits, probes, and security contexts.
- Added a strict values schema that rejects mutable image tags.
- Added the `deployctl` CLI, project-local bootstrap, and a single lab entry point.
- Isolated project Docker configuration from WSL's incompatible Windows credential
  helper without changing the user's global Docker settings.
- Rebuilt a stale virtual environment against the active Python interpreter.
- Verified the kind download against its published SHA256 checksum and pulled each
  pinned validation/load-test image.
- Passed 10 unit and contract tests, Ruff formatting and linting, shell syntax checks,
  Helm lint, and Helm rendering.
- Confirmed the rendered release contains two ConfigMaps, two Services, one
  Deployment, one StatefulSet, and one migration Job.
- Confirmed an invalid `latest` image tag fails Helm schema validation.
- Built `deployproof-api:0.1.0`, confirmed it runs as `deployproof`, and imported the
  application package inside the image.
- Confirmed the root endpoint responds and the health endpoint returns HTTP 503 when
  PostgreSQL is unavailable, proving the expected degraded path.
- Confirmed the generated database password is ignored by Git and has mode `600`.

Next: add policy and manifest validation with Kubeconform and Kyverno, including
positive and negative fixtures.
