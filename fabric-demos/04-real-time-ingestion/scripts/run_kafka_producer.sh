#!/usr/bin/env bash
set -euo pipefail

resource_group="${AZURE_RESOURCE_GROUP:-fabric-mda-demo}"
deployment_name="${DEMO04_EVENT_HUBS_DEPLOYMENT:-demo04-event-hubs}"
speed="${DEMO04_REPLAY_SPEED:-10}"
script_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_directory}/../../.." && pwd)"
emulator_directory="${repo_root}/shared/integrated-test-data/02-emulators"
input_file="${repo_root}/shared/integrated-test-data/projections/realtime/recorded_observed_events.jsonl"

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

cd "${emulator_directory}"
env -u UV_DEFAULT_INDEX -u PIP_INDEX_URL \
  uv run --extra kafka mda-replay-producer \
    --input "${input_file}" \
    --transport kafka \
    --bootstrap-servers "${bootstrap_server}" \
    --topic "${event_hub_name}" \
    --speed "${speed}"