# Technical references

The initial tool and behavior decisions were checked on 2026-07-20 against these
upstream sources:

- [GitLab CI/CD pipelines](https://docs.gitlab.com/ci/pipelines/)
- [GitLab environments](https://docs.gitlab.com/ci/environments/)
- [GitLab report artifacts](https://docs.gitlab.com/ci/yaml/artifacts_reports/)
- [Kubernetes server-side apply and dry-run](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_apply/)
- [Kubernetes rollout status](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_rollout/kubectl_rollout_status/)
- [kind releases](https://github.com/kubernetes-sigs/kind/releases)
- [Helm releases](https://github.com/helm/helm/releases)
- [Kubeconform](https://github.com/yannh/kubeconform)
- [Kyverno CLI](https://kyverno.io/docs/subprojects/kyverno-cli/)
- [k6 checks](https://grafana.com/docs/k6/latest/using-k6/checks/)

## Initial pins

| Tool | Version |
| --- | --- |
| kind | 0.31.0 |
| kind node | Kubernetes 1.35.0, pinned by digest |
| Helm | 4.2.0, pinned by digest |
| Kubeconform | 0.7.0, pinned by digest |
| Kyverno CLI | 1.18.1, pinned by digest |
| k6 | 2.0.0, pinned by digest |
| Python base image | 3.12.11 slim, pinned by digest |
| PostgreSQL | 17.6 Alpine, pinned by digest |

The kind binary download is verified against the upstream SHA256 checksum. Every
containerized project tool and third-party runtime image is referenced by an immutable
SHA256 digest.
