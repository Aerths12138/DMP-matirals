param(
    [ValidateSet("demo", "postgres")]
    [string]$Source = "demo",
    [switch]$FullRefresh
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker Desktop is required. Install Docker, then rerun this script."
    }

    $composeFiles = @(
        "-f", "docker-compose.yml",
        "-f", "lakehouse/compose.lakehouse.yml"
    )
    $services = @("spark-master", "spark-worker", "spark-history")
    if ($Source -eq "postgres") {
        $services = @("postgres") + $services
    }
    & docker compose @composeFiles up -d --build @services
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to start the lakehouse services."
    }

    $jobCommand = @(
        "/opt/spark/bin/spark-submit",
        "--master", "spark://spark-master:7077",
        "--conf", "spark.driver.host=spark-submit",
        "/opt/materials-dmp/lakehouse/jobs/pipeline.py",
        "--source", $Source
    )
    if ($FullRefresh) {
        $jobCommand += "--full-refresh"
    }
    & docker compose @composeFiles run --rm --use-aliases spark-submit @jobCommand
    if ($LASTEXITCODE -ne 0) {
        throw "The Spark pipeline failed. Inspect http://localhost:8081 and http://localhost:18080."
    }
}
finally {
    Pop-Location
}

