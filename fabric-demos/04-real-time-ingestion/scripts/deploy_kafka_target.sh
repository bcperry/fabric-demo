#!/usr/bin/env bash
set -euo pipefail

resource_group="${AZURE_RESOURCE_GROUP:-fabric-mda-demo}"
deployment_name="${DEMO04_EVENT_HUBS_DEPLOYMENT:-demo04-event-hubs}"
script_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
template_file="${script_directory}/../infrastructure/main.bicep"
sender_principal_id="$(az ad signed-in-user show --query id -o tsv)"

az deployment group create \
  --resource-group "${resource_group}" \
  --name "${deployment_name}" \
  --template-file "${template_file}" \
  --parameters senderPrincipalId="${sender_principal_id}" \
  --output none

bootstrap_server="$(
  az deployment group show \
    --resource-group "${resource_group}" \
    --name "${deployment_name}" \
    --query properties.outputs.kafkaBootstrapServer.value \
    -o tsv
)"
event_hub_name="$(
  az deployment group show \
    --resource-group "${resource_group}" \
    --name "${deployment_name}" \
    --query properties.outputs.eventHubName.value \
    -o tsv
)"

printf 'Kafka target ready: %s / %s\n' "${bootstrap_server}" "${event_hub_name}"