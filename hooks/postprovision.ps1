#!/usr/bin/env pwsh
Write-Host "Writing azd environment values to .env file..."
azd env get-values > .env
Write-Host "Done. Environment values written to .env"
