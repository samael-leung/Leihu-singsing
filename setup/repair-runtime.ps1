# Run after installing the patched Python 3.13 from the official winget source.
param([string]$AppDir = (Split-Path $PSScriptRoot -Parent))
$ErrorActionPreference = "Stop"
$AppDir = (Resolve-Path $AppDir).Path
if (-not (Test-Path "$AppDir\installer.py")) { throw "Select the Leihu installation directory." }
$running = Get-CimInstance Win32_Process | Where-Object {
    $_.ExecutablePath -like "$AppDir\python\*" -or $_.ExecutablePath -like "$AppDir\secure-runtime\*"
}
if ($running) { throw "Save recordings and close Leihu before migrating Python." }
& py -3.13 -c "import sys; assert sys.version_info >= (3,13,17), 'Python 3.13.17 or later is required'; assert sys.maxsize > 2**32, '64-bit Python is required'"
if ($LASTEXITCODE -ne 0) { throw "Install or upgrade Python.Python.3.13 with winget first." }
$runtime = Join-Path $AppDir "secure-runtime"
$marker = Join-Path $runtime "leihu-ready.json"
Remove-Item $marker -Force -ErrorAction SilentlyContinue
& py -3.13 -m venv --upgrade $runtime
if ($LASTEXITCODE -ne 0) { throw "Could not prepare the separate Python environment." }
$python = Join-Path $runtime "Scripts\python.exe"
& $python -c "import sys; assert sys.version_info >= (3,13,17); print(sys.version)"
if ($LASTEXITCODE -ne 0) { throw "The new environment does not use the patched Python." }
& $python -m pip install --upgrade "pip>=26.2.2" "certifi>=2026.10.19" "pillow==13.0.0"
if ($LASTEXITCODE -ne 0) { throw "Security package installation failed." }
$installed = Join-Path $AppDir "installed.json"
$previous = if (Test-Path $installed) { [IO.File]::ReadAllBytes($installed) } else { $null }
try {
    Push-Location $AppDir
    try { & $python "$AppDir\installer.py" --repair } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw "Dependency repair failed. The previous Python is still retained." }
} catch {
    if ($null -ne $previous) { [IO.File]::WriteAllBytes($installed, $previous) }
    throw
}
@{ python = (& $python -c "import platform; print(platform.python_version())"); ready = $true } |
    ConvertTo-Json | Set-Content -Path $marker -Encoding UTF8
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "Leihu - Updated Python.lnk"))
$shortcut.TargetPath = Join-Path $runtime "Scripts\pythonw.exe"
$shortcut.Arguments = '"' + (Join-Path $AppDir "desktop.py") + '"'
$shortcut.WorkingDirectory = $AppDir
$shortcut.IconLocation = Join-Path $AppDir "static\icon.ico"
$shortcut.Save()
Write-Host "Completed. Use the 'Leihu - Updated Python' desktop shortcut. Songs and the previous Python were retained."
