# 整合版 2.3.2 — 合併上游 2.3.1，保留所有既有功能

2026-11-18 更新，只發佈至 `leihu-song-request-sync` 分支。

- **已有 Windows AI 選擇整合版：[程式更新檔 Update.exe](./LeihuLiantai-windows-ai-choice-2.3.2-Update.exe)**
- [首次安裝／修復用 Setup.exe](./LeihuLiantai-windows-ai-choice-2.3.2-Setup.exe)
- [完整移除工具](./LeihuLiantai-windows-ai-choice-2.3.2-CleanUninstall.exe)

已合併原作者 `LeihuTW/Leihu-singsing` 最新 2.3.1（`1c87c1781ecb9c3cdf8e5a174fd9436f9013c5eb`）。依使用者要求，保留所有既有功能並加入上游新功能。上游這次將 YouTube／批次匯入預設隱藏，需點標題五下才解鎖；本整合版維持原本直接可用的 YouTube 單曲下載、歌名搜尋、Excel／CSV 表單匯入、播放清單批量匯入、停止／重試及 CSV 匯出，不需要解鎖，即使舊設定含 `yt_enabled=false` 也照常使用。

整合新的音訊匯入框（可點選、拖曳及用鍵盤開啟）、AAC／OPUS／WMA 檔案選取提示、顯卡記憶體偵測與舊快取更新、例行成功查詢降噪、超過 10 MB 的記錄檔輪替備份，以及搬移歌曲庫時保留讀取、阻擋寫入。依「不移除功能」要求，顯存不足 10 GB 時提供單首處理建議，仍保留原本可手動開啟的兩首並行分離與既有設定；直播讓位和記憶體不足回退照常。音訊匯入維持原本的格式相容性，沒有新增僅接受八種副檔名的限制。

保留雙向點歌同步、繁簡／模糊歌名配對、永久對應、點歌者／KEY／佇列、本機／Claude／Gemini／OpenAI 選擇、各供應商金鑰、音訊強制對齊、FLAC、日文標音、錄音分享、快捷鍵、待唱清單、旋律譜、歌單匯出／回顧、歌曲庫搬移及前版全部功能。沒有修改其他 repo 或其他遠端分支。

**先儲存錄音、關閉練唱台，再執行 Update.exe，選原安裝資料夾。** 可由 2.3.1 或先前整合版直接更新，不需中間版本。不重裝 Python、套件或模型；歌曲、錄音、配對、設定與金鑰保留。程式內更新仍只下載本整合分支的 Update.exe 並驗證大小和 SHA-256。

來源合併提交：`dff4ebca7808933aa674469c1e38aa1bcc93a0d5`，NSIS 3.11 建置。保留性檢查確認前版全部 101 個 app API 路由宣告、379 個 UI ID 和 8 個核心模組的具名函式均未遺失。Python 192 項測試中 188 通過、4 項跳過（3 項模式限定、1 項需要 PowerShell）；14 項同步／待唱清單／暫停狀態 JavaScript、11 項相容修復測試及 4 個設定／直播歌詞／麥克風時脈／強制對齊 smoke 通過。

新增回歸驗證涵蓋未設定與舊版關閉設定下的 YouTube 加入佇列、CSV 讀取→解析→批次匯入且保留歌手／KEY、播放清單匯入／歷史／停止／重試、本機跨來源拒絕、搬移中仍可讀取但不可寫入、顯存建議不覆蓋手動並行選擇、舊 probe 快取補測顯存、成功輪詢不記錄但錯誤保留，以及大型記錄檔備份。

實際 Flask／Node／Chromium 驗證全新瀏覽器含 `ytOn=false` 與伺服器 `yt_enabled=false` 時 YouTube／批次／CSV 均可見可用；測過單曲加入佇列、歌名搜尋與批次加入、CSV 上傳保留歌手／KEY、播放清單勾選／匯入／停止／重試／重載、CSV 匯出和鍵盤音訊檔案選擇。亦重新驗證雙向點歌、點歌者保留、永久配對、競爭切歌、七個設定分頁和 AI 設定保存，沒有瀏覽器程式錯誤。瀏覽器的外部 YouTube 搜尋／清單資料採固定測試資料，未實際下載外部影片。

NSIS 壓縮完整性與 38 個封裝檔逐一比對來源通過；沒有 YouTube 隱藏／解鎖限制，不包含使用者資料、Python 環境或模型。更新資訊的大小、分支和 SHA-256 已核對，詳見 [SHA256SUMS](./SHA256SUMS)。Windows 安裝 GUI、實體音訊裝置、實際 GPU／正式分離模型及即時 YouTube 網站相容性尚未實機驗證；安裝檔未簽章。

---

# 整合版 2.3.1 — 合併上游 2.3.0，保留全部自訂功能

2026-11-17 更新，只發佈至 `leihu-song-request-sync` 分支。

- **已有 Windows AI 選擇整合版：[程式更新檔 Update.exe](./LeihuLiantai-windows-ai-choice-2.3.1-Update.exe)**
- [首次安裝／修復用 Setup.exe](./LeihuLiantai-windows-ai-choice-2.3.1-Setup.exe)
- [完整移除工具](./LeihuLiantai-windows-ai-choice-2.3.1-CleanUninstall.exe)

再次檢查上游後，已從先前的 2.1.0 合併到 `LeihuTW/Leihu-singsing` 最新 2.3.0（`fbfa15c399726caf98646bae035b7da7b365f6e6`）。新增顯示卡子程式（閒置自動釋放、停止／卡住偵測、Windows 工作物件）、佇列全部暫停／優先處理、處理加速、模型下載來源修正、歌名／歌詞搜尋範圍與排序、網頁／Excel／CSV 歌單匯出、直播歌單回顧與 YouTube 章節、歌曲庫／模型搬移和採用現有歌曲庫，以及固定高度的七個設定分頁。

保留既有全部自訂功能：雙向點歌同步、模糊歌名／繁簡配對、永久對應、點歌者與 KEY／佇列、原生雷虎整合、播放清單批次匯入／停止／重試、音訊強制對齊、本機／Claude／Gemini／OpenAI 選擇及各供應商金鑰、FLAC、日文標音、錄音分享、快捷鍵與旋律譜。新版 AI 分頁保留所有 AI 模式。自訂播放清單亦納入全部暫停／續跑、重疊處理和狀態列，暫停不會誤記為匯入失敗。歌曲庫搬移會保留批次紀錄，既有配對和供應商設定不會被覆蓋。沒有修改其他 repo 或其他遠端分支。

**先儲存錄音、關閉練唱台，再執行 Update.exe，選原安裝資料夾。** 可直接從 2.1.1 更新；沿用既有歌曲、錄音、配對、設定、金鑰、Python、套件與模型。不必重新安裝，也不需要先執行中間版本。Update.exe 僅更新程式，程式內更新仍只讀本整合分支並核對大小與 SHA-256。

來源合併提交：`a61a6ab2c06adb849f306d6363c1cfc7a8a92e5d`；NSIS 3.11 建置。Python 184 項測試中 180 通過、4 項跳過（3 項模式限定、1 項需 PowerShell）；14 項同步／直播待唱清單／播放清單暫停狀態 JavaScript、11 項相容修復測試及 4 個設定／直播歌詞／麥克風時脈／強制對齊 smoke 通過。新增回歸測試驗證播放清單暫停／續跑、優先順序與同首歌曲互斥、搬移／採用歌曲庫後保留歌詞／批次／模型／配對／金鑰、三種歌單格式與 CSV 再匯入、歷史歌單封存和匯出。

實際 Flask／Node／Chromium 驗證雙向切歌、點歌者保留、模糊配對與重載後恢復、競爭切歌、新版七個設定分頁及固定高度、各 AI 介面、處理品質／直播設定、歌名與歌詞範圍搜尋、XLSX 匯出、直播歌單及章節顯示，沒有瀏覽器程式錯誤。另實際啟動子程式做硬體 probe 和連續兩次 CPU 音高推論，確認子程式重用、主程式不載入 torch、結束後可清除；小型 CTC 本機測試模型的 CPU 推論也通過。

NSIS 壓縮完整性檢查與 38 個封裝檔逐一比對通過，新子程式和匯出模組均已納入；不包含使用者資料、Python 環境或模型。更新資訊的分支、大小與 SHA-256 已核對，詳見 [SHA256SUMS](./SHA256SUMS)。Windows 安裝 GUI／工作物件、實體音訊裝置、實際直播軟體及 GPU／正式分離模型推論仍需 Windows 實機驗證；安裝檔未簽章。

---

# 整合版 2.1.1 — 合併上游 2.1.0，保留所有自訂整合

2026-11-16 更新，只發佈至 `leihu-song-request-sync` 分支。

- **已有 Windows AI 選擇整合版：[程式更新檔 Update.exe](./LeihuLiantai-windows-ai-choice-2.1.1-Update.exe)**
- [首次安裝／修復用 Setup.exe](./LeihuLiantai-windows-ai-choice-2.1.1-Setup.exe)
- [完整移除工具](./LeihuLiantai-windows-ai-choice-2.1.1-CleanUninstall.exe)

已合併原作者 `LeihuTW/Leihu-singsing` 最新 `main` 2.1.0（`8391a332cff14d5bf5fe85415fa0560e54c209e1`）：原唱第二輸出裝置監聽、BS-Roformer 高品質人聲分離、直播時背景工作讓位、直播中輕量匯入及下播後補做高品質、歌詞待修標記／Ctrl+Alt+F、重新分離後歌詞時間不合的重新匯入提示、線上歌詞吻合度把關、簡轉繁只轉字形，以及本機來源限制、切歌競爭與直播清單捲動位置修正。另補上 Windows tasklist 偵測所需的 subprocess 匯入，避免 OBS 偵測默默失效。

保留雙向點歌同步、模糊歌名與繁簡配對、永久對應、點歌者／KEY／佇列、原生雷虎整合、播放清單批次匯入／停止／重試、音訊強制對齊、本機／Claude／Gemini／OpenAI 選擇、供應商獨立金鑰、FLAC、日文標音、錄音與分享功能，以及先前的直播待唱清單、延遲切歌取消、全域快捷鍵、旋律譜圖片與本場歌單。新版人聲品質／監聽／直播讓位設定與既有 AI 設定共同保存。現有點歌系統和相容修復包無須重裝；這次沒有修改其他 repo 或其他分支。

**先儲存錄音、關閉練唱台，再執行 Update.exe，選原安裝資料夾。** 支援既有版本 1.4.4～2.1.1；保留歌曲、錄音、API 金鑰、設定、配對及本場歌單。Update.exe 只更新程式，不重裝 Python、套件或模型；新版分離模型會在使用相關功能時依設定由程式另外下載。程式內一鍵更新仍只從本整合分支下載 Update.exe，並核對大小與 SHA-256。

來源合併提交：`c773dc91de0de7bf1019b8ef91f185cdd9aa1a55`，NSIS 3.11 建置。Python 178 項測試中 174 通過、4 項跳過（3 項模式限定、1 項需要 PowerShell）；包含小型本機 CTC 測試模型的實際 CPU 推論。13 項同步／直播待唱清單 JavaScript、11 項相容修復測試，以及設定、直播歌詞、麥克風時脈、強制對齊 4 個 smoke 通過。新增測試涵蓋 AI／直播狀態共同回傳、監聽與品質設定保存且不覆蓋各供應商金鑰、本機 API 相容與跨來源拒絕、直播輕量匯入、背景工作讓位／恢復、已升級歌曲略過、Windows 程式偵測與重新分離後保留自訂逐字歌詞。

實際 Flask／Node／Chromium 驗證雙向切歌、點歌者保留、模糊歌名配對、永久對應與重新載入、新版直播模式／歌詞待修、AI 和高品質設定保存、慢速舊請求不覆蓋較新的選歌；沒有瀏覽器程式錯誤。NSIS 壓縮封裝檢查通過，36 個封裝檔與 payload 逐一比對一致，程式／字體／說明亦與來源比對；不含使用者資料、Python 環境或模型。更新資訊的分支、檔案大小與 SHA-256 已核對，檢查碼見 [SHA256SUMS](./SHA256SUMS)。

Windows 安裝 GUI、實體麥克風／第二輸出裝置、實際 OBS／VTube Studio、全域快捷鍵與 GPU／正式分離模型推論未在 Linux 雲端實機驗證。安裝檔未簽章。

---

# 整合版 2.0.1 — 合併上游 2.0.0，保留雙向點歌同步

2026-11-09 更新，只發佈至 `leihu-song-request-sync` 分支。

- **已有 Windows AI 選擇整合版 1.4.4～1.6.9：[程式更新檔 Update.exe](./LeihuLiantai-windows-ai-choice-2.0.1-Update.exe)**
- [首次安裝／修復用 Setup.exe](./LeihuLiantai-windows-ai-choice-2.0.1-Setup.exe)
- [完整移除工具](./LeihuLiantai-windows-ai-choice-2.0.1-CleanUninstall.exe)

已合併原作者 `LeihuTW/Leihu-singsing` 的 2.0.0（`9703211cc837f444f59a99c6dfa59d34c2e1c0d3`）：直播模式、五行大字歌詞、待唱清單及 KEY 預先準備、前奏倒數、本場歌單、可自訂的 Windows 全域快捷鍵、直播模式線上歌詞搜尋、抽歌與手機／A4 旋律譜 PNG 匯出。

保留點歌系統雙向同步、模糊歌名與繁簡配對、永久對應、點歌者／KEY／佇列、原生雷虎整合、播放清單批次匯入／停止／重試、音訊強制對齊、本機／Claude／Gemini／OpenAI 選擇、FLAC、日文標音、錄音與分享功能。直播版面為自訂同步控制列保留一整列；上一首結束後排定的自動切歌，會在新的 Twitch／手動選歌或退出直播模式時取消。亦修正重複時間的逐字歌詞可能令旋律譜切段無法結束，並拒絕不同修飾鍵順序表示的同一快捷鍵重複綁定。

點歌系統上游 `sheng7337/twitch-song-request-system` 仍為 `00d83d0`，沒有新提交。現有整合分支或先前已套用的 [404 相容修復包](../../repair/song-request-sync/README.md) 可繼續使用，不需再次修改點歌系統。

**先儲存錄音、關閉練唱台，再執行 Update.exe，選原安裝資料夾。** 不需重裝 Python、套件、模型或安裝 ngrok／快捷鍵軟體；保留歌曲、錄音、API 金鑰、設定及配對。本版新增的 setlist.json 和快捷鍵設定也不會被程式更新覆蓋。1.6.9 亦可使用程式上方提示的一鍵更新，僅從本整合分支下載 Update.exe 並驗證大小和 SHA-256。Update.exe 不更新既有 Python 核心或套件；相關指令見 [安全更新說明](../../SECURITY_UPDATE_2026-10.md)。

來源：`03cc5c2630cce8c8ff2d55929eff4c974e155407`，NSIS 3.11 建置。153 項 Python 測試通過、3 項依 AI 模式跳過；真實 CTC 模型推論未執行。13 項同步／直播待唱清單 JavaScript、3 項設定／歌詞顯示／麥克風時脈 smoke 及點歌系統 129 項測試通過。新增實際手機與 A4 PNG 匯出、重複逐字時間、原歌詞／metadata 不變、快捷鍵設定與供應商金鑰保留、本場歌單跨讀取保存／去重／六小時重設、OBS 曲目資訊及模擬 Windows 註冊／事件派送測試。

實際 Flask／Node／Chromium 驗證雙向同步、模糊配對、點歌者保留、切歌、重載後配對、日文、逐句調整及評分，也驗證直播版面、五行歌詞、原曲／卡拉OK、音量、延遲切歌與外部新選擇的競爭、快捷鍵錄製／保存、前奏倒數、本場歌單、OBS 歌手／KEY、實際 PNG 匯出及狀態重新載入。直播線上歌詞搜尋的外部供應商使用固定測試資料，UI 與套用／保存使用實際程式；沒有呼叫外部 AI 帳戶。瀏覽器沒有程式錯誤。

封裝完整性、33 個來源／字體／說明檔逐一比對及更新資訊檢查通過；更新包不包含執行環境、模型或使用者資料。檢查碼見 [SHA256SUMS](./SHA256SUMS)。Windows 安裝 GUI、實際全域快捷鍵與其他軟體的衝突、實體麥克風及 GPU／模型推論未在 Linux 雲端實機驗證；安裝檔未簽章。

---

# 整合版 1.6.9 — 合併上游 1.6.8，保留點歌同步

2026-11-08 更新，只發佈至 `leihu-song-request-sync` 分支。

- **已有 Windows AI 選擇版 1.4.4～1.6.8：[程式更新檔 Update.exe](./LeihuLiantai-windows-ai-choice-1.6.9-Update.exe)**
- [首次安裝／修復用 Setup.exe](./LeihuLiantai-windows-ai-choice-1.6.9-Setup.exe)
- [完整移除工具](./LeihuLiantai-windows-ai-choice-1.6.9-CleanUninstall.exe)

合併原作者 `LeihuTW/Leihu-singsing` 的 1.6.8（`2a41d3006f83edda35d04aa51f7f97e46cddc941`），包含 1.6.5 之後新增的歌詞逐句調整獨立視窗、依歌聲自動校正、調整時維持歌詞順序、逐句即時評分、合唱模式及最高品質重新辨識。亦包含 Whisper CUDA 試算／CPU 回退、全新安裝 PyTorch 先補相依套件及 Windows 主控台視窗閃爍修正。Claude 結構化對齊的思考控制與舊模型回退整合至共用 ai_api.py，保留本機、OpenAI、Claude、Gemini 選擇與用量紀錄。

保留雙向點歌同步、模糊歌名及繁簡配對、永久對應、點歌者與佇列資料、播放清單批次匯入／停止／重試、音訊強制對齊、FLAC、日文標音、字體、錄音與分享功能。點歌系統 `master` 沒有新提交，現有 `E:\songRequest` 已驗證的相容修復可繼續使用。

**先儲存錄音、關閉程式，再執行 Update.exe 選原安裝資料夾。** 不必重裝 Python、套件、模型或 ngrok；歌曲、錄音、金鑰、設定和對應紀錄保留。Update.exe 不更新既有 Python 核心或套件；相關指令見 [安全更新說明](../../SECURITY_UPDATE_2026-10.md)。

本版開始，程式內的更新提示及一鍵更新只讀取本整合分支的 [update.json](./update.json)，下載同分支 Update.exe 並核對大小和 SHA-256。可沿用 secure-runtime；不會安裝原作者的安裝檔而覆蓋自訂功能。舊版 1.6.6 請先手動執行上方更新檔一次。開發用原始碼環境只提供下載連結。

來源：`4dffa062167dbd83710e3f0207d9b860afb02762`，NSIS 3.11 建置。142 項 Python 測試通過、3 項依 AI 模式跳過；真實 CTC 模型推論未執行。11 項同步 JavaScript 測試、3 項設定／直播歌詞／麥克風時脈 smoke、點歌系統 13 項測試通過。實際 Flask／Node／Chromium 驗證模糊配對、保留點歌者、雙向選歌、跳歌、重新載入後的對應、日文歌詞修復、逐句調整視窗與儲存、歌詞順序、合成音高輸入的評分及更新分支連結，沒有瀏覽器程式錯誤。

封裝完整性、31 個來源／字體／說明檔逐一比對及更新資訊檢查通過；不包含執行環境、模型或使用者資料。檢查碼見 [SHA256SUMS](./SHA256SUMS)。Windows 安裝 GUI、實體麥克風、實際 GPU／模型推論未在 Linux 雲端執行；安裝檔未簽章。

---

# 整合版 1.6.6 — 上游 1.6.5 與 F:\LeihuLiantai 操作指引

只發佈到 `leihu-song-request-sync` 分支。

- **已有 Windows AI 選擇版 1.4.4～1.6.5：[程式更新檔 Update.exe](./LeihuLiantai-windows-ai-choice-1.6.6-Update.exe)**
- [首次安裝／修復用 Setup.exe](./LeihuLiantai-windows-ai-choice-1.6.6-Setup.exe)
- [完整移除工具](./LeihuLiantai-windows-ai-choice-1.6.6-CleanUninstall.exe)
- [安全更新指令：含使用者提供的點歌系統目錄 F:\LeihuLiantai](../../SECURITY_UPDATE_2026-10.md)

已合併原作者 1.6.5（`9628d05d2fc3e65a001e5cbe98aff8b79c76da96`）：依主唱／合音／伴奏開關組合調整音量、舊歌曲背景補量響度及新匯入預設先搜尋並套用線上歌詞。仍可在設定啟用匯入時自動辨識，或對單首歌重新辨識。保留既有全部 AI 供應商、本機模式、音訊強制對齊、播放清單批次匯入／重試、雙向點歌同步、模糊歌名與永久配對、FLAC、日文讀音及分享視窗功能。

儲存錄音並關閉程式後，執行 Update.exe 選原安裝資料夾。歌曲、錄音、模型、設定與配對保留，不需要 ngrok。**Update.exe 不會替換 Python 核心或更新既有套件**，安全指令需另外執行。2026-10-25 再確認 Node.js 24.22.1、pip 26.2.2、certifi 2026.10.23、Pillow 13.0.0；googleapis 188.0.0 隔離副本的 npm audit 仍回報 0 項。安全說明包含 Python 核心另外遷移的指令與驗證限制。

點歌系統路徑依使用者提供為 `F:\LeihuLiantai`。npm 前會檢查 package.json；若只有 python/python.exe 而沒有 package.json，應將它視為練唱台安裝目錄，使用 Python 更新指令，並另找 Node.js 專案目錄。雲端無法直接檢查使用者 F 槽。

來源：`16bc636b7a1b05a3056d7cbd3ad64e6f181beb2e`，NSIS 3.11 建置。127 項 Python 與 11 項同步 JavaScript 測試通過，另有 3 項 Python 測試依 AI 模式跳過；真實 CTC 模型推論未執行。新增實際分軌響度組合、快取與失效、卡拉 OK 音量、預設／明確辨識選擇、自動套用線上歌詞及不覆蓋強制對齊結果的測試。

設定、直播歌詞、麥克風時脈 smoke 及實際 Flask／Node／Chromium 的雙向同步、配對恢復、日文標音和字體保存驗證通過。更新包 27 個程式／字體／說明檔與來源逐一比對一致，不含執行環境、模型或使用者設定；封裝與 SHA-256 見 [SHA256SUMS](./SHA256SUMS)。Windows 遷移、實際音訊分享與 GPU 推論尚需實機驗證，安裝檔未簽章。

---

# 整合版 1.6.5 — 上游 1.6.4 與最新安全指令

只發佈到 `leihu-song-request-sync` 分支。

- **已有 Windows AI 選擇版 1.4.4～1.6.4：[程式更新檔 Update.exe](./LeihuLiantai-windows-ai-choice-1.6.5-Update.exe)**
- [首次安裝／修復用 Setup.exe](./LeihuLiantai-windows-ai-choice-1.6.5-Setup.exe)
- [完整移除工具](./LeihuLiantai-windows-ai-choice-1.6.5-CleanUninstall.exe)
- **[2026-10-24 確認的 Node.js／Python 安全更新指令](../../SECURITY_UPDATE_2026-10.md)**

合併原作者 `LeihuTW/Leihu-singsing` 的 1.6.4（`0ca04f8114a04706333a850c70d398463d2001ed`）：歌曲資料併發寫入與自動修復、排隊效能、獨立分享視窗及音樂輸出裝置選擇。保留所有既有 AI 模式與 API 供應商、強制對齊、播放清單匯入／重試、雙向點歌同步、模糊歌名及永久配對、FLAC 與日文標音功能。

將上游原 Claude 用量檔的安全寫入方式套用至共用 ai_api.py，保留各供應商的來源記錄；強制對齊提交結果時也保護歌曲資料，並將自訂播放清單納入排隊顯示上限。新增私密設定／用量暫存檔與分享視窗資料的 Git 忽略規則。

先儲存錄音、關閉程式，執行 Update.exe 選原安裝資料夾。歌曲、錄音、模型、設定及配對保留。**Update.exe 不會更新既有 Python 核心或套件**，請另外依安全說明更新。2026-10-24 再確認 Node.js 24.x 修補版仍為 24.22.1，pip 26.2.2、Pillow 13.0.0；certifi 更新為最新 2026.10.23，requirements 與遷移腳本同步更新。一般 Setup 的舊 bootstrap 仍建立 Python 3.11.9，不能視為已修補核心；安全說明包含獨立 secure-runtime 遷移與新捷徑指令，保留舊環境供回復。

來源：`cd5383c259fa71462b3e42706e9ab803a3bdd378`，NSIS 3.11 建置。122 項 Python、11 項同步 JavaScript 及隔離點歌系統 7 項測試通過，另有 3 項 Python 測試依 AI 模式跳過，真實 CTC 模型推論未執行。新增併發寫入不遺失欄位、損壞 JSON 修復、播放清單排隊上限、各供應商用量紀錄及分享視窗啟動參數測試。設定（含輸出裝置與 API 金鑰）、直播歌詞及 USB 麥克風時脈 smoke 通過。

實際 Flask／Node 配合 Chromium 驗證雙向選歌、保留點歌者、模糊比對、配對恢復、日文讀音與字體保存。修補後的已安裝 Python 測試套件與 googleapis 188.0.0 隔離副本稽核回報 0 項，但不涵蓋未安裝的完整 Windows／GPU／ML 套件或執行環境核心。Windows 遷移腳本、實際 Discord 畫面／聲音分享、實體音效裝置與 GPU 推論未在雲端驗證。

更新包 27 個程式／字體／說明檔與來源逐一比對一致，不含執行環境或使用者資料；封裝與 SHA-256 見 [SHA256SUMS](./SHA256SUMS)。安裝檔未簽章。

---

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
