$ErrorActionPreference = 'Stop'
$server = Join-Path $PSScriptRoot 'server.py'
$url = 'http://127.0.0.1:8767/'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$digest = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($root))).ToLower().Substring(0,16)
try {
    $health = Invoke-RestMethod ($url + 'api/health') -TimeoutSec 2
    if ($health.app -eq 'monogrowlab-local-web' -and $health.project_id -eq $digest) {
        Start-Process $url
        Write-Output 'The existing workbench is running. Opened it in your browser.'
        exit 0
    }
    throw 'Port 8767 is used by a different application. Nothing was stopped.'
} catch {
    if ($_.Exception.Message -like 'Port 8767*') {throw}
}
& py -3.13 -c 'import numpy, scipy, skimage, PIL'
if ($LASTEXITCODE -ne 0) {throw 'Python 3.13 with the existing project dependencies is required. No packages were changed.'}
$env:PYTHONDONTWRITEBYTECODE='1'
& py -3.13 -u $server --project-root $root --port 8767 --open-browser
if ($LASTEXITCODE -ne 0) {throw ('Workbench exited with code ' + $LASTEXITCODE)}
