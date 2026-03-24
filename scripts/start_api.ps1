param(
    [string]$RedisHost = "127.0.0.1",
    [int]$RedisPort = 6379,
    [string]$RedisPassword = "",
    [string]$Host = "127.0.0.1",
    [int]$Port = 8000
)

$env:ALGOHLPER_TASK_QUEUE_BACKEND = "celery"
$env:ALGOHLPER_REDIS_HOST = $RedisHost
$env:ALGOHLPER_REDIS_PORT = "$RedisPort"
if ($RedisPassword) {
    $env:ALGOHLPER_REDIS_PASSWORD = $RedisPassword
}

Write-Host "Starting API with Redis $RedisHost`:$RedisPort ..."
uvicorn algohlper.api.app:app --app-dir src --host $Host --port $Port --reload
