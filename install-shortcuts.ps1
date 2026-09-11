$ErrorActionPreference = 'Stop'
$exe = Join-Path $PSScriptRoot 'dist\ACQuotaScreen\ACQuotaScreen.exe'
if (!(Test-Path -LiteralPath $exe)) { throw 'Build the desktop EXE first' }
$shell = New-Object -ComObject WScript.Shell
$name = 'AC ' + [char]0x526f + [char]0x5c4f
foreach ($folder in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
    $link = $shell.CreateShortcut((Join-Path $folder ($name + '.lnk')))
    $link.TargetPath = $exe
    $link.WorkingDirectory = $PSScriptRoot
    $link.Description = 'AC Quota Screen'
    $link.Save()
}
