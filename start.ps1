$ErrorActionPreference = 'Stop'
$desktop = Join-Path $PSScriptRoot 'dist\ACQuotaScreen\ACQuotaScreen.exe'
if (Test-Path -LiteralPath $desktop) {
    Start-Process -FilePath $desktop -WindowStyle Hidden
    exit
}
$python = Join-Path $PSScriptRoot '..\.venv\Scripts\pythonw.exe'
if (!(Test-Path -LiteralPath $python)) { throw 'Python environment missing' }
Start-Process -FilePath $python -ArgumentList ('"' + (Join-Path $PSScriptRoot 'app.py') + '"') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
$runtimePath = Join-Path $env:LOCALAPPDATA 'ACQuotaScreen\runtime.json'
for ($i=0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $runtime = Get-Content -LiteralPath $runtimePath | ConvertFrom-Json
        $url = 'http://127.0.0.1:' + $runtime.port
        $null = Invoke-RestMethod ($url + '/api/state') -TimeoutSec 2
        Start-Process $url
        exit
    } catch { }
}
throw 'App did not become ready. Check the local server log.'
