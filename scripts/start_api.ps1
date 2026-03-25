param(
    [ValidateSet("inprocess", "celery")]
    [string]$Backend = "inprocess",
    [string]$RedisHost = "127.0.0.1",
    [int]$RedisPort = 6379,
    [string]$RedisPassword = "",
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8000
)

$env:ALGOHLPER_TASK_QUEUE_BACKEND = $Backend

if ($Backend -eq "celery") {
    $env:ALGOHLPER_REDIS_HOST = $RedisHost
    $env:ALGOHLPER_REDIS_PORT = "$RedisPort"
    if ($RedisPassword) {
        $env:ALGOHLPER_REDIS_PASSWORD = $RedisPassword
    }
    elseif (Test-Path Env:ALGOHLPER_REDIS_PASSWORD) {
        Remove-Item Env:ALGOHLPER_REDIS_PASSWORD
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$pythonCmd = if (Test-Path $venvPython) { $venvPython } else { "python" }

if ($Backend -eq "celery") {
    Write-Host "Starting API with backend celery (Redis $RedisHost`:$RedisPort) ..."
}
else {
    Write-Host "Starting API with backend inprocess ..."
}

Push-Location $repoRoot
try {
    & $pythonCmd -m uvicorn algohlper.api.app:app --app-dir src --host $BindHost --port $Port --reload
}
finally {
    Pop-Location
}
