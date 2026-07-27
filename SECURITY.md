# Security policy

## Scope

release-verify is a local laboratory. It builds an inventory API and a PostgreSQL database
into an isolated kind cluster on a workstation. It is not intended to run in production,
to receive production traffic, or to hold real credentials.

## Reporting

Report a vulnerability through GitHub's private security advisory form on this repository.
Please do not open a public issue for something exploitable.

## What the lab already enforces

- Kyverno policies reject workloads that run as root, that allow privilege escalation,
  that do not drop Linux capabilities, that omit a RuntimeDefault seccomp profile, or that
  lack resource requests and limits.
- The values schema rejects a mutable image tag, so a release cannot be pinned to
  `latest`.
- Every third-party runtime image and containerized tool is referenced by an immutable
  SHA256 digest, and the kind binary is verified against its published checksum.
- The only mapped application port is `127.0.0.1:18082`, so nothing is reachable off the
  host.
- Certification records the digest of the image actually running rather than trusting its
  tag, and the source revision is baked into the image at build time so a stale image
  cannot claim the current commit.
- Generated credentials, kubeconfig files, rendered manifests, and reports are ignored by
  Git. Evidence must contain no credential values.

## Credential handling

The database password is generated locally into `.secrets/` with mode 600 and written
without a trailing newline. `kubectl create secret --from-file` stores file bytes verbatim,
so a stray newline becomes part of the password. `doctor` fails on a credential that is
empty or contains a line ending, and `deploy` refuses to apply one.

## Dependencies

Python dependencies are pinned in `requirements-dev.txt` and `app/requirements.txt`.
Container images are pinned by digest. Dependabot is enabled for pip, GitHub Actions, and
Docker.

Dependabot raises alerts it does not always open a pull request for, so check
`gh api repos/RedBeret/release-verify/dependabot/alerts` rather than relying on the open
pull request list alone.
