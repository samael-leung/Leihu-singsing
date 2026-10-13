param([Parameter(Mandatory=$true)][string]$Workspace)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot '../setup/clean-uninstall.ps1') -FunctionsOnly
$fixture=Join-Path $Workspace ('cleanup-test-' + [Guid]::NewGuid().ToString('N'))
$null=New-Item -ItemType Directory -Path $fixture
$env:USERPROFILE=Join-Path $fixture 'user'
$env:LOCALAPPDATA=Join-Path $fixture 'local'
$null=New-Item -ItemType Directory -Path $env:USERPROFILE,$env:LOCALAPPDATA
$env:OLLAMA_MODELS=''
$script:fakeExe=$null
function Find-Ollama { return $script:fakeExe }
$script:checks=0
function Assert([bool]$Condition,[string]$Message) {
    if (!$Condition) { throw $Message }
    $script:checks++
}
function Fixture([string]$Name) {
    $root=Join-Path $fixture $Name
    $null=New-Item -ItemType Directory -Path $root
    foreach ($file in @('app.py','desktop.py','VERSION')) { Set-Content -LiteralPath (Join-Path $root $file) -Value 'fixture' }
    return $root
}
try {
    $root=Fixture 'preserve'
    $null=New-Item -ItemType Directory -Path (Join-Path $root 'python/site-packages'),(Join-Path $root 'models'),(Join-Path $root 'library')
    Set-Content (Join-Path $root 'python/site-packages/package.py') 'test'
    Set-Content (Join-Path $root 'models/model.onnx') 'test'
    Set-Content (Join-Path $root 'library/song.wav') 'test'
    Set-Content (Join-Path $root 'config.json') '{"openai_api_key":"fixture-secret"}'
    Set-Content (Join-Path $root 'unrelated.txt') 'unrelated user file'
    $plan=Get-CleanupPlan $root $false
    Remove-AppFiles $plan $true
    Assert (!(Test-Path (Join-Path $root 'python'))) 'Packages were not removed'
    Assert (!(Test-Path (Join-Path $root 'models'))) 'Audio models were not removed'
    Assert (Test-Path (Join-Path $root 'library/song.wav')) 'User recordings were deleted'
    Assert (Test-Path (Join-Path $root 'config.json')) 'API config was deleted despite keep-data'
    Assert (Test-Path (Join-Path $root 'unrelated.txt')) 'Unrelated user files were deleted'

    $root=Fixture 'purge'
    $null=New-Item -ItemType Directory -Path (Join-Path $root 'library')
    Set-Content (Join-Path $root 'library/song.wav') 'test'
    Set-Content (Join-Path $root 'config.json') '{}'
    Remove-AppFiles (Get-CleanupPlan $root $false) $false
    Assert (!(Test-Path $root)) 'Explicit full-data cleanup left app files'

    $root=Fixture 'links'
    $outside=Join-Path $fixture 'outside'; $null=New-Item -ItemType Directory -Path $outside
    Set-Content (Join-Path $outside 'keep.txt') 'outside file'
    $null=New-Item -ItemType Directory -Path (Join-Path $root 'python')
    $linkType='SymbolicLink'
    if ([Environment]::OSVersion.Platform -eq 'Win32NT') { $linkType='Junction' }
    $null=New-Item -ItemType $linkType -Path (Join-Path $root 'python/linked-folder') -Target $outside
    Remove-AppFiles (Get-CleanupPlan $root $false) $false
    Assert (Test-Path (Join-Path $outside 'keep.txt')) 'Nested link cleanup traversed its target'

    $root=Fixture 'repository'; $null=New-Item -ItemType Directory -Path (Join-Path $root '.git')
    $blocked=$false; try { $null=Get-CleanupPlan $root $false } catch { $blocked=$true }
    Assert $blocked 'Repository checkout was accepted for deletion'
    $blocked=$false; try { $null=Get-CleanupPlan $env:USERPROFILE $false } catch { $blocked=$true }
    Assert $blocked 'User home was accepted for deletion'

    $root=Fixture 'app-local'; $script:fakeExe='existing-ollama.exe'
    Set-Content (Join-Path $root 'config.json') '{"ollama_url":"http://127.0.0.1:11434","ollama_model":"custom:14b"}'
    $plan=Get-CleanupPlan $root $true
    Assert ($plan.Models.Count -eq 1 -and $plan.Models[0] -eq 'custom:14b') 'Configured local model was not planned'
    Set-Content (Join-Path $root 'config.json') '{"ollama_url":"https://remote.example","ollama_model":"custom:14b"}'
    Assert ((Get-CleanupPlan $root $true).Models.Count -eq 0) 'Remote model was included in destructive plan'

    Set-Content (Join-Path $root 'config.json') '{"ollama_url":"http://127.0.0.1:11434","ollama_model":"custom:14b"}'
    $plan=Get-CleanupPlan $root $true
    $script:removed=@(); $script:tagModels=@('custom:14b','unrelated:8b')
    function Ensure-Ollama([string]$Base) {}
    function Get-OllamaTags([string]$Base) { return @{models=@($script:tagModels | ForEach-Object { @{name=$_} })} }
    function Invoke-RestMethod {
        param($Uri,$Method,$ContentType,$Body,$TimeoutSec)
        if ($Method -ne 'Delete') { throw 'Unexpected request' }
        $name=($Body | ConvertFrom-Json).model
        $script:removed += $name
        $script:tagModels=@($script:tagModels | Where-Object { $_ -ne $name })
        return @{}
    }
    $remaining=@(Remove-AppModels $plan)
    Assert ($script:removed.Count -eq 1 -and $script:removed[0] -eq 'custom:14b') 'Cleanup removed unrelated model'
    Assert ($remaining.Count -eq 1 -and $remaining[0] -eq 'unrelated:8b') 'Shared model was not preserved'
    $plan.Ownership=@{installed_by_app=$true;install_dir=(Join-Path $env:LOCALAPPDATA 'Programs/Ollama')}
    function Start-Process { throw 'Shared Ollama runtime must not be uninstalled' }
    Remove-OllamaRuntime $plan $true @() # Must refresh inventory rather than trust an empty list.
    Assert ($script:tagModels.Count -eq 1) 'Shared runtime inventory changed'

    $script:tagModels=@(); $plan.Ownership=$null
    $cache=Join-Path $env:USERPROFILE '.ollama/models'
    $null=New-Item -ItemType Directory -Path (Join-Path $cache 'manifests'),(Join-Path $cache 'blobs')
    Set-Content (Join-Path $cache 'manifests/other-model') 'manifest'
    Set-Content (Join-Path $cache 'blobs/partial-download') 'partial'
    Set-Content (Join-Path $cache 'notes.txt') 'unrelated user file'
    Remove-OllamaRuntime $plan $true @()
    Assert (Test-Path (Join-Path $cache 'manifests/other-model')) 'Cache manifest from another API instance was deleted'
    Remove-Item (Join-Path $cache 'manifests/other-model')
    Remove-OllamaRuntime $plan $false @()
    Assert (Test-Path (Join-Path $cache 'blobs/partial-download')) 'Unselected shared runtime cleanup deleted blobs'
    $runtime=Join-Path $env:LOCALAPPDATA 'Programs/Ollama'; $null=New-Item -ItemType Directory -Path $runtime
    Set-Content (Join-Path $runtime 'unins000.exe') 'fixture'
    $script:uninstalls=0
    function Start-Process { param($FilePath,$ArgumentList,[switch]$Wait,[switch]$PassThru); $script:uninstalls++; return @{ExitCode=0} }
    Remove-OllamaRuntime $plan $true @()
    Assert ($script:uninstalls -eq 1) 'Explicit legacy runtime uninstall was not executed'
    Assert (!(Test-Path (Join-Path $cache 'blobs'))) 'Orphan partial model blobs were not cleaned'
    Assert (Test-Path (Join-Path $cache 'notes.txt')) 'Unknown file in model cache was deleted'

    $root=Fixture 'retry'
    $state=@{app='LeihuLiantai';root=$root;base='http://127.0.0.1:11434';models=@();models_cleaned=$true;runtime_cleaned=$true}
    $state | ConvertTo-Json | Set-Content (Join-Path $root 'cleanup-state.json')
    Remove-Item (Join-Path $root 'app.py'),(Join-Path $root 'desktop.py'),(Join-Path $root 'VERSION')
    Assert ((Get-CleanupPlan $root $false).State.models_cleaned) 'Partially finished cleanup cannot resume'
    Assert (Test-AppShortcutTarget 'C:\App' 'C:\App\python\pythonw.exe' '') 'Own application shortcut was not recognized'
    Assert (!(Test-AppShortcutTarget 'C:\App' 'C:\App-other\python\pythonw.exe' '')) 'Another installation shortcut would be deleted'
    Write-Output "Cleanup functional checks passed: $script:checks"
} finally {
    Remove-SafeTree $fixture
}
