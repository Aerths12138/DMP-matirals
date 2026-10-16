param(
    [string]$SqlFile = ""
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
    $sqlCommand = @(
        "/opt/spark/bin/spark-sql",
        "--master", "spark://spark-master:7077",
        "--conf", "spark.driver.host=spark-submit"
    )
    if ($SqlFile) {
        $resolved = Resolve-Path -LiteralPath $SqlFile
        $lakehouseRoot = Resolve-Path -LiteralPath $PSScriptRoot
        if (-not $resolved.Path.StartsWith($lakehouseRoot.Path, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "SqlFile must be inside the lakehouse directory so it is available in the container."
        }
        $relative = $resolved.Path.Substring($lakehouseRoot.Path.Length).TrimStart("\")
        $containerPath = "/opt/materials-dmp/lakehouse/" + $relative.Replace("\", "/")
        $sqlCommand += @("-f", $containerPath)
    }
    & docker compose @composeFiles run --rm --use-aliases spark-submit @sqlCommand
    if ($LASTEXITCODE -ne 0) {
        throw "Spark SQL exited with an error."
    }
}
finally {
    Pop-Location
}

