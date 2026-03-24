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

Write-Host "Starting Celery worker with Redis $RedisHost`:$RedisPort and pool=$Pool ..."
celery -A algohlper.worker.tasks.celery_app worker --loglevel=$LogLevel --pool=$Pool
