{{- /*
Denne fil laver helper logik til at formatere JSON på en læsbar måde uden escaped tegn som u003c.
Formålet er at generere pæn rå JSON til blandt andet NATS Box context secret data.
*/}}

{{- /*
toPrettyRawJson
input: interface{} valid JSON document
output: pretty raw JSON string
*/}}
{{- define "toPrettyRawJson" -}}
  {{- include "toPrettyRawJsonStr" (toPrettyJson .) -}}
{{- end -}}

{{- /*
toPrettyRawJsonStr
input: pretty JSON string
output: pretty raw JSON string
*/}}
{{- define "toPrettyRawJsonStr" -}}
  {{- $s :=
    (regexReplaceAll "([^\\\\](?:\\\\\\\\)*)\\\\u003e"
      (regexReplaceAll "([^\\\\](?:\\\\\\\\)*)\\\\u003c"
        (regexReplaceAll "([^\\\\](?:\\\\\\\\)*)\\\\u0026" . "${1}&")
      "${1}<")
    "${1}>")
  -}}
  {{- if regexMatch "([^\\\\](?:\\\\\\\\)*)\\\\u00(26|3c|3e)" $s -}}
    {{- include "toPrettyRawJsonStr" $s -}}
  {{- else -}}
    {{- $s -}}
  {{- end -}}
{{- end -}}
