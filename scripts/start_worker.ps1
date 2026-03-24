param(
    [string]$RedisHost = "127.0.0.1",
    [int]$RedisPort = 6379,
    [string]$RedisPassword = "",
    [string]$Pool = "solo",
    [string]$LogLevel = "info"
)

$env:ALGOHLPER_TASK_QUEUE_BACKEND = "celery"
$env:ALGOHLPER_REDIS_HOST = $RedisHost
$env:ALGOHLPER_REDIS_PORT = "$RedisPort"
$env:ALGOHLPER_CELERY_WORKER_POOL = $Pool
if ($RedisPassword) {
    $env:ALGOHLPER_REDIS_PASSWORD = $RedisPassword
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$pythonCmd = if (Test-Path $venvPython) { $venvPython } else { "python" }

Write-Host "Starting Celery worker with Redis $RedisHost`:$RedisPort and pool=$Pool ..."
Push-Location $repoRoot
try {
    & $pythonCmd -c "import celery" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Celery 未安装，正在安装 queue 依赖..."
        & $pythonCmd -m pip install -e .[queue]
        if ($LASTEXITCODE -ne 0) {
            throw "安装 Celery 依赖失败。"
        }
    }

    & $pythonCmd -m celery -A algohlper.worker.tasks.celery_app worker --loglevel=$LogLevel --pool=$Pool
}
finally {
    Pop-Location
}
