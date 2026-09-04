#!/usr/bin/env bash
set -euo pipefail

export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"
export PYTHONUTF8="${PYTHONUTF8:-1}"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"

WORKSPACE="${FABRIC_WORKSPACE:-mda-fabric-demo}"
LAKEHOUSE="${FABRIC_LAKEHOUSE:-IntegratedTestLakehouse}"
EVENTHOUSE="${FABRIC_EVENTHOUSE:-eh_mda_test}"
KQL_DATABASE="${FABRIC_KQL_DATABASE:-kqldb_mda_test}"
EVENTSTREAM="${FABRIC_EVENTSTREAM:-mda_test_events}"
WORKSPACE_PATH="${WORKSPACE}.Workspace"
LAKEHOUSE_PATH="${WORKSPACE_PATH}/01-data-lake-basics.Folder/${LAKEHOUSE}.Lakehouse"
DATA_PRODUCT_DIR="${REPO_ROOT}/shared/integrated-test-data"
DEMO_01_DIR="${REPO_ROOT}/fabric-demos/01-data-lake-basics"
DEMO_02_DIR="${REPO_ROOT}/fabric-demos/02-database-mirroring"
DEMO_03_DIR="${REPO_ROOT}/fabric-demos/03-star-schema-bi"
DEMO_04_DIR="${REPO_ROOT}/fabric-demos/04-real-time-ingestion"
DEMO_05_DIR="${REPO_ROOT}/fabric-demos/05-ml-models"
DEMO_06_DIR="${REPO_ROOT}/fabric-demos/06-ai-data-agent"
FABRIC_CLI_BIN="${FABRIC_CLI_BIN:-}"
FABRIC_CLI_PYTHON="${FABRIC_CLI_PYTHON:-}"
WORKSPACE_ID="${FABRIC_WORKSPACE_ID:-}"
LAKEHOUSE_ID="${FABRIC_LAKEHOUSE_ID:-}"

if [[ -z "${FABRIC_CLI_BIN}" ]]; then
    if command -v fab.exe >/dev/null 2>&1; then
        FABRIC_CLI_BIN="$(command -v fab.exe)"
    else
        FABRIC_CLI_BIN="$(command -v fab 2>/dev/null || true)"
    fi
fi

usage() {
    cat <<'EOF'
Usage: shared/setup-scripts/fabric_demo_cli.sh <command> [arguments]

Commands:
  install
      Install or upgrade the Fabric CLI as a uv-managed tool.
  auth
      Sign in interactively. Set FABRIC_TENANT_ID to target a tenant.
  status
      Show the active Fabric CLI authentication context.
  list
      List items in the configured workspace.
  provision-lakehouses
      Create the shared Integrated Test Lakehouse when absent.
  provision-realtime
      Deploy the Stage 04 Eventhouse, KQL schema, Eventstream, and live dashboard.
  push-reporting-items
      Deploy the Stage 03-05 semantic models and their dynamically bound reports.
  push-data
      Upload the canonical shared release once to Lakehouse Files/shared.
  push-notebook <file> [item-name]
      Create or update a Fabric notebook from a local .ipynb file.
  push-notebooks
      Create or update every notebook with the configured default Lakehouse.
  pull-notebook <item-name> [output-directory]
      Export a Fabric notebook as .ipynb.
  upload-file <local-file> [lakehouse-relative-path]
      Copy a local file into the configured Lakehouse Files area.
  download-file <lakehouse-relative-path> [local-path]
      Copy a Lakehouse file to the local filesystem.
  push-demo-01
      Deploy the CSV-to-Lakehouse notebook.
  push-demo-02
      Deploy the mirror validation notebook. Mirror setup remains manual.
  run-demo-02 [timeout-seconds]
      Validate the configured PostgreSQL mirror.
  push-demo-03
      Deploy star-schema notebooks, semantic model, and report.
  run-demo-03 [timeout-seconds]
      Run the seven Stage 03 notebooks in dependency order.
  refresh-demo-03-items
      Refresh SQL metadata, semantic model, and report after Gold changes.
  push-demo-04
      Deploy real-time replay notebooks plus engineer and director visuals.
  run-demo-04 [timeout-seconds]
      Run the four Stage 04 replay notebooks in dependency order.
  refresh-demo-04-items
      Refresh SQL metadata, semantic model, and report after Gold changes.
  push-demo-05
      Deploy ML notebooks, semantic model, and report.
  run-demo-05 [timeout-seconds]
      Run the six Stage 05 notebooks in dependency order.
  push-demo-06
      Deploy ontology notebooks and package assets.
  run-demo-06 [timeout-seconds]
      Validate bindings and create the ontology in dependency order.
  push-all
      Upload the shared release and import every notebook, model, and report.
    pull-demo-03 [output-directory]
      Export the three medallion notebooks.
  run-notebook <item-name> [timeout-seconds]
      Run a notebook synchronously and return its final job status.

Environment:
  FABRIC_WORKSPACE   Workspace name (default: mda-fabric-demo)
  FABRIC_LAKEHOUSE   Lakehouse name (default: IntegratedTestLakehouse)
    FABRIC_EVENTHOUSE  Eventhouse name (default: eh_mda_test)
    FABRIC_KQL_DATABASE KQL database name (default: kqldb_mda_test)
    FABRIC_EVENTSTREAM Eventstream name (default: mda_test_events)
  FABRIC_TENANT_ID   Optional tenant ID used by the auth command
  FABRIC_CLI_BIN     Optional path to fab or fab.exe
EOF
}

require_fab() {
    if [[ -z "${FABRIC_CLI_BIN}" || ! -x "${FABRIC_CLI_BIN}" ]]; then
        echo "Fabric CLI is not installed. Run: $0 install" >&2
        exit 1
    fi
}

cli_path() {
    if [[ "${FABRIC_CLI_BIN}" == *.exe ]]; then
        wslpath -w "$1"
    else
        printf '%s\n' "$1"
    fi
}

resolve_fabric_cli_python() {
    local tool_dir_windows

    if [[ -n "${FABRIC_CLI_PYTHON}" ]]; then
        return
    fi
    if [[ "${FABRIC_CLI_BIN}" != *.exe ]] || ! command -v uv.exe >/dev/null 2>&1; then
        echo "Set FABRIC_CLI_PYTHON to the Python executable containing fabric_cli." >&2
        exit 1
    fi

    tool_dir_windows="$(uv.exe tool dir | sed $'s/\r$//')"
    FABRIC_CLI_PYTHON="$(
        wslpath -u "${tool_dir_windows}\\ms-fabric-cli\\Scripts\\python.exe"
    )"
    if [[ ! -x "${FABRIC_CLI_PYTHON}" ]]; then
        echo "Fabric CLI Python executable not found: ${FABRIC_CLI_PYTHON}" >&2
        exit 1
    fi
}

resolve_workspace_id() {
    local output

    if [[ -z "${WORKSPACE_ID}" ]]; then
        output="$("${FABRIC_CLI_BIN}" get "${WORKSPACE_PATH}" --query id --output_format json)"
        WORKSPACE_ID="$(jq -r '.result.data[0]' <<< "${output}")"
    fi
}

resolve_lakehouse_id() {
    local lakehouse_name="$1"
    local lakehouse_path
    local output

    lakehouse_path="$(lakehouse_path_for_name "${lakehouse_name}")"
    output="$(
        "${FABRIC_CLI_BIN}" get \
            "${lakehouse_path}" \
            --query id \
            --output_format json
    )"
    jq -r '.result.data[0]' <<< "${output}"
}

resolve_item_id() {
    local item_path="$1"
    local output

    output="$(
        "${FABRIC_CLI_BIN}" get \
            "${item_path}" \
            --query id \
            --output_format json
    )"
    jq -r '.result.data[0]' <<< "${output}"
}

resolve_onelake_ids() {
    resolve_workspace_id
    if [[ -z "${LAKEHOUSE_ID}" ]]; then
        LAKEHOUSE_ID="$(resolve_lakehouse_id "${LAKEHOUSE}")"
    fi
}

refresh_lakehouse_sql_metadata() {
    local lakehouse_output
    local refresh_output
    local sql_endpoint_id
    local status_code

    resolve_onelake_ids
    lakehouse_output="$(
        "${FABRIC_CLI_BIN}" api \
            "workspaces/${WORKSPACE_ID}/lakehouses/${LAKEHOUSE_ID}" \
            --output_format json
    )"
    sql_endpoint_id="$(
        jq -r '.result.data[0].text.properties.sqlEndpointProperties.id // empty' \
            <<< "${lakehouse_output}"
    )"
    if [[ -z "${sql_endpoint_id}" ]]; then
        echo "Could not resolve SQL endpoint for Lakehouse: ${LAKEHOUSE}" >&2
        return 1
    fi

    refresh_output="$(
        "${FABRIC_CLI_BIN}" api \
            "workspaces/${WORKSPACE_ID}/sqlEndpoints/${sql_endpoint_id}/refreshMetadata" \
            --method post \
            --output_format json
    )"
    status_code="$(jq -r '.result.data[0].status_code // empty' <<< "${refresh_output}")"
    if [[ "${status_code}" != "200" ]]; then
        echo "Lakehouse SQL metadata refresh failed: ${LAKEHOUSE}" >&2
        jq -r '.result.data[0].text // .' <<< "${refresh_output}" >&2
        return 1
    fi
}

upload_onelake_file() {
    local file="$1"
    local relative_path="$2"
    local lakehouse_name="$3"
    local lakehouse_id

    resolve_fabric_cli_python
    resolve_workspace_id
    lakehouse_id="$(resolve_lakehouse_id "${lakehouse_name}")"
    "${FABRIC_CLI_PYTHON}" \
        "$(cli_path "${SCRIPT_DIR}/onelake_upload.py")" \
        "${WORKSPACE_ID}" \
        "${lakehouse_id}" \
        "$(cli_path "${file}")" \
        "Files/${relative_path}"
}

require_argument() {
    local value="${1:-}"
    local label="$2"
    if [[ -z "${value}" ]]; then
        echo "Missing required argument: ${label}" >&2
        usage >&2
        exit 2
    fi
}

remote_exists() {
    local output
    output="$("${FABRIC_CLI_BIN}" exists "$1" --output_format json)"
    [[ "${output}" == *'"message": "true"'* ]]
}

container_has_item() {
    local container_path="$1"
    local item_name="$2"
    local output

    output="$("${FABRIC_CLI_BIN}" ls "${container_path}" --output_format json)"
    [[ "${output}" == *"\"name\": \"${item_name}\""* ]]
}

demo_folder_for_file() {
    local file
    local relative_path

    file="$(realpath -m "$1")"
    if [[ "${file}" != "${REPO_ROOT}/fabric-demos/"* ]]; then
        return
    fi

    relative_path="${file#"${REPO_ROOT}/fabric-demos/"}"
    printf '%s\n' "${relative_path%%/*}"
}

notebook_lakehouse_for_file() {
    printf '%s\n' "${LAKEHOUSE}"
}

lakehouse_path_for_name() {
    local lakehouse_name="$1"
    printf '%s\n' "${WORKSPACE_PATH}/01-data-lake-basics.Folder/${lakehouse_name}.Lakehouse"
}

ensure_workspace_folder() {
    local folder_name="$1"
    local folder_path="${WORKSPACE_PATH}/${folder_name}.Folder"

    if ! remote_exists "${folder_path}"; then
        "${FABRIC_CLI_BIN}" mkdir "${folder_path}"
    fi
}

ensure_lakehouse() {
    local lakehouse_name="$1"
    local lakehouse_path

    lakehouse_path="$(lakehouse_path_for_name "${lakehouse_name}")"
    if ! remote_exists "${lakehouse_path}"; then
        "${FABRIC_CLI_BIN}" mkdir "${lakehouse_path}"
    fi
}

provision_lakehouses() {
    ensure_workspace_folder "01-data-lake-basics"
    ensure_lakehouse "${LAKEHOUSE}"
}

prepare_item_target() {
    local file="$1"
    local item_name="$2"
    local item_type="$3"
    local folder_name
    local root_item_path="${WORKSPACE_PATH}/${item_name}.${item_type}"

    folder_name="$(demo_folder_for_file "${file}")"
    TARGET_ITEM_PATH="${root_item_path}"

    if [[ -z "${folder_name}" ]]; then
        return
    fi

    ensure_workspace_folder "${folder_name}"
    TARGET_ITEM_PATH="${WORKSPACE_PATH}/${folder_name}.Folder/${item_name}.${item_type}"

    if ! container_has_item "${WORKSPACE_PATH}/${folder_name}.Folder" "${item_name}.${item_type}" &&
        container_has_item "${WORKSPACE_PATH}" "${item_name}.${item_type}"; then
        echo "Move ${item_name}.${item_type} into ${folder_name} in the Fabric portal before importing." >&2
        exit 1
    fi
}

push_notebook() {
    local file="$1"
    local item_name="${2:-$(basename "${file}" .ipynb)}"
    local definition_directory
    local import_status=0
    local notebook_lakehouse_id
    local notebook_lakehouse_name

    if [[ ! -f "${file}" ]]; then
        echo "Notebook not found: ${file}" >&2
        exit 1
    fi
    if [[ "${item_name}" == *'"'* ]]; then
        echo "Notebook item names cannot contain double quotes: ${item_name}" >&2
        exit 1
    fi

    prepare_item_target "${file}" "${item_name}" "Notebook"
    resolve_workspace_id
    notebook_lakehouse_name="$(notebook_lakehouse_for_file "${file}")"
    notebook_lakehouse_id="$(resolve_lakehouse_id "${notebook_lakehouse_name}")"
    mkdir -p "${REPO_ROOT}/.fabric-export"
    definition_directory="$(
        mktemp -d "${REPO_ROOT}/.fabric-export/notebook-import.XXXXXX.Notebook"
    )"
    jq \
        --arg lakehouse_id "${notebook_lakehouse_id}" \
        --arg lakehouse_name "${notebook_lakehouse_name}" \
        --arg workspace_id "${WORKSPACE_ID}" \
        '
        .metadata.kernel_info.name = "synapse_pyspark"
        | .metadata.dependencies.lakehouse = {
            "default_lakehouse": $lakehouse_id,
            "default_lakehouse_name": $lakehouse_name,
            "default_lakehouse_workspace_id": $workspace_id,
            "known_lakehouses": []
        }
        ' "${file}" > "${definition_directory}/notebook-content.ipynb"
    printf '%s\n' \
        '{' \
        '  "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",' \
        '  "metadata": {' \
        '    "type": "Notebook",' \
        "    \"displayName\": \"${item_name}\"" \
        '  },' \
        '  "config": {' \
        '    "version": "2.0",' \
        '    "logicalId": "00000000-0000-0000-0000-000000000000"' \
        '  }' \
        '}' > "${definition_directory}/.platform"

    "${FABRIC_CLI_BIN}" import "${TARGET_ITEM_PATH}" \
        --input "$(cli_path "${definition_directory}")" \
        --force || import_status=$?
    rm -rf "${definition_directory}"
    return "${import_status}"
}

push_fabric_item() {
    local source_path="$1"
    local item_name="$2"
    local item_type="$3"
    local item_format="${4:-}"
    local target_source_path="${5:-${source_path}}"
    local import_args=()

    prepare_item_target "${target_source_path}" "${item_name}" "${item_type}"
    if [[ -n "${item_format}" ]]; then
        import_args+=(--format "${item_format}")
    fi

    "${FABRIC_CLI_BIN}" import "${TARGET_ITEM_PATH}" \
        --input "$(cli_path "${source_path}")" \
        "${import_args[@]}" \
        --force
}

push_bound_semantic_model() {
    local source_path="$1"
    local item_name="$2"
    local definition_directory
    local import_status=0

    resolve_onelake_ids
    mkdir -p "${REPO_ROOT}/.fabric-export"
    definition_directory="$(
        mktemp -d "${REPO_ROOT}/.fabric-export/semantic-model-import.XXXXXX.SemanticModel"
    )"
    cp -R "${source_path}/." "${definition_directory}/"
    sed -E \
        "s#https://onelake\.dfs\.fabric\.microsoft\.com/[0-9a-f-]+/[0-9a-f-]+#https://onelake.dfs.fabric.microsoft.com/${WORKSPACE_ID}/${LAKEHOUSE_ID}#g" \
        "${source_path}/definition/expressions.tmdl" \
        > "${definition_directory}/definition/expressions.tmdl"
    grep -Fq \
        "https://onelake.dfs.fabric.microsoft.com/${WORKSPACE_ID}/${LAKEHOUSE_ID}" \
        "${definition_directory}/definition/expressions.tmdl"
    push_fabric_item \
        "${definition_directory}" \
        "${item_name}" \
        "SemanticModel" \
        "TMDL" \
        "${source_path}" || import_status=$?
    rm -rf "${definition_directory}"
    return "${import_status}"
}

push_bound_report() {
    local source_path="$1"
    local item_name="$2"
    local semantic_model_path="$3"
    local semantic_model_id
    local definition_directory
    local import_status=0

    semantic_model_id="$(resolve_item_id "${semantic_model_path}")"
    mkdir -p "${REPO_ROOT}/.fabric-export"
    definition_directory="$(
        mktemp -d "${REPO_ROOT}/.fabric-export/report-import.XXXXXX.Report"
    )"
    cp -R "${source_path}/." "${definition_directory}/"
    jq \
        --arg semantic_model_id "${semantic_model_id}" \
        '.datasetReference.byConnection.connectionString |= sub("semanticmodelid=[^;]*"; "semanticmodelid=" + $semantic_model_id)' \
        "${source_path}/definition.pbir" > "${definition_directory}/definition.pbir"
    push_fabric_item \
        "${definition_directory}" \
        "${item_name}" \
        "Report" \
        "" \
        "${source_path}" || import_status=$?
    rm -rf "${definition_directory}"
    return "${import_status}"
}

push_bound_kql_dashboard() {
    local source_path="$1"
    local item_name="$2"
    local kql_database_path="$3"
    local kql_database_id
    local kql_database_output
    local query_service_uri
    local definition_directory
    local import_status=0

    resolve_workspace_id
    kql_database_id="$(resolve_item_id "${kql_database_path}")"
    kql_database_output="$(
        "${FABRIC_CLI_BIN}" api \
            "workspaces/${WORKSPACE_ID}/kqlDatabases/${kql_database_id}" \
            --output_format json
    )"
    query_service_uri="$(
        jq -r '.result.data[0].text.properties.queryServiceUri // empty' \
            <<< "${kql_database_output}"
    )"
    if [[ -z "${query_service_uri}" ]]; then
        echo "Could not resolve query endpoint for KQL database: ${kql_database_path}" >&2
        return 1
    fi

    mkdir -p "${REPO_ROOT}/.fabric-export"
    definition_directory="$(
        mktemp -d "${REPO_ROOT}/.fabric-export/kql-dashboard-import.XXXXXX.KQLDashboard"
    )"
    cp -R "${source_path}/." "${definition_directory}/"
    jq \
        --arg cluster_uri "${query_service_uri}" \
        --arg database_id "${kql_database_id}" \
        --arg database_name "${KQL_DATABASE}" \
        --arg workspace_id "${WORKSPACE_ID}" \
        '
        .dataSources[0].clusterUri = $cluster_uri
        | .dataSources[0].name = $database_name
        | .dataSources[0].databaseArtifactId = $database_id
        | .dataSources[0].database = $database_id
        | .dataSources[0].workspace = $workspace_id
        ' "${source_path}/RealTimeDashboard.json" \
        > "${definition_directory}/RealTimeDashboard.json"
    push_fabric_item \
        "${definition_directory}" \
        "${item_name}" \
        "KQLDashboard" \
        "" \
        "${source_path}" || import_status=$?
    rm -rf "${definition_directory}"
    return "${import_status}"
}

request_semantic_model_refresh() {
    local item_path="$1"
    local item_output
    local model_id
    local refresh_output
    local status_code

    item_output="$(
        "${FABRIC_CLI_BIN}" get \
            "${item_path}" \
            --query id \
            --output_format json
    )"
    model_id="$(jq -r '.result.data[0] // empty' <<< "${item_output}")"
    if [[ -z "${model_id}" ]]; then
        echo "Could not resolve semantic model ID: ${item_path}" >&2
        return 1
    fi

    refresh_output="$(
        "${FABRIC_CLI_BIN}" api \
            "datasets/${model_id}/refreshes" \
            --audience powerbi \
            --method post \
            --headers 'Content-Type=application/json' \
            --input '{"notifyOption":"NoNotification"}' \
            --output_format json
    )"
    status_code="$(jq -r '.result.data[0].status_code // empty' <<< "${refresh_output}")"
    if [[ "${status_code}" != "202" ]]; then
        echo "Semantic model refresh was not accepted: ${item_path}" >&2
        jq -r '.result.data[0].text // .' <<< "${refresh_output}" >&2
        return 1
    fi
}

push_demo_03_items() {
    push_bound_semantic_model \
        "${DEMO_03_DIR}/fabric-items/MDA Pre-Test Readiness.SemanticModel" \
        "MDA Pre-Test Readiness"
    push_bound_report \
        "${DEMO_03_DIR}/fabric-items/MDA Pre-Test Readiness and Data Trust.Report" \
        "MDA Pre-Test Readiness and Data Trust" \
        "${WORKSPACE_PATH}/03-star-schema-bi.Folder/MDA Pre-Test Readiness.SemanticModel"
}

refresh_demo_03_items() {
    refresh_lakehouse_sql_metadata
    push_bound_semantic_model \
        "${DEMO_03_DIR}/fabric-items/MDA Pre-Test Readiness.SemanticModel" \
        "MDA Pre-Test Readiness"
    request_semantic_model_refresh \
        "${WORKSPACE_PATH}/03-star-schema-bi.Folder/MDA Pre-Test Readiness.SemanticModel"
    push_bound_report \
        "${DEMO_03_DIR}/fabric-items/MDA Pre-Test Readiness and Data Trust.Report" \
        "MDA Pre-Test Readiness and Data Trust" \
        "${WORKSPACE_PATH}/03-star-schema-bi.Folder/MDA Pre-Test Readiness.SemanticModel"
}

push_demo_04_items() {
    push_bound_semantic_model \
        "${DEMO_04_DIR}/fabric-items/MDA During-Test Findings.SemanticModel" \
        "MDA During-Test Findings"
    push_bound_report \
        "${DEMO_04_DIR}/fabric-items/MDA During-Test Command Health.Report" \
        "MDA During-Test Decision Brief" \
        "${WORKSPACE_PATH}/04-real-time-ingestion.Folder/MDA During-Test Findings.SemanticModel"
}

refresh_demo_04_items() {
    refresh_lakehouse_sql_metadata
    push_bound_semantic_model \
        "${DEMO_04_DIR}/fabric-items/MDA During-Test Findings.SemanticModel" \
        "MDA During-Test Findings"
    request_semantic_model_refresh \
        "${WORKSPACE_PATH}/04-real-time-ingestion.Folder/MDA During-Test Findings.SemanticModel"
    push_bound_report \
        "${DEMO_04_DIR}/fabric-items/MDA During-Test Command Health.Report" \
        "MDA During-Test Decision Brief" \
        "${WORKSPACE_PATH}/04-real-time-ingestion.Folder/MDA During-Test Findings.SemanticModel"
}

push_demo_04_realtime_items() {
    local folder_path="${WORKSPACE_PATH}/04-real-time-ingestion.Folder"
    local eventhouse_path="${folder_path}/${EVENTHOUSE}.Eventhouse"
    local kql_database_path="${folder_path}/${KQL_DATABASE}.KQLDatabase"
    local default_kql_database_path="${folder_path}/${EVENTHOUSE}.KQLDatabase"
    local eventhouse_id
    local eventhouse_created=false
    local definition_directory
    local import_status=0

    ensure_workspace_folder "04-real-time-ingestion"
    if ! remote_exists "${eventhouse_path}"; then
        "${FABRIC_CLI_BIN}" mkdir "${eventhouse_path}"
        eventhouse_created=true
    fi
    eventhouse_id="$(resolve_item_id "${eventhouse_path}")"

    mkdir -p "${REPO_ROOT}/.fabric-export"
    definition_directory="$(
        mktemp -d "${REPO_ROOT}/.fabric-export/kql-database-import.XXXXXX.KQLDatabase"
    )"
    jq -n \
        --arg parent_eventhouse_item_id "${eventhouse_id}" \
        '{
            databaseType: "ReadWrite",
            parentEventhouseItemId: $parent_eventhouse_item_id,
            oneLakeCachingPeriod: "P36500D",
            oneLakeStandardStoragePeriod: "P365000D"
        }' > "${definition_directory}/DatabaseProperties.json"
    cp \
        "${DEMO_04_DIR}/fabric-items/${KQL_DATABASE}.KQLDatabase/DatabaseSchema.kql" \
        "${DEMO_04_DIR}/fabric-items/${KQL_DATABASE}.KQLDatabase/.platform" \
        "${definition_directory}/"
    "${FABRIC_CLI_BIN}" import "${kql_database_path}" \
        --input "$(cli_path "${definition_directory}")" \
        --force || import_status=$?
    rm -rf "${definition_directory}"
    if [[ "${import_status}" -ne 0 ]]; then
        return "${import_status}"
    fi

    if [[ "${eventhouse_created}" == true && "${EVENTHOUSE}" != "${KQL_DATABASE}" ]] && \
        remote_exists "${default_kql_database_path}"; then
        "${FABRIC_CLI_BIN}" rm "${default_kql_database_path}" --hard --force
    fi

    push_fabric_item \
        "${DEMO_04_DIR}/fabric-items/${EVENTSTREAM}.Eventstream" \
        "${EVENTSTREAM}" \
        "Eventstream"
    push_bound_kql_dashboard \
        "${DEMO_04_DIR}/fabric-items/MDA Live Test Control.KQLDashboard" \
        "MDA Live Test Control" \
        "${kql_database_path}"
}

push_demo_05_items() {
    push_bound_semantic_model \
        "${DEMO_05_DIR}/fabric-items/MDA Readiness Model Governance.SemanticModel" \
        "MDA Readiness Model Governance"
    request_semantic_model_refresh "${TARGET_ITEM_PATH}"
    push_bound_report \
        "${DEMO_05_DIR}/fabric-items/MDA Readiness Model Governance.Report" \
        "MDA Readiness Model Governance" \
        "${WORKSPACE_PATH}/05-ml-models.Folder/MDA Readiness Model Governance.SemanticModel"
}

ensure_onelake_directory() {
    local relative_directory="$1"
    local lakehouse_path="$2"
    local current_path="${lakehouse_path}/Files"
    local part
    local parts=()

    IFS='/' read -r -a parts <<< "${relative_directory}"
    for part in "${parts[@]}"; do
        if [[ -z "${part}" || "${part}" == "." ]]; then
            continue
        fi
        current_path="${current_path}/${part}"
        if ! remote_exists "${current_path}"; then
            "${FABRIC_CLI_BIN}" mkdir "${current_path}"
        fi
    done
}

upload_file() {
    local file="$1"
    local relative_path="${2:-$(basename "${file}")}"
    local target_lakehouse_name
    local target_lakehouse_path
    local remote_directory

    if [[ ! -f "${file}" ]]; then
        echo "Source file not found: ${file}" >&2
        exit 1
    fi

    relative_path="${relative_path#/}"
    relative_path="${relative_path#Files/}"
    target_lakehouse_name="$(notebook_lakehouse_for_file "${file}")"
    target_lakehouse_path="$(lakehouse_path_for_name "${target_lakehouse_name}")"
    if [[ "$(basename "${relative_path}")" != "$(basename "${file}")" ]]; then
        echo "Lakehouse upload cannot rename files: ${relative_path}" >&2
        exit 1
    fi

    if [[ "${relative_path}" == *"="* ]]; then
        upload_onelake_file "${file}" "${relative_path}" "${target_lakehouse_name}"
        return
    fi

    ensure_onelake_directory "$(dirname "${relative_path}")" "${target_lakehouse_path}"
    remote_directory="${target_lakehouse_path}/Files/$(dirname "${relative_path}")"
    "${FABRIC_CLI_BIN}" cp "$(cli_path "${file}")" "${remote_directory}" --force
}

push_shared_data() {
    local file
    local files=()
    local relative_path

    for file in \
        "${DATA_PRODUCT_DIR}/RELEASE_MANIFEST.json" \
        "${DATA_PRODUCT_DIR}/PORTFOLIO_CONTRACT.json"; do
        relative_path="${file#"${REPO_ROOT}/"}"
        upload_file "${file}" "${relative_path}"
    done

    mapfile -d '' files < <(
        find \
            "${DATA_PRODUCT_DIR}/data" \
            "${DATA_PRODUCT_DIR}/projections/foundation" \
            "${DATA_PRODUCT_DIR}/projections/medallion" \
            "${DATA_PRODUCT_DIR}/projections/model-governance" \
            "${DATA_PRODUCT_DIR}/projections/realtime" \
            "${DATA_PRODUCT_DIR}/projections/star-schema" \
            -type f \
            ! -path '*/__pycache__/*' \
            -print0 |
            sort -z
    )
    for file in "${files[@]}"; do
        relative_path="${file#"${REPO_ROOT}/"}"
        upload_file "${file}" "${relative_path}"
    done
}

push_all_notebooks() {
    local file
    local notebooks=()

    mapfile -d '' notebooks < <(
        find "${REPO_ROOT}/fabric-demos" \
            -type f \
            -name '*.ipynb' \
            -print0 |
            sort -z
    )
    for file in "${notebooks[@]}"; do
        push_notebook "${file}"
    done
}

command="${1:-help}"
shift || true

case "${command}" in
    install)
        command -v uv >/dev/null 2>&1 || {
            echo "uv is required to install the Fabric CLI." >&2
            exit 1
        }
        uv tool install --upgrade ms-fabric-cli
        fab --version
        ;;
    auth)
        require_fab
        if [[ -n "${FABRIC_TENANT_ID:-}" ]]; then
            "${FABRIC_CLI_BIN}" auth login --tenant "${FABRIC_TENANT_ID}"
        else
            "${FABRIC_CLI_BIN}" auth login
        fi
        ;;
    status)
        require_fab
        "${FABRIC_CLI_BIN}" auth status
        ;;
    list)
        require_fab
        "${FABRIC_CLI_BIN}" ls "${WORKSPACE_PATH}" --long
        ;;
    provision-lakehouses)
        require_fab
        provision_lakehouses
        ;;
    provision-realtime)
        require_fab
        push_demo_04_realtime_items
        ;;
    push-reporting-items)
        require_fab
        push_demo_03_items
        push_demo_04_items
        push_demo_05_items
        ;;
    push-data)
        require_fab
        provision_lakehouses
        push_shared_data
        ;;
    push-notebook)
        require_fab
        require_argument "${1:-}" "file"
        push_notebook "$1" "${2:-}"
        ;;
    push-notebooks)
        require_fab
        provision_lakehouses
        push_all_notebooks
        ;;
    pull-notebook)
        require_fab
        require_argument "${1:-}" "item-name"
        output_directory="${2:-${REPO_ROOT}/.fabric-export}"
        mkdir -p "${output_directory}"
        "${FABRIC_CLI_BIN}" export "${WORKSPACE_PATH}/$1.Notebook" \
            --output "$(cli_path "${output_directory}")" \
            --format .ipynb \
            --force
        ;;
    upload-file)
        require_fab
        require_argument "${1:-}" "local-file"
        upload_file "$1" "${2:-}"
        ;;
    download-file)
        require_fab
        require_argument "${1:-}" "lakehouse-relative-path"
        remote_path="${1#/}"
        remote_path="${remote_path#Files/}"
        local_path="${2:-${REPO_ROOT}/.fabric-export/$(basename "${remote_path}")}"
        mkdir -p "$(dirname "${local_path}")"
        "${FABRIC_CLI_BIN}" cp "${LAKEHOUSE_PATH}/Files/${remote_path}" "$(cli_path "${local_path}")" --force
        ;;
    push-demo-01)
        require_fab
        provision_lakehouses
        push_shared_data
        push_notebook "${DEMO_01_DIR}/notebooks/01_load_mission_baseline.ipynb"
        ;;
    push-demo-02)
        require_fab
        provision_lakehouses
        push_notebook "${DEMO_02_DIR}/notebooks/01_validate_mirror.ipynb"
        echo "Configure MDA Operations Mirror and expose its tables to this notebook before running Stage 02."
        ;;
    run-demo-02)
        require_fab
        timeout="${1:-1800}"
        "${FABRIC_CLI_BIN}" job run \
            "${WORKSPACE_PATH}/02-database-mirroring.Folder/01_validate_mirror.Notebook" \
            --timeout "${timeout}" \
            --polling_interval 15
        ;;
    push-demo-03)
        require_fab
        provision_lakehouses
        push_shared_data
        for file in \
            "${DEMO_03_DIR}/notebooks/01_bronze_ingest.ipynb" \
            "${DEMO_03_DIR}/notebooks/02_silver_canonicalize.ipynb" \
            "${DEMO_03_DIR}/notebooks/03_gold_test_products.ipynb" \
            "${DEMO_03_DIR}/star-schema/notebooks/01_bronze_multi_lane_ingest.ipynb" \
            "${DEMO_03_DIR}/star-schema/notebooks/02_silver_conformed_dimensions.ipynb" \
            "${DEMO_03_DIR}/star-schema/notebooks/03_gold_integrated_facts.ipynb" \
            "${DEMO_03_DIR}/star-schema/notebooks/04_gold_mission_products.ipynb"; do
            push_notebook "${file}"
        done
        push_demo_03_items
        ;;
    run-demo-03)
        require_fab
        timeout="${1:-1800}"
        for item_name in \
            01_bronze_ingest \
            02_silver_canonicalize \
            03_gold_test_products \
            01_bronze_multi_lane_ingest \
            02_silver_conformed_dimensions \
            03_gold_integrated_facts \
            04_gold_mission_products; do
            "${FABRIC_CLI_BIN}" job run \
                "${WORKSPACE_PATH}/03-star-schema-bi.Folder/${item_name}.Notebook" \
                --timeout "${timeout}" \
                --polling_interval 15
        done
        refresh_demo_03_items
        ;;
    refresh-demo-03-items)
        require_fab
        refresh_demo_03_items
        ;;
    push-demo-04)
        require_fab
        provision_lakehouses
        push_shared_data
        push_demo_04_realtime_items
        for file in \
            "${DEMO_04_DIR}/notebooks/01_connect_streaming_sources.ipynb" \
            "${DEMO_04_DIR}/notebooks/02_build_streaming_measures.ipynb" \
            "${DEMO_04_DIR}/notebooks/03_apply_finding_rules.ipynb" \
            "${DEMO_04_DIR}/notebooks/04_publish_test_findings.ipynb"; do
            push_notebook "${file}"
        done
        push_demo_04_items
        ;;
    run-demo-04)
        require_fab
        timeout="${1:-1800}"
        for item_name in \
            01_connect_streaming_sources \
            02_build_streaming_measures \
            03_apply_finding_rules \
            04_publish_test_findings; do
            "${FABRIC_CLI_BIN}" job run \
                "${WORKSPACE_PATH}/04-real-time-ingestion.Folder/${item_name}.Notebook" \
                --timeout "${timeout}" \
                --polling_interval 15
        done
        ;;
    refresh-demo-04-items)
        require_fab
        refresh_demo_04_items
        ;;
    push-demo-05)
        require_fab
        provision_lakehouses
        upload_file \
            "${DATA_PRODUCT_DIR}/projections/model-governance/readiness_observation_features.csv" \
            "readiness_observation_features.csv"
        for file in \
            "${DEMO_05_DIR}/notebooks/01_readiness_feature_engineering.ipynb" \
            "${DEMO_05_DIR}/notebooks/02_readiness_model_sklearn.ipynb" \
            "${DEMO_05_DIR}/notebooks/03_readiness_model_lightgbm.ipynb" \
            "${DEMO_05_DIR}/notebooks/04_model_comparison.ipynb" \
            "${DEMO_05_DIR}/notebooks/05_governed_batch_scoring.ipynb" \
            "${DEMO_05_DIR}/notebooks/06_readiness_drift_monitoring.ipynb"; do
            push_notebook "${file}"
        done
        push_demo_05_items
        ;;
    run-demo-05)
        require_fab
        timeout="${1:-1800}"
        for item_name in \
            01_readiness_feature_engineering \
            02_readiness_model_sklearn \
            03_readiness_model_lightgbm \
            04_model_comparison \
            05_governed_batch_scoring \
            06_readiness_drift_monitoring; do
            "${FABRIC_CLI_BIN}" job run \
                "${WORKSPACE_PATH}/05-ml-models.Folder/${item_name}.Notebook" \
                --timeout "${timeout}" \
                --polling_interval 15
        done
        request_semantic_model_refresh \
            "${WORKSPACE_PATH}/05-ml-models.Folder/MDA Readiness Model Governance.SemanticModel"
        ;;
    push-demo-06)
        require_fab
        provision_lakehouses
        for file in \
            "${DEMO_06_DIR}/Ontology/fabriciq_ontology_accelerator-0.1.0-py3-none-any.whl" \
            "${DEMO_06_DIR}/Ontology/mda_test_ontology.iq"; do
            relative_path="${file#"${REPO_ROOT}/"}"
            upload_file "${file}" "${relative_path}"
        done
        for file in \
            "${DEMO_06_DIR}/Notebook/Validate MDA Test Ontology Bindings.ipynb" \
            "${DEMO_06_DIR}/Notebook/Create MDA Test Ontology from Package.ipynb"; do
            push_notebook "${file}"
        done
        ;;
    run-demo-06)
        require_fab
        timeout="${1:-1800}"
        for item_name in \
            "Validate MDA Test Ontology Bindings" \
            "Create MDA Test Ontology from Package"; do
            "${FABRIC_CLI_BIN}" job run \
                "${WORKSPACE_PATH}/06-ai-data-agent.Folder/${item_name}.Notebook" \
                --timeout "${timeout}" \
                --polling_interval 15
        done
        ;;
    push-all)
        require_fab
        provision_lakehouses
        mapfile -d '' demo_directories < <(
            find "${REPO_ROOT}/fabric-demos" \
                -mindepth 1 \
                -maxdepth 1 \
                -type d \
                -name '[0-9][0-9]*' \
                -print0 |
                sort -z
        )
        for directory in "${demo_directories[@]}"; do
            folder_name="$(basename "${directory}")"
            ensure_workspace_folder "${folder_name}"
        done
        push_shared_data
        push_demo_04_realtime_items
        upload_file \
            "${DATA_PRODUCT_DIR}/projections/model-governance/readiness_observation_features.csv" \
            "readiness_observation_features.csv"
        for file in \
            "${DEMO_06_DIR}/Ontology/fabriciq_ontology_accelerator-0.1.0-py3-none-any.whl" \
            "${DEMO_06_DIR}/Ontology/mda_test_ontology.iq"; do
            relative_path="${file#"${REPO_ROOT}/"}"
            upload_file "${file}" "${relative_path}"
        done
        push_all_notebooks
        push_demo_03_items
        push_demo_04_items
        push_demo_05_items
        ;;
    pull-demo-03)
        require_fab
        output_directory="${1:-${REPO_ROOT}/.fabric-export/demo-03}"
        mkdir -p "${output_directory}"
        for item_name in \
            01_bronze_ingest \
            02_silver_canonicalize \
            03_gold_test_products; do
            "${FABRIC_CLI_BIN}" export "${WORKSPACE_PATH}/03-star-schema-bi.Folder/${item_name}.Notebook" \
                --output "$(cli_path "${output_directory}")" \
                --format .ipynb \
                --force
        done
        ;;
    run-notebook)
        require_fab
        require_argument "${1:-}" "item-name"
        "${FABRIC_CLI_BIN}" job run "${WORKSPACE_PATH}/$1.Notebook" \
            --timeout "${2:-1800}" \
            --polling_interval 15
        ;;
    help|-h|--help)
        usage
        ;;
    *)
        echo "Unknown command: ${command}" >&2
        usage >&2
        exit 2
        ;;
esac
