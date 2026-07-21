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

Next: build the repository foundation, project-local bootstrap, sample service, and
Helm chart, then prove their baseline tests and rendering.
