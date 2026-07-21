{{- define "deployproof.name" -}}
deployproof
{{- end }}

{{- define "deployproof.labels" -}}
app.kubernetes.io/name: {{ include "deployproof.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
