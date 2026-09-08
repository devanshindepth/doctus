# Deploy Doctus Studio (FastAPI + React SPA) to Google Cloud Run (PowerShell)
# Usage:
#   $env:GOOGLE_CLOUD_PROJECT="your-project-id"
#   .\deploy\deploy_cloud_run.ps1

param(
    [string]$ProjectId = $env:GOOGLE_CLOUD_PROJECT,
    [string]$Region = "us-central1",
    [string]$ServiceName = "doctus-studio",
    [string]$RepoName = "doctus"
)

if (-not $ProjectId) {
    Write-Error "Please provide -ProjectId or set `$env:GOOGLE_CLOUD_PROJECT."
    exit 1
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Deploying Doctus Studio to Google Cloud Run" -ForegroundColor Cyan
Write-Host "  Project:  $ProjectId"
Write-Host "  Region:   $Region"
Write-Host "  Service:  $ServiceName"
Write-Host "=========================================================="

Write-Host "`n--> Enabling required Google Cloud APIs..." -ForegroundColor Yellow
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com --project=$ProjectId

Write-Host "`n--> Submitting Cloud Build container build..." -ForegroundColor Yellow
gcloud builds submit `
    --project=$ProjectId `
    --substitutions="_AR_REGION=$Region,_AR_REPO=$RepoName,_DEPLOY_REGION=$Region" `
    --config=deploy/cloudrun/cloudbuild.yaml `
    .

Write-Host "`n--> Fetching deployed Service URL..." -ForegroundColor Yellow
$serviceUrl = gcloud run services describe $ServiceName --platform=managed --region=$Region --project=$ProjectId --format="value(status.url)"

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  🎉 Doctus Studio Successfully Deployed to Google Cloud!" -ForegroundColor Green
Write-Host "  URL: $serviceUrl" -ForegroundColor Green
Write-Host "=========================================================="
