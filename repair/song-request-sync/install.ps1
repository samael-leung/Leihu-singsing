param([string]$ProjectDir = 'E:\songRequest', [switch]$Undo)
$ErrorActionPreference = 'Stop'
Get-Command node -ErrorAction Stop | Out-Null
if (Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue) {
    throw 'Stop the song-request server with Ctrl+C first. Port 3000 is still listening; no files were changed.'
}
if ($Undo) { & node "$PSScriptRoot\install.js" $ProjectDir --undo }
else { & node "$PSScriptRoot\install.js" $ProjectDir }
if ($LASTEXITCODE -ne 0) { throw 'Repair did not complete. Read the message above.' }
