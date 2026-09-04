{{- define "mda-demo.labels" -}}
app.kubernetes.io/part-of: mda-fabric-demo
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
data-classification: synthetic-unclass
{{- end }}
