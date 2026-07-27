# Contributing

## Before you start

```bash
./scripts/bootstrap.sh
./scripts/lab.sh doctor
./scripts/lab.sh test
```

`doctor` must pass before anything else is worth debugging. It checks the required
commands, the Docker daemon, the project-local kind binary, and that the generated
database credential exists without a trailing line ending. That last check exists because
`kubectl create secret --from-file` stores file bytes verbatim, and a stray newline once
became part of the password.

## The rule that matters most

Every gate in this project must be able to fail. Before accepting a new check, break the
thing it guards and confirm the check goes red. A gate that has only ever been observed
passing is not evidence.

The same applies to certification. A comparison against a reading the cluster did not
supply must fail, never pass by default. `release/contract.yaml` declares the expected
release and every check records the expected value, the observed value, and a pass field.

## Running the live gates

```bash
./scripts/lab.sh deploy
./scripts/lab.sh smoke
./scripts/lab.sh integration
./scripts/lab.sh load
./scripts/lab.sh verify-gate
./scripts/lab.sh rollback-drill
./scripts/lab.sh evidence
```

After any merge, `HEAD` moves and the running cluster falls behind, so `certify` fails
`release.source_revision` until you redeploy. That is the gate working. Redeploy to
reconcile before judging live state.

## Isolation

The lab acts only on the `deployproof` kind cluster. Before any cluster-scoped or
destructive action, kind must report a cluster named `deployproof`, the kubeconfig must
resolve to context `kind-deployproof`, and the Docker node must carry the label
`io.x-k8s.kind.cluster=deployproof`.

The lowercase `deployproof` identifier is the isolation boundary, not branding. It is the
cluster name, the context, the namespace, the Helm release name, and that Docker label. Do
not rename it to match the repository. Any neighbouring cluster, including KubeDrift, is
outside the project boundary and is never reused, modified, or deleted.

## Style

- Plain declarative sentences in prose and commit messages. No marketing tone.
- No em dashes or en dashes anywhere. Use a hyphen, a comma, or reword.
- Match the surrounding code. Comments are sparse and explain why, not what.
- Keep pull requests small and merge each one before starting the next.
- `WORKLOG.md` is a dated record. Add to it, do not rewrite past entries.

## Checks that run in CI

```bash
./scripts/lab.sh doctor
./scripts/lab.sh test
./scripts/lab.sh build
./scripts/lab.sh render
./scripts/lab.sh validate
```

CI runs the same `./scripts/lab.sh` entrypoints a workstation does. Do not add build,
validation, or certification logic to a pipeline file; add it to `deployctl` and call it
from both. `tests/test_pipeline.py` fails if a job runs anything other than a real
`deployctl` command, if the static stage stops matching the sequence in the README, if a
gate stops running, or if the teardown is removed.
