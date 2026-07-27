# Changelog

## Unreleased

### Changed

- Renamed the project from `deployproof-lab` to `release-verify`. The rename is prose only.
  The lowercase `deployproof` identifier is unchanged in all 156 remaining places, because
  it is the kind cluster name, the kube context, the namespace, the Helm release name, and
  the Docker label the three-part identity check reads before any destructive action.
- Added the MIT license file that `pyproject.toml` had declared since the first commit
  without the repository ever granting it.

## 1.0

All ten done criteria in `docs/PROJECT_PLAN.md` met and verified against a live cluster.

### Certification

- Live comparison of a declared release contract against Kubernetes, application, and
  database state, producing 14 checks each recording expected, observed, and pass.
- The running image certified by content digest rather than by its mutable tag, with the
  loaded digest stamped onto the pod template so a rebuild under the same tag rolls the
  pod instead of leaving the old one serving.
- Source revision baked into the image at build time, so a stale image reports the commit
  it was built from rather than whatever the deploy supplied.
- A self-cleaning negative fixture that drifts real database state, confirms certification
  rejects it, and restores the state.

### Gates

- Static validation: Kubernetes 1.35 schema checks with Kubeconform and Kyverno workload
  and immutable-release policies, with fixtures that must be rejected.
- HTTP smoke checks asserting each declared endpoint's status and body against the
  contract.
- An integration check reading the live database directly and confirming the running
  application reports the same rows.
- A k6 load gate whose latency, error-rate, and check-rate thresholds live in the contract
  and exit non-zero when breached.
- A rollback drill that installs a second valid release, proves certification rejects it as
  undeclared, rolls back, and requires the declared release restored. The rollback runs in
  a `finally`, so an aborted drill still leaves the declared release installed.
- A clean-room teardown proof requiring every neighbouring cluster to be left byte for byte
  as it was, comparing by state rather than by count.

### Evidence and pipeline

- Certification evidence written as JSON, Markdown, and JUnit from one result, all agreeing
  on outcome and counts and containing no credential values.
- A GitLab pipeline whose every script line is a real `deployctl` entrypoint, enforced by
  `tests/test_pipeline.py`.
- Failure diagnostics collected automatically when a deploy fails.

### Fixed

- PostgreSQL never initialized because the data volume was mounted with `subPath: pgdata`,
  which Kubernetes creates as root, so `initdb` running as UID 10001 could not `chmod` it.
- Database authentication failed against a correct-looking password because the credential
  was written with a trailing newline and `kubectl create secret --from-file` stores file
  bytes verbatim.
- Every deploy after the first failed its server-side dry run, because the dry run used its
  own field manager and the API server reported ownership conflicts against fields Helm
  already owned.
- A rebuilt image left the old container running, because the tag and every chart value
  stayed the same so Helm saw no change to the pod template.
- Certification expired about ten minutes after a deploy, because the migration Job set
  `ttlSecondsAfterFinished` and Kubernetes garbage-collected the completed Job.
- Diagnostics failed while reporting a failure, because the collector passed a `helm status`
  flag the pinned Helm version rejects.
