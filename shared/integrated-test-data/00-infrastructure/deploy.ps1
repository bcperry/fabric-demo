#!/usr/bin/env pwsh

param(
    [Parameter(Mandatory = $true)]
    [string]$SubscriptionId,

    [Parameter(Mandatory = $true)]
    [string]$ExistingFabricCapacityId,

    [Parameter(Mandatory = $false)]
    [string]$ResourceGroupName = "rg-mda-fabric-demo",

    [Parameter(Mandatory = $false)]
    [string]$Location = "centralus",

    [Parameter(Mandatory = $false)]
    [string]$EnvironmentName = "dev",

    [Parameter(Mandatory = $false)]
    [string]$PostgresAdministratorLogin = "mdaadmin",

    [Parameter(Mandatory = $true)]
    [SecureString]$PostgresAdministratorPassword,

    [Parameter(Mandatory = $false)]
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$templateFile = Join-Path $scriptDirectory "main.bicep"

$account = az account show --output json 2>$null | ConvertFrom-Json
if (-not $account) {
    throw "Azure CLI is not authenticated. Run 'az login' with the MCAPS tenant account."
}

az account set --subscription $SubscriptionId
if ($LASTEXITCODE -ne 0) {
    throw "Unable to select subscription '$SubscriptionId'."
}

$account = az account show --output json | ConvertFrom-Json
$operator = az ad signed-in-user show --output json | ConvertFrom-Json
if (-not $operator.id) {
    throw "Unable to resolve the signed-in user's object ID."
}

az bicep build --file $templateFile
if ($LASTEXITCODE -ne 0) {
    throw "Bicep build failed."
}

if ($WhatIf) {
    $resourceGroupExists = az group exists --name $ResourceGroupName --output tsv
    if ($LASTEXITCODE -ne 0 -or $resourceGroupExists -ne "true") {
        throw "What-if requires an existing resource group named '$ResourceGroupName'."
    }
} else {
    az group create `
        --name $ResourceGroupName `
        --location $Location `
        --tags environment=$EnvironmentName project=mda-integrated-test-operations workload=fabric-demo classification=synthetic-unclass `
        --output none
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to create or update resource group '$ResourceGroupName'."
    }
}

$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($PostgresAdministratorPassword)
try {
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)

    $arguments = @(
        "deployment", "group", $(if ($WhatIf) { "what-if" } else { "create" }),
        "--resource-group", $ResourceGroupName,
        "--template-file", $templateFile,
        "--parameters",
        "environmentName=$EnvironmentName",
        "location=$Location",
        "tenantId=$($account.tenantId)",
        "operatorPrincipalId=$($operator.id)",
        "operatorPrincipalType=User",
        "existingFabricCapacityId=$ExistingFabricCapacityId",
        "postgresAdministratorLogin=$PostgresAdministratorLogin",
        "postgresAdministratorPassword=$plainPassword",
        "--output", "json"
    )

    $result = & az @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Infrastructure deployment failed."
    }

    if (-not $WhatIf) {
        $deployment = $result | ConvertFrom-Json
        $deployment.properties.outputs | ConvertTo-Json -Depth 5
    }
}
finally {
    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
    $plainPassword = $null
}
