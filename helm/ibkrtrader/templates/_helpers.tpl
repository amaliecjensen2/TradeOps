{{/*
Udvid navnet på chartet.
*/}}
{{- define "ibkrtrader.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Opret et default fuldt kvalificeret app navn. Trunkeres ved 63 tegn.
*/}}
{{- define "ibkrtrader.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Chart label.
*/}}
{{- define "ibkrtrader.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Fælles labels.
*/}}
{{- define "ibkrtrader.labels" -}}
helm.sh/chart: {{ include "ibkrtrader.chart" . }}
{{ include "ibkrtrader.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: ibkrtrader
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
{{- end -}}

{{/*
Selector labels.
*/}}
{{- define "ibkrtrader.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ibkrtrader.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Service account navn.
*/}}
{{- define "ibkrtrader.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "ibkrtrader.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{/*
Aktivt gateway service hostnavn baseret på .Values.ibkr.mode.
Strategier og risk gatewayen bruger dette til at finde IBGW.
*/}}
{{- define "ibkrtrader.activeGatewayHost" -}}
{{- printf "%s-ibgw-%s.%s.svc.cluster.local" (include "ibkrtrader.fullname" .) .Values.ibkr.mode .Release.Namespace -}}
{{- end -}}

{{- define "ibkrtrader.activeGatewayPort" -}}
{{- if eq .Values.ibkr.mode "live" -}}
{{- .Values.ibkr.gateways.live.apiPort -}}
{{- else -}}
{{- .Values.ibkr.gateways.paper.apiPort -}}
{{- end -}}
{{- end -}}

{{/*
Intern NATS DNS (subchartens service).
*/}}
{{- define "ibkrtrader.natsHost" -}}
{{- printf "%s-nats.%s.svc.cluster.local" .Release.Name .Release.Namespace -}}
{{- end -}}

{{/*
Validér at alle aktiverede strategier har unikke clientIds.
Stopper template rendering med en tydelig fejl hvis dubletter findes.
*/}}
{{- define "ibkrtrader.validateClientIds" -}}
{{- $seen := dict -}}
{{- range $i, $s := .Values.strategies -}}
  {{- if $s.enabled -}}
    {{- if not $s.clientId -}}
      {{- fail (printf "strategy[%d] %q is missing clientId" $i $s.name) -}}
    {{- end -}}
    {{- $key := printf "%v" $s.clientId -}}
    {{- if hasKey $seen $key -}}
      {{- fail (printf "duplicate IBKR clientId %v on strategies %q and %q" $s.clientId (index $seen $key) $s.name) -}}
    {{- end -}}
    {{- $_ := set $seen $key $s.name -}}
  {{- end -}}
{{- end -}}
{{- end -}}

{{/*
Standard env blok for enhver pod der skal nå IBGW + NATS.
*/}}
{{- define "ibkrtrader.commonEnv" -}}
- name: IBGW_HOST
  value: {{ include "ibkrtrader.activeGatewayHost" . | quote }}
- name: IBGW_PORT
  value: {{ include "ibkrtrader.activeGatewayPort" . | quote }}
- name: NATS_URL
  value: {{ printf "nats://%s:4222" (include "ibkrtrader.natsHost" .) | quote }}
- name: IBKR_ACCOUNT
  value: {{ .Values.ibkr.account | quote }}
- name: IBKR_MODE
  value: {{ .Values.ibkr.mode | quote }}
{{- end -}}
