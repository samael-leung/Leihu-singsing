#Requires -Version 5.1
param([string]$AppDir = '', [switch]$LocalModel, [switch]$HybridAI, [switch]$FunctionsOnly)
$ErrorActionPreference = 'Stop'

function Read-Object([string]$Path) {
    if (!(Test-Path -LiteralPath $Path)) { return $null }
    return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Get-CleanupPlan([string]$Root, [bool]$IncludeLocalModel, [bool]$HybridMode = $false) {
    $full = [IO.Path]::GetFullPath($Root).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    $forbidden = @([IO.Path]::GetPathRoot($full).TrimEnd('\','/'), $env:USERPROFILE,
                   $env:LOCALAPPDATA, $env:APPDATA, $env:WINDIR, $env:ProgramFiles,
                   (Join-Path $env:LOCALAPPDATA 'Programs'), (Join-Path $env:USERPROFILE 'Desktop'),
                   (Join-Path $env:USERPROFILE 'Documents'), (Join-Path $env:USERPROFILE 'Downloads'))
    $state=Read-Object (Join-Path $full 'cleanup-state.json')
    $resuming=($state -and $state.app -eq 'LeihuLiantai' -and $state.root -eq $full)
    $identity=((Test-Path -LiteralPath (Join-Path $full 'app.py')) -and
               (Test-Path -LiteralPath (Join-Path $full 'desktop.py')) -and
               (Test-Path -LiteralPath (Join-Path $full 'VERSION')))
    if ($full -in $forbidden -or (Test-Path -LiteralPath (Join-Path $full '.git')) -or (!$identity -and !$resuming)) {
        throw '找不到有效的練唱台安裝目錄，或目錄不適合自動清理。請指定安裝資料夾。'
    }
    if ((Get-Item -LiteralPath $full -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw '安裝目錄是連結，請使用實際安裝目錄。'
    }
    $cfg = Read-Object (Join-Path $full 'config.json')
    $owned = Read-Object (Join-Path $full 'ollama-install.json')
    if (!$owned -and $resuming) { $owned=$state.ownership }
    $base = 'http://127.0.0.1:11434'
    if ($resuming -and $state.base) { $base=[string]$state.base }
    if ($cfg -and $cfg.ollama_url) { $base = [string]$cfg.ollama_url }
    $uri = [Uri]$base
    $loopback = ($uri.Scheme -eq 'http' -and $uri.DnsSafeHost -in @('localhost','127.0.0.1','::1','[::1]') -and
                 !$uri.UserInfo -and !$uri.Query -and !$uri.Fragment -and $uri.AbsolutePath -eq '/')
    $models = @()
    $modelDir=Join-Path $env:USERPROFILE '.ollama\models'
    if ($env:OLLAMA_MODELS) { $modelDir=$env:OLLAMA_MODELS }
    $hasOllama=($owned -or (Find-Ollama) -or (Test-Path -LiteralPath $modelDir))
    if ($loopback -and $hasOllama -and ($IncludeLocalModel -or $owned -or ($cfg -and $cfg.ollama_model))) {
        if ($resuming) { $models += @($state.models) }
        if ($owned) { $models += @($owned.models) }
        if ($cfg -and $cfg.ollama_model -and (!$HybridMode -or ($cfg.ai_mode -eq 'local' -and $cfg.ai_setup_complete))) { $models += [string]$cfg.ollama_model }
        elseif ($IncludeLocalModel -and !$HybridMode) { $models += 'qwen2.5:14b' }
    }
    $models = @($models | Where-Object { $_ } | Select-Object -Unique)
    foreach ($model in $models) {
        if ($model -notmatch '^[A-Za-z0-9][A-Za-z0-9._/:@-]*$') { throw '模型名稱不正確，停止自動移除。' }
    }
    return [PSCustomObject]@{ Root=$full; Base=$base.TrimEnd('/'); Models=$models; Ownership=$owned; IsLocal=$loopback; State=$state }
}

function Show-CleanupConfirmation($Plan) {
    Add-Type -AssemblyName System.Windows.Forms
    $form = New-Object Windows.Forms.Form
    $form.Text = '雷虎練唱台：一鍵完整移除'
    $form.Size = New-Object Drawing.Size(590,350)
    $form.StartPosition = 'CenterScreen'
    $form.FormBorderStyle = 'FixedDialog'; $form.MaximizeBox = $false; $form.MinimizeBox = $false
    $label = New-Object Windows.Forms.TextBox
    $label.Multiline=$true; $label.ReadOnly=$true; $label.ScrollBars='Vertical'; $label.WordWrap=$true
    $label.Location = New-Object Drawing.Point(18,18); $label.Size = New-Object Drawing.Size(540,170)
    $modelText = '無本機語言模型'
    if ($Plan.Models.Count) { $modelText = $Plan.Models -join ', ' }
    $label.Text = "將關閉練唱台並刪除其 Python 套件、音訊模型、下載暫存、程式及捷徑。`r`n`r`n安裝位置：$($Plan.Root)`r`n`r`n同時刪除本機 AI 模型：$modelText`r`n其他 Ollama 模型、系統 Python 與顯示卡驅動會保留。"
    $keep = New-Object Windows.Forms.CheckBox
    $keep.Location = New-Object Drawing.Point(18,190); $keep.Size = New-Object Drawing.Size(540,24)
    $keep.Text = '保留歌曲庫、錄音與設定（含 API 金鑰）；取消勾選則一併刪除'; $keep.Checked = $true
    $runtime = New-Object Windows.Forms.CheckBox
    $runtime.Location = New-Object Drawing.Point(18,220); $runtime.Size = New-Object Drawing.Size(540,24)
    $runtime.Text = '同時解除安裝 Ollama 與模型下載暫存（沒有其他模型時）'
    $runtime.Checked = [bool]($Plan.Ownership -and $Plan.Ownership.installed_by_app)
    $runtime.Enabled = [bool]($Plan.IsLocal -and ($Plan.Models.Count -or $Plan.Ownership))
    if (!$runtime.Checked) { $runtime.Text += '；來源不明，預設保留' }
    $ok = New-Object Windows.Forms.Button
    $ok.Location = New-Object Drawing.Point(285,265); $ok.Size = New-Object Drawing.Size(155,30)
    $ok.Text = '清除並解除安裝'; $ok.DialogResult = 'OK'
    $cancel = New-Object Windows.Forms.Button
    $cancel.Location = New-Object Drawing.Point(450,265); $cancel.Size = New-Object Drawing.Size(105,30)
    $cancel.Text = '取消'; $cancel.DialogResult = 'Cancel'
    $form.Controls.AddRange(@($label,$keep,$runtime,$ok,$cancel)); $form.AcceptButton=$ok; $form.CancelButton=$cancel
    $result=$form.ShowDialog()
    $selection=[PSCustomObject]@{ Confirmed=($result -eq 'OK'); KeepData=$keep.Checked; RemoveRuntime=$runtime.Checked -and $runtime.Enabled }
    $form.Dispose()
    return $selection
}

function Find-Ollama {
    $exe = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
    if (Test-Path -LiteralPath $exe) { return $exe }
    $cmd=Get-Command ollama.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Get-OllamaTags([string]$Base) {
    return Invoke-RestMethod -Uri "$Base/api/tags" -TimeoutSec 5
}

function Ensure-Ollama([string]$Base) {
    try { $null=Get-OllamaTags $Base; return } catch {}
    $exe=Find-Ollama
    if (!$exe) { throw '找不到 Ollama，無法移除共用目錄中的模型。請啟動或修復 Ollama 後重試。' }
    $previous=$env:OLLAMA_HOST
    try {
        $env:OLLAMA_HOST=([Uri]$Base).Authority
        $null=Start-Process -FilePath $exe -ArgumentList 'serve' -WindowStyle Hidden -PassThru
    } finally { $env:OLLAMA_HOST=$previous }
    for ($attempt=0; $attempt -lt 30; $attempt++) {
        try { $null=Get-OllamaTags $Base; return } catch { Start-Sleep -Milliseconds 500 }
    }
    throw 'Ollama 啟動失敗，未刪除練唱台。請先啟動 Ollama 再重試。'
}

function Remove-AppModels($Plan) {
    if (!$Plan.Models.Count) { return @() }
    Ensure-Ollama $Plan.Base
    foreach ($model in $Plan.Models) {
        $tags=Get-OllamaTags $Plan.Base
        $names=@($tags.models | ForEach-Object { $_.name })
        $canonical=$model
        if (!$model.Contains(':')) { $canonical=$model + ':latest' }
        if ($model -in $names -or $canonical -in $names) {
            $null=Invoke-RestMethod -Uri "$($Plan.Base)/api/delete" -Method Delete -ContentType 'application/json' -Body (@{model=$model} | ConvertTo-Json -Compress) -TimeoutSec 120
        }
    }
    $remaining=@((Get-OllamaTags $Plan.Base).models | ForEach-Object { $_.name })
    foreach ($model in $Plan.Models) {
        $canonical=$model
        if (!$model.Contains(':')) { $canonical=$model + ':latest' }
        if ($model -in $remaining -or $canonical -in $remaining) { throw "模型 $model 尚未移除，請重試。" }
    }
    # Ollama deletes unreferenced blobs while preserving layers used by other models.
    return $remaining
}

function Remove-OllamaRuntime($Plan, [bool]$Selected, [string[]]$Remaining) {
    if (!$Selected -or $Remaining.Count -or !$Plan.IsLocal) { return }
    # Recheck even when no target models existed: never uninstall a shared runtime blindly.
    if (@((Get-OllamaTags $Plan.Base).models).Count) { return }
    $expected=[IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'Programs\Ollama'))
    if ($Plan.Ownership -and $Plan.Ownership.installed_by_app -and
        [IO.Path]::GetFullPath([string]$Plan.Ownership.install_dir) -ne $expected) { throw 'Ollama 安裝來源紀錄不符，停止自動移除。' }
    $modelDir=Join-Path $env:USERPROFILE '.ollama\models'
    if ($env:OLLAMA_MODELS) { $modelDir=$env:OLLAMA_MODELS }
    if ($Plan.Ownership -and $Plan.Ownership.model_dir) { $modelDir=[string]$Plan.Ownership.model_dir }
    $modelDir=[IO.Path]::GetFullPath($modelDir)
    $default=[IO.Path]::GetFullPath((Join-Path $env:USERPROFILE '.ollama\models'))
    $allowed=($modelDir -eq $default)
    if ($env:OLLAMA_MODELS) { $allowed=$allowed -or $modelDir -eq [IO.Path]::GetFullPath($env:OLLAMA_MODELS) }
    if (!$allowed -or $modelDir -in @($Plan.Root,$env:USERPROFILE,$env:LOCALAPPDATA,$env:WINDIR,[IO.Path]::GetPathRoot($modelDir)) -or
        (Test-Path -LiteralPath (Join-Path $modelDir '.git'))) { throw 'Ollama 模型目錄不適合自動清理。' }
    $manifests=Join-Path $modelDir 'manifests'
    # An API instance can use a different cache: preserve any manifests not deleted above.
    if ((Test-Path -LiteralPath $manifests) -and @(Get-ChildItem -LiteralPath $manifests -File -Recurse -Force).Count) { return }
    $uninstaller=Join-Path $expected 'unins000.exe'
    if (Test-Path -LiteralPath $uninstaller) {
        $result=Start-Process -FilePath $uninstaller -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART' -Wait -PassThru
        if ($result.ExitCode -notin @(0,3010)) { throw 'Ollama 解除安裝失敗，請重試。' }
    } elseif (Find-Ollama) {
        throw '找不到官方 Ollama 解除安裝程式。可取消勾選移除 Ollama，先清理練唱台。'
    }
    # This explicit option also handles orphan partial blobs left by older installers.
    foreach ($name in @('blobs','manifests')) { Remove-SafeTree (Join-Path $modelDir $name) }
    if ((Test-Path -LiteralPath $modelDir) -and !(Get-ChildItem -LiteralPath $modelDir -Force)) {
        Remove-Item -LiteralPath $modelDir -Force
    }
}

function Remove-SafeTree([string]$Path) {
    if (!(Test-Path -LiteralPath $Path)) { return }
    $item=Get-Item -LiteralPath $Path -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { $item.Delete(); return }
    if ($item.PSIsContainer) {
        foreach ($child in @(Get-ChildItem -LiteralPath $Path -Force)) { Remove-SafeTree $child.FullName }
    }
    Remove-Item -LiteralPath $Path -Force
}

function Remove-AppFiles($Plan, [bool]$KeepData) {
    # Never recurse through an arbitrary chosen root or follow directory junctions.
    $folders=@('python','.venv','models','downloads','bin','logs','static','setup','__pycache__','.webview')
    if (!$KeepData) { $folders += 'library' }
    foreach ($name in $folders) {
        $path=Join-Path $Plan.Root $name
        if (Test-Path -LiteralPath $path) {
            Remove-SafeTree $path
        }
    }
    $files=@('app.py','desktop.py','pipeline.py','share.py','ai_api.py','claude_api.py','ollama_setup.py','model_setup.py','installer.py',
             'VERSION','requirements.txt','requirements-win.txt','installed.json','ollama-install.json',
             '使用說明.html','版權與使用聲明.txt','uninstall.exe','clean-uninstall.exe')
    if (!$KeepData) { $files += @('config.json','usage.json','usage-local.json','usage-openai.json','usage-ai-choice.json') }
    foreach ($name in $files) {
        $path=Join-Path $Plan.Root $name
        for ($attempt=0; $attempt -lt 10; $attempt++) {
            try { if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }; break }
            catch { if ($attempt -eq 9) { throw }; Start-Sleep -Milliseconds 500 }
        }
    }
    if (!(Get-ChildItem -LiteralPath $Plan.Root -Force)) { Remove-Item -LiteralPath $Plan.Root -Force }
}

function Test-AppShortcutTarget([string]$Root,[string]$Target,[string]$Arguments) {
    $prefix=$Root.TrimEnd('\') + '\'
    return ($Target.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase) -or
            $Arguments.IndexOf($prefix,[StringComparison]::OrdinalIgnoreCase) -ge 0 -or
            $Arguments.IndexOf('"' + $Root + '"',[StringComparison]::OrdinalIgnoreCase) -ge 0)
}

function Remove-AppShortcuts([string]$Root) {
    $desktop=[Environment]::GetFolderPath('Desktop')
    $folder=Join-Path ([Environment]::GetFolderPath('Programs')) '雷虎練唱台'
    $paths=@((Join-Path $desktop '雷虎練唱台.lnk'),(Join-Path $desktop '雷虎練唱台 完整移除.lnk'))
    if (Test-Path -LiteralPath $folder) { $paths += @(Get-ChildItem -LiteralPath $folder -Filter '*.lnk' | ForEach-Object { $_.FullName }) }
    $shell=New-Object -ComObject WScript.Shell
    try {
        foreach ($path in $paths) {
            if (Test-Path -LiteralPath $path) {
                $shortcut=$shell.CreateShortcut($path)
                if (Test-AppShortcutTarget $Root $shortcut.TargetPath $shortcut.Arguments) { Remove-Item -LiteralPath $path -Force }
                [Runtime.InteropServices.Marshal]::ReleaseComObject($shortcut) | Out-Null
            }
        }
        if ((Test-Path -LiteralPath $folder) -and !(Get-ChildItem -LiteralPath $folder -Force)) { Remove-Item -LiteralPath $folder -Force }
    } finally { [Runtime.InteropServices.Marshal]::ReleaseComObject($shell) | Out-Null }
}

function Invoke-Cleanup($Plan, $Selection) {
    $state=@{app='LeihuLiantai';root=$Plan.Root;base=$Plan.Base;models=$Plan.Models;ownership=$Plan.Ownership;
             models_cleaned=$false;runtime_cleaned=$false;remaining_models=@()}
    if ($Plan.State) {
        $state.models_cleaned=[bool]$Plan.State.models_cleaned
        $state.runtime_cleaned=[bool]$Plan.State.runtime_cleaned
        $state.remaining_models=@($Plan.State.remaining_models)
    }
    $stateFile=Join-Path $Plan.Root 'cleanup-state.json'
    $state | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $stateFile -Encoding UTF8
    $prefix=$Plan.Root.TrimEnd('\') + '\'
    Get-CimInstance Win32_Process | Where-Object {
        $_.ProcessId -ne $PID -and $_.ExecutablePath -and
        $_.ExecutablePath.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)
    } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        Wait-Process -Id $_.ProcessId -Timeout 10 -ErrorAction SilentlyContinue
    }
    if (!$state.models_cleaned) {
        $state.remaining_models=@(Remove-AppModels $Plan)
        $state.models_cleaned=$true
        $state | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $stateFile -Encoding UTF8
    }
    if (!$state.runtime_cleaned -and $Selection.RemoveRuntime) {
        Remove-OllamaRuntime $Plan $Selection.RemoveRuntime $state.remaining_models
        $state.runtime_cleaned=$true
        $state | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $stateFile -Encoding UTF8
    }
    Set-Location $env:TEMP
    Remove-AppFiles $Plan $Selection.KeepData
    Remove-AppShortcuts $Plan.Root
    $key='HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\LeihuLiantai'
    if (Test-Path -LiteralPath $key) {
        if ((Get-ItemProperty -LiteralPath $key).InstallLocation -eq $Plan.Root) {
            Remove-Item -LiteralPath $key -Recurse -Force
        }
    }
    Remove-Item -LiteralPath $stateFile -Force
    if (!(Get-ChildItem -LiteralPath $Plan.Root -Force)) { Remove-Item -LiteralPath $Plan.Root -Force }
}

if ($FunctionsOnly) { return }
try {
    if (!$AppDir) {
        $AppDir=(Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\LeihuLiantai' -ErrorAction SilentlyContinue).InstallLocation
        if (!$AppDir) { $AppDir=Join-Path $env:LOCALAPPDATA 'LeihuLiantai' }
    }
    $plan=Get-CleanupPlan $AppDir ([bool]$LocalModel) ([bool]$HybridAI)
    $selection=Show-CleanupConfirmation $plan
    if ($selection.Confirmed) {
        Invoke-Cleanup $plan $selection
        $message='程式套件與模型已清理。'
        if ($selection.KeepData) { $message += "`r`n歌曲、錄音與設定保留在：$($plan.Root)" }
        [Windows.Forms.MessageBox]::Show($message,'完整移除完成') | Out-Null
    }
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [Windows.Forms.MessageBox]::Show("清理未完成：$($_.Exception.Message)`r`n可修正問題後重新執行；尚未完成的步驟不會假裝成功。",'完整移除失敗') | Out-Null
    exit 1
} finally {
    # The standalone launcher copies this script outside the app, so it can remove itself.
    if ($PSCommandPath -and $env:TEMP -and $PSCommandPath.StartsWith((Join-Path $env:TEMP 'LeihuCleanup-'),[StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath (Split-Path $PSCommandPath) -Force -ErrorAction SilentlyContinue
    }
}
