param(
    [string]$ApiBaseUrl = "http://127.0.0.1:8000",
    [int]$Port = 3000
)

$env:NEXT_PUBLIC_API_BASE_URL = $ApiBaseUrl

Write-Host "Starting web app with API base $ApiBaseUrl ..."
Push-Location "$PSScriptRoot\\..\\apps\\web"
try {
    npm run dev -- --port $Port
}
finally {
    Pop-Location
}
