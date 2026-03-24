param(
    [string]$RedisHost = "127.0.0.1",
    [int]$RedisPort = 6379,
    [string]$RedisPassword = "",
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8000
)

$env:ALGOHLPER_TASK_QUEUE_BACKEND = "celery"
$env:ALGOHLPER_REDIS_HOST = $RedisHost
$env:ALGOHLPER_REDIS_PORT = "$RedisPort"
if ($RedisPassword) {
    $env:ALGOHLPER_REDIS_PASSWORD = $RedisPassword
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$pythonCmd = if (Test-Path $venvPython) { $venvPython } else { "python" }

Write-Host "Starting API with Redis $RedisHost`:$RedisPort ..."
Push-Location $repoRoot
try {
    & $pythonCmd -m uvicorn algohlper.api.app:app --app-dir src --host $BindHost --port $Port --reload
}
finally {
    Pop-Location
}
