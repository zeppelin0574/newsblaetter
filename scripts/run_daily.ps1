$ErrorActionPreference = "Stop"

Set-Location -Path (Split-Path -Parent $PSScriptRoot)

& (Join-Path $PSScriptRoot "run_morning.ps1")
