{{- define "langchain-service.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "langchain-service.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- include "langchain-service.name" . -}}
{{- end -}}
{{- end -}}

{{- define "langchain-service.labels" -}}
app.kubernetes.io/name: {{ include "langchain-service.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
{{- end -}}

{{- define "langchain-service.selectorLabels" -}}
app.kubernetes.io/name: {{ include "langchain-service.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "langchain-service.secretName" -}}
{{- if .Values.externalSecret.enabled -}}
{{- default (printf "%s-secrets" (include "langchain-service.fullname" .)) .Values.externalSecret.target.name -}}
{{- else -}}
{{- default "openai-api" .Values.secret.name -}}
{{- end -}}
{{- end -}}
