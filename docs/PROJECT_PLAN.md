# DeployProof Lab project plan

## Objective

DeployProof Lab certifies that a Kubernetes release was configured, installed, loaded,
and exercised correctly. A release is not considered successful merely because its Pods
are running. The lab compares the declared release contract with live cluster state,
application state, database state, and load-test results, then emits evidence suitable
for an operator, QA reviewer, or customer handoff.

## Version 1 scope

- Run natively from Ubuntu WSL with Docker.
- Create an isolated kind cluster named `deployproof` using context
  `kind-deployproof`.
- Build and load a small inventory API image into the cluster.
- Package the API, PostgreSQL, migration Job, configuration, Service, and supporting
  resources as a Helm chart.
- Validate Helm values, rendered Kubernetes resources, and Kyverno policies before
  deployment.
- Ask the Kubernetes API server to validate the rendered release without persisting it.
- Deploy into the dedicated `deployproof` namespace and wait for bounded rollouts and
  Jobs.
- Compare the declared image, configuration fingerprint, application build, migration
  version, row counts, and canonical data hash with live state.
- Run smoke, integration, and k6 load gates with explicit pass/fail thresholds.
- Install a superseding valid release, prove the gate rejects it as undeclared, roll back,
  and prove the declared release is restored.
- Produce JSON, Markdown, and JUnit evidence from the same certification result.
- Provide a GitLab pipeline and a local runner script that execute the same commands.

## Non-goals

- Production database hosting or backup.
- Production secret management.
- A general-purpose Kubernetes deployment platform.
- Reusing, modifying, or deleting the KubeDrift cluster.
- Claiming production capacity from a laptop-scale load test.
- Installing a release that is known to be broken. Criterion 7 was originally written around
  injecting a bad release. It is proven instead with two valid, healthy releases: the second
  one serves every declared endpoint but is not the release the contract declares, which is
  the situation a rollback actually exists for. The lab is never deliberately left unhealthy.
- Air-gapped packaging in version 1; that is the first planned extension.

## Isolation and safety contract

- Every cluster command supplies `--context kind-deployproof` explicitly.
- Every namespace-scoped command supplies `--namespace deployproof` explicitly.
- Destructive cluster commands verify both the exact cluster and context names first.
- The kind node uses the Docker label `io.x-k8s.kind.cluster=deployproof`.
- The only mapped application port is `127.0.0.1:18082` to NodePort `30082`.
- Generated credentials, kubeconfig files, rendered manifests, reports, and tool
  downloads are ignored by Git.
- Teardown removes only the `deployproof` kind cluster.

## Release contract

Each candidate release declares:

- application name and version
- source revision
- container image reference
- target namespace
- expected configuration fingerprint
- expected migration version
- expected table row counts
- expected canonical data hash
- rollout timeout
- HTTP correctness checks
- load-test latency, error-rate, and check-rate thresholds

The validator records both expected and observed values. A missing observation is a
failure, not an implicit pass.

## Evidence contract

The JSON report is authoritative and contains:

- report format version and timestamps
- release identity
- tool and cluster versions
- every comparison with expected, observed, and pass fields
- rollout, migration, smoke, integration, and load-test results
- rollback drill results
- overall outcome and failure reasons

The Markdown report is the operator view. JUnit is the GitLab test-report view. All
three outputs must agree on the overall outcome and check counts.

## Delivery stages

1. Repository and toolchain foundation.
2. Sample service, database schema, deterministic data, container, and Helm chart.
3. Static schema and policy validation, including negative fixtures.
4. Isolated deployment and live desired-versus-actual certification.
5. Smoke, integration, load, failure-injection, and rollback gates.
6. GitLab pipeline and multi-format evidence.
7. Clean-room acceptance, documentation, and release review.

## Done criteria

Version 1 is complete only when all of the following are demonstrated from a clean
clone:

1. Bootstrap installs or downloads the pinned project-local tools and verifies them.
2. Static validation accepts the good chart and rejects at least one invalid manifest
   and one policy violation.
3. The cluster and namespace are created without changing `kind-kubedrift`.
4. A valid release deploys and every declared-versus-observed comparison passes.
5. A wrong configuration or incomplete data load makes certification fail.
6. k6 thresholds make an unacceptable load result exit non-zero.
7. A superseding release is rolled back and the prior declared release is proven restored.
8. JSON, Markdown, and JUnit evidence agree and contain no secret values.
9. Local validation and GitLab CI run the same entrypoints.
10. Teardown leaves no DeployProof containers while KubeDrift remains running.
