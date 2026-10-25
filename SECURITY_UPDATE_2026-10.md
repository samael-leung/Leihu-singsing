# 2026-10-24 Windows 安全更新指令

先儲存錄音並關閉點歌系統及練唱台。以下在 PowerShell 執行；自訂安裝位置請修改 `$AppDir`。這是已確認公告與套件版本的修補方式，不能據此判定電腦曾被入侵或已完全排除入侵。若您指的是另一則事件，需再對照公告／CVE。

## Node.js：更新執行環境

原作者 2026-10-21 公告修正憑證驗證、Brotli 記憶體破壞等高風險問題，並更新受 eMudhra 中繼 CA 私鑰外洩影響的信任資料。修補版為 22.23.4、24.22.1、26.12.1；本專案建議保留 24.x LTS。

```powershell
node --version
winget upgrade --id OpenJS.NodeJS.LTS --exact --source winget
```

關閉 PowerShell、重新開啟，確認 `node --version` 是 **v24.22.1 或較新的受支援修補版**。若 winget 找不到套件，先用 `winget list Node.js` 確認原安裝來源；nvm／fnm 管理的 Node 應透過原工具升級，避免安裝兩份。重新啟動所有 Node 程序才會使用修補版；`npm update` 不會更新 Node 核心。

## 點歌系統：修補 npm 依賴

本次在乾淨目錄重現既有 package.json，稽核發現 googleapis 的間接 uuid 漏洞 [GHSA-w5hq-g745-h8pq](https://github.com/advisories/GHSA-w5hq-g745-h8pq)。單純 `npm audit fix` 無法消除受直接依賴版本限制的項目；以下指定升級已在隔離副本通過 7 項現有測試，並使 npm audit 回報 0 項。googleapis 為主要版本升級，真實 Google Sheets 帳戶仍需開機後確認。

您提供的點歌系統資料夾是 **`F:\LeihuLiantai`**。先確認這裡包含 Node.js 專案的 `package.json`，再執行：

```powershell
Set-Location -LiteralPath 'F:\LeihuLiantai'
if (-not (Test-Path -LiteralPath '.\package.json')) {
    throw '此資料夾沒有 package.json，請改用 Node.js 點歌系統專案的實際路徑；不要在 Python 練唱台資料夾執行 npm。'
}
npm install --save-exact --ignore-scripts googleapis@188.0.0
if ($LASTEXITCODE -ne 0) { throw 'npm install failed' }
npm test
if ($LASTEXITCODE -ne 0) { throw 'Tests failed; do not start yet' }
npm audit --omit=dev
```

以上會更新您本機的 package.json／相依套件；這組 Google API 升級與相容修復已正式納入點歌系統的 `leihu-song-request-sync` 分支，並納入 package-lock.json 供重現與稽核。不要使用 `npm audit fix --force` 直接升級所有主要版本，也不要覆寫原本 .env 或金鑰。

若 `F:\LeihuLiantai` 包含 `python\python.exe` 而沒有 `package.json`，它是練唱台的安裝資料夾；請在下方將 `$AppDir` 改成 `'F:\LeihuLiantai'`，npm 指令則要在另外的 Node.js 專案執行。

## 練唱台：修補 Python 套件

受影響的 certifi 信任庫至少應升級至 **2026.10.19**；2026-10-24 再確認 PyPI 最新為 **2026.10.23**，以下使用此版本作為更新下限。本次也將 pip 更新至 **26.2.2**，將舊的 Pillow 11.3.0 更新至 **13.0.0**，並在這些版本上執行回歸測試。1.6.6 的 requirements 已記錄新要求，但 **Update.exe 只複製程式，不會自動更新既有套件或 Python 核心**。

```powershell
$AppDir = Join-Path $env:LOCALAPPDATA 'LeihuLiantai'
$Py = Join-Path $AppDir 'python\python.exe'
if (Test-Path "$AppDir\secure-runtime\leihu-ready.json") {
    $Py = Join-Path $AppDir 'secure-runtime\Scripts\python.exe'
}
& $Py --version
& $Py -m pip install --upgrade 'pip>=26.2.2' 'certifi>=2026.10.23' 'pillow==13.0.0'
if ($LASTEXITCODE -ne 0) { throw 'Security package upgrade failed' }
& $Py -m pip check
& $Py -c "import certifi, PIL, pip; print('certifi',certifi.__version__); print('Pillow',PIL.__version__); print('pip',pip.__version__)"
```

不要關閉 TLS 驗證、使用 `--trusted-host`，或從不明鏡像安裝修補套件。Windows 本身的根憑證信任由 Windows Update 維護，請同時套用 Windows 安全更新並重新啟動相關程式。

## Python 核心：另外建立修補後的執行環境

舊安裝含 **內嵌 Python 3.11.9**。更新系統 Python 或 pip 都不會改動它；本版一般 Setup 的舊 bootstrap 仍會建立 3.11.9，不能視為已修補 Python 核心。以下遷移改用獨立的 `secure-runtime`，保留原 Python、歌曲、模型、設定及配對，不需要刪除舊環境。

先透過官方 winget 來源安裝／更新 64 位元 Python 3.13：

```powershell
# 尚未安裝 Python 3.13 時：
winget install --id Python.Python.3.13 --exact --source winget
# 已安裝 Python 3.13 時，改執行：
# winget upgrade --id Python.Python.3.13 --exact --source winget
```

重新開啟 PowerShell。先安裝本分支的 1.6.6 Update.exe，再執行：

```powershell
$AppDir = Join-Path $env:LOCALAPPDATA 'LeihuLiantai'
py -3.13 -c "import sys; assert sys.version_info >= (3,13,17), '需要 Python 3.13.17 或更新的 3.13 修補版'; print(sys.version)"
if ($LASTEXITCODE -ne 0) { throw '請先更新 Python 3.13；不要繼續使用舊版' }
powershell -NoProfile -ExecutionPolicy RemoteSigned -File "$AppDir\setup\repair-runtime.ps1" -AppDir $AppDir
if ($LASTEXITCODE -ne 0) { throw 'Python migration did not complete' }
```

Python 3.13.17 於 2026-10-21 更新內附 pip 至 26.2.2。如果 winget 尚未提供此版，請等來源更新或透過 [Python 官方 Windows 下載頁](https://www.python.org/downloads/windows/) 安裝已修補的 64 位元 3.13，確認安裝程式的 Python Software Foundation 簽章；不要跳過版本檢查。此環境無法存取 python.org 下載頁，因此未驗證目前 winget 的 Windows 套件是否已同步。

遷移會重裝相符的 Python 套件／PyTorch，可能下載數 GB；原模型會沿用。安裝程式已改為按實際 Python ABI 選擇 PyTorch wheel，官方 CUDA 12.8 清單的 cp313 Windows wheel 已確認存在。完成後請使用桌面的 **Leihu - Updated Python** 捷徑；原捷徑仍可能指向舊 Python。後續 Update.exe 會優先開啟完成遷移的環境。保留舊環境是為了可回復，並不代表舊 Python 已修補。

遷移指令及 Windows GUI 未在 Linux 雲端實機執行，不能宣稱 Windows／GPU 已驗證。此項與程式／套件回歸測試分開計算。

## 稽核與限制

需進一步掃描實際安裝的 ML 套件，可在選定的 Python 環境執行：

```powershell
& $Py -m pip install --upgrade pip-audit
& $Py -m pip_audit
```

這只檢查已知 Python 套件公告，不檢查 Python 核心、Node 核心、Windows、手動下載的模型或惡意套件是否曾執行。修補版本不等於清除已發生的入侵；若您曾執行明確被公告為惡意的套件，還需要依該公告判定是否撤銷 Twitch／Google／AI 金鑰，不能只重裝套件。

本次測試環境已安裝的 Python 套件稽核在修補後回報 0 項；雲端未安裝完整 GPU／ML 套件組，這不是所有 Windows requirements 的完整安全認證。

來源：

- [Node.js 2026-10-21 安全公告](https://nodejs.org/en/blog/vulnerability/october-2026-security-releases)
- [Node.js 官方版本清單](https://nodejs.org/dist/index.json)
- [certifi 憑證事件 GHSA-6q48-6c7w-9gw2](https://github.com/advisories/GHSA-6q48-6c7w-9gw2)
- [CPython 3.13.17 安全更新紀錄](https://github.com/python/cpython/blob/v3.13.17/Misc/NEWS.d/3.13.17.rst)
