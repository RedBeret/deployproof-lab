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

## 2026-07-20 - Stage 3

- Added strict Kubeconform validation against Kubernetes 1.35 schemas.
- Added Kyverno rules for non-root workloads, RuntimeDefault seccomp, disabled
  privilege escalation, dropped Linux capabilities, resource requests/limits, and
  rejection of the `latest` tag.
- Added malformed-schema and unsafe-workload fixtures that must fail validation.
- Hardened the API image to use numeric UID/GID 10001 so Kubernetes can prove it is
  non-root before starting the container.
- Added non-root pod settings for PostgreSQL and the migration Job and bounded the
  migration Job's CPU and memory.
- Pinned the Python base image, PostgreSQL image, and all containerized project tools
  by SHA256 digest.
- Confirmed all seven rendered resources pass schema checks and all 12 applicable
  Kyverno evaluations pass.
- Confirmed both deliberate negative fixtures exit non-zero and identify the fixture
  that was rejected.
- Added `deployctl validate` and made the normal test command run the same static gate.

Next: create the isolated kind cluster, deploy the chart, and compare the declared
release contract with live Kubernetes, application, configuration, and database state.

## 2026-07-21 - Stage 4

- Added `deployctl cluster create`, `status`, and `delete` for the isolated cluster.
- Required kind, the project kubeconfig context, and the Docker node label to agree
  before any cluster-scoped or destructive action.
- Routed every kubectl invocation through one wrapper that pins the kubeconfig, the
  context, and the namespace.
- Waited for the API server to report a Ready node rather than trusting kind's own wait.
- Added `deployctl deploy` and `deployctl certify` and the declared release contract.
- Fixed the PostgreSQL data directory so `initdb` owns it; the previous `subPath` mount
  was created as root and could not be chmod'd by UID 10001.
- Removed the trailing newline from the generated database credential, which
  `kubectl create secret --from-file` had been storing as part of the password.
- Used Helm's field manager for the server-side dry run so repeat deploys do not fail on
  field ownership conflicts.
- Added diagnostics collection for failed deploys and restricted it to flags the pinned
  Helm version accepts.
- Confirmed a deploy from a deleted cluster installs revision 1 and passes all 13
  comparisons without manual intervention.
- Confirmed a second deploy against the existing release installs revision 2 and passes
  all 13 comparisons.
- Passed 31 tests, Ruff, shell syntax checks, Helm lint, Kubeconform, Kyverno, and both
  negative fixtures.

Next: add smoke, integration, k6 load, failure-injection, and rollback gates.

## 2026-07-22 - Image digest certification

- Recorded the digest of the image loaded into the node and compared it against the digest
  the running container reports, so the release is certified by content instead of the
  mutable `deployproof-api:0.1.0` tag.
- Stamped the loaded digest onto the pod template so a rebuild under the same tag rolls the
  pod; a content change no longer leaves the previous container in place.
- Added the fourteenth comparison, `kubernetes.image_digest`, which fails when the digest is
  missing on either side rather than treating two absent readings as equal.
- Confirmed with a live cluster that a stale running container fails `kubernetes.image_digest`
  while `kubernetes.deployment_image` still passes, then that a clean redeploy passes all 14.
- Passed 36 tests, Ruff, shell syntax checks, Helm lint, Kubeconform, Kyverno, and both
  negative fixtures.

Next: bake the source revision into the image so it cannot be injected at deploy time.

## 2026-07-22 - Baked source revision

- Passed the current commit to `docker build` as a `SOURCE_REVISION` build argument and set
  it as an image environment variable, so the running container reports the commit it was
  built from.
- Removed the deployment's `SOURCE_REVISION` environment variable and the
  `application.sourceRevision` chart value, so the revision can no longer be supplied at
  deploy time independent of the image.
- Confirmed with a live cluster that advancing HEAD without rebuilding fails
  `release.source_revision` while the image digest still matches, then that a redeploy from
  the new HEAD passes all 14 comparisons.
- Passed 37 tests, Ruff, shell syntax checks, Helm lint, Kubeconform, Kyverno, and both
  negative fixtures.

Next: add smoke, integration, k6 load, failure-injection, and rollback gates.

## 2026-07-22 - Live negative gate fixture

- Added `deployctl verify-gate`, the live counterpart to the static negative fixtures: it
  certifies the baseline, inserts a probe row into `inventory_items`, and confirms the drift
  fails exactly `database.row_counts` and `database.data_sha256`, then removes the row and
  confirms the gate returns to green.
- Chose a database row for the drift because it is real observed state, restores exactly on
  delete, and touches no Kubernetes resource, so it cannot split field ownership the way an
  out-of-band `kubectl patch` did in an earlier session.
- Removed the probe row before the baseline as well, so an interrupted run leaves nothing
  behind.
- Split certification into gathering observations and running the report so the gate can read
  the failing check names without shelling out again.
- Found that `kubernetes.completed_migration_jobs` depends on the migration Job, which has a
  600 second TTL, so certification is only valid for about ten minutes after a deploy. Left
  for a separate change; the durable `database.migration_version` already proves the same
  fact.
- Passed 39 tests, Ruff, shell syntax checks, Helm lint, Kubeconform, Kyverno, and both
  static negative fixtures, and the live gate end to end.

Next: add smoke, integration, k6 load, failure-injection, and rollback gates.
