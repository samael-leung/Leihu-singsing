# 整合版 1.6.2 — 上游 1.6.1 與安全更新指令

只發佈到 `leihu-song-request-sync` 分支。

- **已有 Windows AI 選擇版 1.4.4～1.6.1：[程式更新檔 Update.exe](./LeihuLiantai-windows-ai-choice-1.6.2-Update.exe)**
- [首次安裝／修復用 Setup.exe](./LeihuLiantai-windows-ai-choice-1.6.2-Setup.exe)
- [完整移除工具](./LeihuLiantai-windows-ai-choice-1.6.2-CleanUninstall.exe)
- **[Node.js／Python／憑證事件的 PowerShell 安全更新指令](../../SECURITY_UPDATE_2026-10.md)**

合併原作者 `LeihuTW/Leihu-singsing` 的 1.6.1（`556d6189498c96df7510e2ebaf55bfbc9be7a64e`），包含遠端開歌與 KEY、繁簡搜尋、歌手／曲名／KEY 表單、排序與分組、FLAC 儲存與容量整理、預先下載、背景歌詞搜尋與精細處理。保留所有既有 AI 選擇、日文標音、雙向點歌同步、模糊歌名比對與永久配對，以及播放清單批次匯入、停止／重試及音訊強制對齊。

本次修正自訂強制對齊支援 FLAC、播放清單重試可沿用已匯入的 FLAC，並保留 YouTube 暫停狀態及上游處理完成後的預設 KEY／精細處理行為。

先儲存錄音並關閉程式，執行 Update.exe 選原安裝資料夾。更新包保留歌曲、錄音、模型、設定與 song-request-links.json；不需要 ngrok。**Update.exe 不會更新既有 Python 核心或套件，請另外執行安全說明中的指令。** requirements 已更新至 Pillow 13.0.0、certifi >=2026.10.19。

安全說明列出 Node.js 24.22.1、pip >=26.2.2、certifi >=2026.10.19 的確認來源。舊內嵌 Python 3.11.9 不會因為更新系統 Python 而改變；setup/repair-runtime.ps1 可用已安裝的修補版 Python 3.13.17+ 建立 secure-runtime、重裝相符套件並建立新捷徑，保留原 Python 與使用者資料。一般 Setup 的舊 bootstrap 仍是 3.11.9，不能視為已修補核心。遷移腳本與 Windows 安裝 GUI 未在 Linux 雲端實機執行；winget 是否已同步該 Python 版本也未驗證，腳本會檢查最低版本。

來源：`0f9962dbec04c8af0666ad71eb93c3f4f3ddd352`，NSIS 3.11。116 項 Python 測試、11 項同步 JavaScript 測試通過，另有 3 項 Python 測試依 AI 模式跳過，真實 CTC 模型推論未執行。設定、直播歌詞、USB 麥克風時脈 smoke 及實際 Flask／Node／Chromium 的雙向同步、日文標音、字體與配對恢復驗證通過。新增 FLAC 壓縮／播放／對齊、播放清單重試、遠端 API、繁簡搜尋及 Python ABI 選 wheel 的回歸測試。

點歌系統升級 googleapis 188.0.0 的隔離副本通過 7 項測試，npm audit 回報 0 項；其原分支沒有更動。雲端測試環境在更新 pip／certifi／Pillow 後 pip-audit 回報 0 項，這不涵蓋未安裝的完整 Windows／GPU／ML 套件或 Python 核心。實際 GPU／模型推論及 Windows 執行環境遷移尚需實機驗證。

更新包的 27 個程式／字體／安全說明檔與來源逐一比對一致，不包含執行環境、模型或使用者資料；封裝及 SHA-256 見 [SHA256SUMS](./SHA256SUMS)。安裝檔未簽章。

---

# 整合版 1.5.2 — 合併原作者 1.5.1

此版本只發佈到 `leihu-song-request-sync` 分支。

- **已有 Windows AI 選擇版 1.4.4～1.5.1：[程式更新檔 Update.exe](./LeihuLiantai-windows-ai-choice-1.5.2-Update.exe)**
- [首次安裝／修復用 Setup.exe](./LeihuLiantai-windows-ai-choice-1.5.2-Setup.exe)
- [完整移除工具](./LeihuLiantai-windows-ai-choice-1.5.2-CleanUninstall.exe)

合併原作者 `LeihuTW/Leihu-singsing` 的 1.5.1（`9b2014a8939cc0369ffb28d344b2b7f0744d9120`）：日文假名／羅馬拼音、逐首儲存讀音修正、舊日文歌詞字形修復、內建 jf open 粉圓字體與授權、分離進度及具有大小／SHA-256 驗證的多來源模型下載。

保留本機／Claude／Gemini／OpenAI 選擇、音訊強制對齊、播放清單批量匯入與重試、雙向點歌同步、模糊歌名比對、一次確認及記住對應。保留重新辨識時不覆蓋手動修改或任何 AI／音訊對齊結果的行為，也保留直播歌詞切歌時重新傳送相同歌詞的修正；新增的日文標註會一起傳送。

先儲存錄音並關閉程式，執行 Update.exe 選原安裝資料夾。更新包只覆蓋程式與內建字體，不重裝 Python 或模型；歌曲、錄音、設定及 `song-request-links.json` 保留。首次啟用日文標音時，程式會在背景自動下載約 45 MB 的 SudachiPy 字典套件；不需要重裝主程式、安裝系統字體或 ngrok。完整 Setup.exe 會預先安裝日文字典。

來源：`f90bb3c4d8b66abd49b8ce2a43ba0e5ec62997a3`，NSIS 3.11 建置。109 項 Python、11 項同步 JavaScript 與點歌系統 7 項測試通過；另有 3 項 Python 測試依 AI 模式跳過，真實 CTC 模型推論未執行。設定／金鑰、直播歌詞（日文標註與切歌）及麥克風時脈 smoke 通過。實際 SudachiPy 字典與 Pillow 字體繪製通過；錯誤下載來源被檢查碼拒絕並切換備援來源的測試通過。

Chromium 配合實際 Flask／Node 驗證模糊選歌、保留點歌者、反向選歌、重新載入歌曲對應、日文歌詞修復、假名／羅馬拼音、讀音修改及字體設定保存。更新包 24 個程式／字體／授權檔與來源逐一比對一致，不包含 Python、歌曲、模型或使用者設定；封裝及 SHA-256 見 [SHA256SUMS](./SHA256SUMS)。Windows 安裝 GUI、實體麥克風、實際 GPU／模型推論未在雲端驗證，安裝檔未簽章。

---

# 整合版 1.4.10 — 合併原作者 1.4.9

此版本只發佈到 `leihu-song-request-sync` 分支。

- **已有 Windows AI 選擇版 1.4.4～1.4.9：[程式更新檔 Update.exe](./LeihuLiantai-windows-ai-choice-1.4.10-Update.exe)**
- [首次安裝／修復用 Setup.exe](./LeihuLiantai-windows-ai-choice-1.4.10-Setup.exe)
- [完整移除工具](./LeihuLiantai-windows-ai-choice-1.4.10-CleanUninstall.exe)

合併原作者 `LeihuTW/Leihu-singsing` 的 1.4.9（`3b36bf2cd3ff611f6678a67d2bff4a454a3d377f`）：USB 麥克風修正、歌詞辨識品質與語言判斷、辨識／線上歌詞切換、高品質模型背景下載、Excel／CSV／歌名批次匯入、佇列排序、錄音對齊、試聽拖曳與匯出音質改善。

保留本機／Claude／Gemini／OpenAI 選擇、音訊強制對齊、播放清單批量匯入與重試、雙向點歌同步、模糊歌名比對、一次確認及記住對應。不需要 ngrok 或新增同步軟體。重新辨識不會覆蓋手動修改、各 AI 供應商或音訊強制對齊的歌詞。

請先儲存錄音並關閉程式，執行 Update.exe 選原安裝資料夾。不需要重新安裝 Python、套件或模型；歌曲庫、錄音、設定與 `song-request-links.json` 都會保留。高品質分離模型未下載完成時先使用標準模型並在背景下載；如要沿用現有模型，請在設定選「標準」。

來源：`006a4790e52eb4c1a4bc3c67c979d2a4871df2cb`，NSIS 3.11 建置。103 項 Python 測試、11 項同步 JavaScript 測試及點歌系統 7 項測試通過；另有 3 項 Python 測試依 AI 模式跳過，真實 CTC 模型推論未執行。設定、直播歌詞及 USB 麥克風時脈 smoke 通過。實際 Flask／Node 配合 Chromium 驗證批次介面、模糊歌名選歌、保留點歌者、歌詞來源切換、反向選歌、跳歌及重新載入後的歌曲對應。Windows 安裝 GUI、實體 USB 麥克風與 GPU／模型推論仍需實機驗證。

更新包的 21 個程式／設定來源檔已逐一比對一致，不包含 Python、歌曲庫、模型及使用者設定；Setup.exe 封裝檢查通過。SHA-256 見 [SHA256SUMS](./SHA256SUMS)。安裝檔未簽章。

---

# 整合版 1.4.7 — 合併原作者更新，保留完整點歌同步功能

**此版本及後續更新只發佈到 `leihu-song-request-sync` 分支。**

- **已有 1.4.4～1.4.7：[程式更新檔 Update.exe](./LeihuLiantai-windows-ai-choice-1.4.7-Update.exe)**
- [首次安裝／修復用 Setup.exe](./LeihuLiantai-windows-ai-choice-1.4.7-Setup.exe)
- [完整移除工具](./LeihuLiantai-windows-ai-choice-1.4.7-CleanUninstall.exe)

已合併原作者 `LeihuTW/Leihu-singsing` 的 1.4.5（`18755f8`），包含高品質主唱／合音分離、音量標準化、處理停止／取消及有時間上限的歌詞搜尋。同時保留本機／Claude／Gemini／OpenAI 選擇、YouTube 播放清單批量匯入、音訊強制對齊、雙向點歌同步、YouTube 歌名自動比對、一次確認及記住對應。

請先儲存錄音、關閉程式，再用 Update.exe 選原安裝資料夾；不必重裝 Python、套件或模型，歌曲、設定及 `song-request-links.json` 都會保留。上游高品質分離模型首次使用可能下載約 900 MB；如要沿用現有模型，在設定的主唱分離品質選「標準」。CPU 的自動模式預設使用標準模型。

合併來源：`33cc693db137beced2b742a67db7681a7f74544f`，NSIS 3.11 建置。96 項 Python 測試及 11 項同步 JavaScript 測試通過，另有 3 項 Python 測試依 AI 模式跳過；設定／歌詞顯示 smoke 及 Chromium 雙向同步、音量標準化音訊線路與品質設定驗證通過。CTC 真實模型推論、實際 GPU 分離與 Windows 安裝 GUI 未在本次雲端驗證。高品質失敗退回標準、音量計算、取消工作和舊資料保留已驗證。封裝內容與來源、SHA-256 檢查通過，見 [SHA256SUMS](./SHA256SUMS)；安裝檔未簽章。

---

## Windows AI 選擇版 1.4.6 — YouTube 歌名自動對應

- **已有 1.4.4／1.4.5／1.4.6：[程式更新檔 Update.exe](./LeihuLiantai-windows-ai-choice-1.4.6-Update.exe)**
- [首次安裝／修復用 Setup.exe](./LeihuLiantai-windows-ai-choice-1.4.6-Setup.exe)
- [完整移除工具](./LeihuLiantai-windows-ai-choice-1.4.6-CleanUninstall.exe)

先儲存錄音並關閉練唱台，再執行 Update.exe 選原安裝資料夾；不用重裝 Python、套件或模型。更新會保留歌曲、設定與 `song-request-links.json` 對應紀錄。**點歌系統也須更新到 `feat/leihu-song-request-sync` 分支最新版**，才能完整支援只綁定對應、保留原點歌項目的行為。

本版會清理 YouTube 歌詞／Official MV／HD 標記，結合歌手、曲名中繼資料及繁簡體別名自動尋找歌曲。例如「下一個天亮」會對應「郭靜 下一個天亮 歌詞」。同名或版本無法區分時，點候選確認一次即可；對應會保存在本機，重新啟動仍可沿用，並可按「更改對應」修正。反向選歌使用正式歌名與已保存的對應，避免建立重複歌曲。不需要新增軟體或相依套件。

來源：`e4b33080f4d08fc94544baea7837641b6d87116e`，使用 NSIS 3.11 建置。點歌系統 7 項、練唱台 16 項測試通過，並以實際 Flask／Node 程式與 Chromium 驗證截圖案例、自動對應、一次確認、重新載入記憶及保留原點歌資訊。封裝內容與來源比對及 SHA-256 檢查通過，見 [SHA256SUMS](./SHA256SUMS)。Windows 安裝 GUI 仍需實機驗證；安裝檔未簽章。

---

## Windows AI 選擇版 1.4.5 — 點歌系統雙向同步

- **已有 1.4.4／1.4.5 安裝：[只更新程式的 .exe](./LeihuLiantai-windows-ai-choice-1.4.5-Update.exe)**
- [首次安裝／修復用完整安裝檔](./LeihuLiantai-windows-ai-choice-1.4.5-Setup.exe)
- [完整移除工具](./LeihuLiantai-windows-ai-choice-1.4.5-CleanUninstall.exe)

已有 Windows AI 選擇版不需要解除安裝或重裝執行環境。請先儲存錄音、關閉練唱台，執行 **Update.exe** 並選擇原本安裝資料夾。程式更新檔只更新程式，不會下載或安裝 Python、套件、模型或其他軟體，也不會覆蓋歌曲庫、錄音、API 金鑰與設定。未完成安裝或更舊版本請使用 Setup.exe。完整安裝檔的「更新」模式會沿用既有資料並檢查相依套件；若只需這次功能，優先使用 Update.exe。

更新後，在練唱台勾選「同步點歌系統『正在播放』」。搭配 `samael-leung/twitch-song-request-system` 的 `feat/leihu-song-request-sync` 分支，沿用其最新上游瀏覽器設定精靈與授權流程；不需通道或額外同步軟體。雙向選歌、原歌曲保留、重複事件與版本衝突處理均包含在此版本。

建置來源：`b9fb020cbe89d372753a09d2677faedec723da15`，NSIS 3.11。SHA-256 見 [SHA256SUMS](./SHA256SUMS)。已驗證編譯、封裝完整性、同步檔案與來源一致，以及更新檔不包含執行環境／使用者資料；同步測試及實際 Chromium 雙向操作通過。Windows 安裝與更新 GUI 仍需實機驗證。安裝檔未簽章。

---

## 歷史版本 1.4.4


- [安裝檔](./LeihuLiantai-windows-ai-choice-1.4.4-Setup.exe)
- [完整移除工具](./LeihuLiantai-windows-ai-choice-1.4.4-CleanUninstall.exe)

首次啟動可選本機 Ollama 或 Claude／Gemini／OpenAI API。API 模式不下載 Ollama 或語言模型。本機模式在儲存設定後依硬體選模、下載並驗證；也可指定模型。

已有安裝請關閉程式，安裝到原資料夾並選更新，保留歌曲、錄音、設定及模型。完整移除預設保留資料，API-only 安裝不會清理其他程式的本機模型；曾使用本機模式時仍可清理已記錄的模型。

來源提交：`dadaafd68c2711d6be42ccca5c4bd6fa7bdc110c`。以 NSIS 3.11 建置，SHA-256 見 [SHA256SUMS](./SHA256SUMS)。供應商合約、設定介面、硬體選模及清理測試通過；Windows GUI／GPU、真實 API 帳戶仍需實機驗證。安裝檔未簽章。此目錄其他 localModel 檔案為歷史版本，請使用上方 AI 選擇版下載。

新增音訊強制對齊：中文普通話／英文，以 Wav2Vec2／CTC 對齊主唱音訊並儲存逐字時間，不需要 API。首次按「依音訊強制對齊」會下載對齊模型；請貼上整首、同版本的完整歌詞。已有 1.4.4 請重新下載安裝檔更新，以安裝新增套件。

新增 YouTube 播放清單批量匯入：可選曲、逐首處理、停止剩餘項目、重試失敗或中斷項目，並保留批次紀錄。已有 1.4.4 請重新下載安裝檔更新程式，無新增套件需求。

中文強制對齊改用 ydshieh/wav2vec2-large-xlsr-53-chinese-zh-cn-gpt，公開字典包含 7,322 個漢字（繁簡體），解決「眠、徘、徊」缺字問題。更新後首次中文對齊自動下載約 1.2 GB 的新模型，繁體顯示保留；仍可能缺少罕見字，歌唱效果需播放確認。
