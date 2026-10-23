# 雷虎練唱台

在自己電腦上跑的 Windows 練歌工具。匯入一首歌（音訊檔或 YouTube 網址），它會：

- 用 AI 模型把歌拆成**主唱、合音、伴奏**三軌（有顯示卡時用高品質 Roformer 模型分離主唱與合音）
- 分析主唱的**旋律**，可切換「原聲曲線」或「音符區塊」顯示
- **辨識歌詞**並對上時間，中文轉成台灣繁體；也會到 LRCLIB、網易雲、酷狗搜尋歌詞，與辨識結果比對後讓你選一版；也可以匯入 LRC／SRT／TXT 歌詞檔
- **升降 KEY、調整速度**練唱（用所有 CPU 核心轉換）；唱的時候會依你的音域**建議適合的 KEY**
- 可以關掉旋律只看歌詞（五行）；也有給 OBS 用的**去背直播歌詞**畫面，跟著播放同步上色
- 開麥克風時即時顯示你的音高，有音量表、增益與自動調整、防爆音；錄音後在本機**自動評分**，標出最需要練的句子
- 把你的錄音和合音、伴奏混音後**匯出 MP3／WAV、直式影片（旋律線條＋歌詞）或成績卡圖片**，一鍵開啟 FB、IG、X、Threads 分享
- 播放時自動**音量標準化**（LUFS），每首歌差不多大聲
- **批次加入**：多個 YouTube 網址、歌單網址、「歌手 歌名」搜尋或 Excel／CSV 歌單，依序排隊下載處理，可調整順序
- 歌曲庫可自訂分類（例如中文歌、日文歌）並用關鍵字搜尋

歌曲與錄音處理在本機執行。首次啟動會開啟設定，讓使用者選擇 **本機模型** 或 **API**；API 可選 **Claude、Gemini、OpenAI**，之後隨時可以切換。

## Windows 安裝（windows-ai-choice）

到 [installer/releases](installer/releases) 下載 `LeihuLiantai-windows-ai-choice-1.6.2-Setup.exe`。安裝到可寫入的資料夾，首次開啟後選擇 AI 模式。安裝程式先準備 Python、音訊套件及 UVR／Whisper；這一步不會下載 Ollama 或本機語言模型。已有安裝請關閉程式，安裝到原位置並選「更新」，保留歌曲、錄音與設定。

已安裝 Windows AI 選擇版 1.4.4～1.6.2 者，使用 `LeihuLiantai-windows-ai-choice-1.6.2-Update.exe` 即可加入雙向選歌；先儲存錄音、關閉程式，再選原安裝資料夾。這個程式更新檔不下載或重裝 Python、套件、模型，也不修改歌曲、錄音與設定。尚未完成安裝或更舊版本請使用完整 Setup.exe。

本機模式按「儲存」後才會沿用或安裝 Ollama、自動選模、下載並驗證回覆。下載中斷可再次儲存續傳。Ollama 官方 Windows 安裝檔會驗證 Authenticode 簽章，不會繞過驗證。API 模式不需要 Ollama，也不會下載本機語言模型。

Windows 10 22H2／11 64 位元，音訊套件建議預留約 8 GB，選本機模式時另外預留模型與 Ollama 空間（依模型約 2–13 GB）。NVIDIA 的音訊加速依驅動與 PyTorch 相容性決定，會測試運算並在必要時退回 CPU。

## AI 模式與設定

1. **本機模型**：保留「依硬體自動選擇模型」，按儲存開始準備。介面會顯示偵測結果、建議模型及下載進度。可取消自動選擇，輸入自己的 Ollama 模型名稱。遠端 Ollama 請使用手動選模，因為本程式只能偵測本機硬體。
2. **API**：選 Claude／Gemini／OpenAI，確認模型名稱，輸入該供應商的 API 金鑰，再儲存。三家帳戶與模型設定會分別保留；切換供應商不會覆寫其他金鑰。留空保留已存金鑰，「清除目前供應商」只清除該家的已存金鑰。
3. API 也支援 `ANTHROPIC_API_KEY`、`GEMINI_API_KEY`、`OPENAI_API_KEY` 環境變數。金鑰存在安裝資料夾的 `config.json`，介面只回傳是否已設定，不會傳回金鑰內容。不要上傳設定檔。

預設 API 模型為 `claude-sonnet-4-6`、`gemini-2.5-flash`、`gpt-4.1-mini`；可改成帳戶可使用且支援所需結構化輸出的模型。歌詞對齊分別使用 Claude 工具回傳、Gemini JSON Schema、OpenAI 嚴格 JSON Schema；回覆仍會檢查行數、時間遞增與歌曲長度，無效資料不會覆蓋歌詞。

API 會把歌詞／練習分析傳給所選供應商，可能產生 API 費用；網頁版訂閱不等於 API 額度。本機推論無 API 費用，模型下載後可離線；YouTube 匯入和線上歌詞搜尋仍需網路。

### 本機模型選擇

| 硬體 | 自動選擇 | 上下文 |
| --- | --- | --- |
| NVIDIA 目前可用顯示記憶體 ≥20 GB，RAM ≥16 GB | Qwen2.5 14B | 16,384 tokens |
| NVIDIA 目前可用顯示記憶體 ≥10 GB，RAM ≥12 GB | Qwen2.5 7B | 8,192 tokens |
| NVIDIA 目前可用顯示記憶體 ≥5 GB | Qwen2.5 3B | 4,096 tokens |
| NVIDIA 剩餘顯示記憶體較少 | Qwen2.5 1.5B | 4,096 tokens |
| Apple Silicon 共享記憶體 ≥48 GB | Qwen2.5 14B | 8,192 tokens |
| Apple Silicon 共享記憶體 ≥16 GB | Qwen2.5 7B | 8,192 tokens |
| Apple Silicon 共享記憶體 <16 GB | Qwen2.5 3B | 4,096 tokens |
| 未偵測到 NVIDIA，RAM ≥16 GB／不足或未知 | Qwen2.5 3B／1.5B | 4,096 tokens |

你的 RTX 3080／24 GB VRAM、96 GB RAM 在顯示記憶體空間足夠時會選 14B；M2 Pro Mac mini／32 GB RAM 會選 7B。這是保留音訊處理空間的建議，並非速度或品質保證；3B／1.5B 的複雜歌詞對齊效果可能較弱，可以改用較大模型或 API。AMD／Intel 顯示卡目前使用 RAM 的保守建議，實際加速由 Ollama 管理。

每次 AI 回覆後以 `keep_alive: 0` 釋放語言模型。練習建議被截斷時最多加大長度上限重試一次；兩次用量都記錄。結構化對齊不會自動重試。紀錄存在 `usage-ai-choice.json`，用量畫面依目前供應商分開顯示。API 未設定價格時顯示「—」，以供應商帳單為準；若在設定檔指定 `ai_price_provider`、`ai_price_model`、每百萬 token 的 `ai_input_price`／`ai_output_price`，可估算費用，但快取與特殊計價仍需核對官方帳單。

## 更新與移除

原始碼版在目前分支執行 `git pull --ff-only`。Windows 安裝版重新下載此分支的安裝檔，更新到原資料夾。此分支包含上游 1.4.4、直播歌詞與面板換行修正；舊歌曲可按「更新旋律分析」，不用重新分軌。

Windows「完整移除」預設保留歌曲與設定，可選擇清除。只清理本程式記錄或設定的 Ollama 模型；其他模型、系統 Python 與驅動會保留。沒有其他模型時才可選擇一併解除安裝 Ollama。即使改用 API，之前下載的本機模型仍可由完整移除工具清理。

## 開發與驗證

```sh
python -m venv .venv
# 啟用虛擬環境後：
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
node tests/settings_smoke.js
node tests/overlay_smoke.js
python app.py --no-browser
```

Windows 安裝檔以 `sh installer/build.sh` 建置，需要 NSIS。Mac 請使用 [macos-ai-choice 分支](https://github.com/samael-leung/Leihu-singsing/tree/macos-ai-choice)。Linux 環境已驗證模擬三家 API 的請求／回應、切換供應商、金鑰隱藏、硬體選模、下載失敗與恢復、設定介面及清理邏輯。尚未以真實 API 額度測試三家模型，也尚未驗證 Windows GUI／GPU 與 Mac Homebrew／Metal／麥克風。

## 使用的開源專案

[audio-separator](https://github.com/nomadkaraoke/python-audio-separator)（UVR MDX-Net 模型）、[torchcrepe](https://github.com/maxrporter/torchcrepe)、[faster-whisper](https://github.com/SYSTRAN/faster-whisper)、[OpenCC](https://github.com/BYVoid/OpenCC)、[pedalboard](https://github.com/spotify/pedalboard)、[yt-dlp](https://github.com/yt-dlp/yt-dlp)、[pywebview](https://github.com/r0x0r/pywebview)、[LRCLIB](https://lrclib.net/)。

## 授權

雷虎練唱台 © 2026 雷虎肯茲（Leihustore）。授權條款見 [LICENSE.md](LICENSE.md)（PolyForm Noncommercial 1.0.0，加上作者的附加許可）：

- **可以**：個人練唱、學習，以及實況直播使用（包含有訂閱、贊助收入的實況）
- **可以**：修改並免費分享原版或修改版，但須註明來源（雷虎練唱台／雷虎肯茲 Leihustore，附上本專案網址）並保留 LICENSE.md
- **不可以**：把本工具或修改後的版本打包販售、收費散布，或做成付費商品、付費服務

本工具使用 AI 開發，並調度多項 AI 工具協作，可能發生不明狀況。免費提供，安裝或使用即視同同意：使用過程中發生的任何狀況與損害由使用者自行承擔，開發者不負損害賠償責任。

使用的第三方套件和模型各有自己的授權。匯入的歌曲與歌詞版權屬於原權利人，請只匯入你有權使用的音樂。

## 音訊強制對齊（中文普通話／英文）

在「貼上正確歌詞」貼上整首、同一演唱版本的完整歌詞，選擇語言，按「依音訊強制對齊」。它以主唱 `lead.wav` 的 Wav2Vec2／CTC 聲學模型搜尋逐字時間，不需要 Ollama 或 API 金鑰；會保留原本的繁體顯示文字，儲存 Enhanced LRC 的逐字時間。原本的 AI 對齊仍可使用。

中文對齊改用 `ydshieh/wav2vec2-large-xlsr-53-chinese-zh-cn-gpt`，公開字典包含 7,322 個漢字（含繁體與簡體），涵蓋「眠、徘、徊、愛、臺、灣、鬱、體」等字。模型訓練包含轉為簡體的台灣中文語音資料；對齊優先使用簡體標籤，缺少時嘗試原字，繁體歌詞顯示不變。此模型仍未涵蓋所有罕見字，字典較大也不代表歌唱對齊一定更準。已使用舊模型者，更新後首次中文對齊會自動下載新模型，無需手動修改設定或刪除舊模型。

首次會從 Hugging Face 下載對齊模型至 `models/alignment/`；中文模型約 1.2 GB，英文約 360 MB，請預留額外空間。下載後可離線使用。對齊使用 CPU，音訊每次推論約 20 秒並保留重疊，整首歌曲會在背景工作中搜尋完整順序；不需要重做分軌或重新辨識歌詞。唱歌、長尾音、錯漏字、缺少副歌或不同版本仍可能不準，完成後請播放確認。

更新程式後需更新相依套件：Mac 執行 `bash setup/install-mac.sh`，Windows 安裝版重新下載本分支的最新版安裝檔並更新到原資料夾；原始碼版在虛擬環境執行 `python -m pip install -r requirements.txt`。對齊模型會在第一次按按鈕時下載，不會在安裝時強制下載。

不支援的字元（例如未唱成文字的數字）、不合理時間或過多低信心字詞會顯示錯誤，保留原歌詞；對齊期間若手動修改歌詞，也不會覆寫新的內容。原生模型工作隔離在子程序，記錄位於 `logs/alignment-worker.log`。目前支援中文普通話與英文，尚未加入日文／韓文／粵語模型。

已驗證預訓練英文模型對官方語音樣本的時間對齊、中文模型字典與繁簡轉換、逐字格式及失敗保護；歌唱效果與 Mac／Windows 實機仍需確認。這項實作使用 Wav2Vec2／CTC 對齊，沒有安裝 WhisperX 全套套件。

## YouTube 播放清單批量匯入

在歌曲庫展開「YouTube 播放清單批量匯入」，貼上含 `list=` 的清單網址，按「讀取清單」。勾選歌曲後按「匯入勾選歌曲」，會沿用目前分類，逐首下載、分軌、分析旋律與辨識歌詞。單首 YouTube 匯入仍使用原本的輸入欄位；帶播放清單參數的單首網址也只下載該影片。

每次最多列出／匯入 200 首，大型清單可按「下一批 200 首」或修改起始項目。可在「匯入批次」切換最近批次，查看每首進度、完成、略過與失敗原因。私人、已刪除或無法存取的影片會停用或顯示失敗，不會阻擋其他歌曲。重複選擇、已存在或已在佇列的歌曲不會重複下載。

「停止尚未開始的歌曲」保留正在處理的歌曲，停止後面的等待項目；「重試失敗／中斷項目」只重新排入失敗、中斷或停止項目，並沿用已有歌曲紀錄與完成的音訊步驟。程式關閉後，批次資訊保存在 `library/.youtube-batches/`，重新啟動可重試；不會自動開始全部下載。

批次、重試、停止、單首相容性與實際瀏覽器操作已驗證。雲端環境的網路代理拒絕 YouTube 連線，因此真實播放清單下載仍需在本機測試；一般使用仍受 YouTube 存取與影片可用性限制。

## 點歌系統同步

此分支可搭配包含雷虎整合 API 的 `samael-leung/twitch-song-request-system`：在練唱台勾選「同步點歌系統『正在播放』」即可雙向選歌。必須同時部署兩個專案的整合變更，既有安裝檔不會自動更新。

預設連接本機點歌系統的 `http://127.0.0.1:3000`；可在啟動練唱台前設定 `SONG_REQUEST_URL`。請使用受信任的本機／私有網路端點。同步由開啟中的練唱台視窗每秒執行，預設關閉；首次啟用以點歌系統目前歌曲為準，不會自動播放。

不需安裝 ngrok 或其他同步軟體。點歌系統的整合分支已合併最新上游，使用其瀏覽器設定精靈授權 Twitch 並自動更新憑證；啟動後依設定精靈操作即可。詳見點歌系統的 `TWITCH_WEBSOCKET.md`；練唱台沿用既有環境即可。

1.4.6 會自動清理 YouTube 標題中的「歌詞／Official MV／HD」等附加文字，結合歌手、YouTube 曲名、線上歌詞曲名與繁簡體別名比對。例如「下一個天亮」可自動對應「郭靜 下一個天亮 歌詞」，不需要重新命名下載檔案。明確且唯一的結果會直接選取；同名或不同版本無法區分時，按候選按鈕確認一次即可，之後重啟也會記住。需要修正時按「更改對應」，或在歌曲庫手動開啟正確歌曲。

對應記錄儲存在本機 `song-request-links.json`，不含密鑰且不會上傳 Git；更新程式不會覆蓋它。反向選歌會優先使用記住的歌名，或比對點歌系統的歌曲清單，保留原本歌名、點歌者與調音，避免新增重複項目。歌曲仍須先匯入並完成旋律分析；沒有新增下載或分析步驟。選歌當下不記錄歷史，唱完才依點歌系統規則記錄。建議只開啟一個同步視窗，兩個專案皆須更新到整合分支最新版。

## 整合版 1.6.2

本版合併原作者 `LeihuTW/Leihu-singsing` 的 1.6.1（`556d618`）：遠端開歌與 KEY、繁簡搜尋、歌手／曲名／預設 KEY 表單、排序與分組、FLAC 分軌與容量整理、預先下載、背景歌詞搜尋及精細處理。也包含先前日文標音、字體、USB 麥克風、錄音與匯出的上游改善。保留本機／Claude／Gemini／OpenAI 選擇、音訊強制對齊、YouTube 播放清單批量匯入、點歌系統雙向同步、YouTube 歌名自動比對及記住對應。

後續更新只發佈至本儲存庫的 `leihu-song-request-sync` 分支。已有 1.4.4～1.6.1 安裝可使用 1.6.2 Update.exe 更新程式，不用重新安裝執行環境；歌曲、API 設定與歌曲對應紀錄保留。上游的高品質分離模型首次使用會在背景下載約 900 MB；下載完成前先用標準模型，可在設定選「標準」沿用原本模型。重新辨識歌詞不會覆蓋手動編輯、各 AI 供應商或音訊強制對齊的歌詞。

日文標音使用本機 SudachiPy 字典。舊版直接使用 Update.exe 即可，首次啟用標音時會在背景下載約 45 MB 的 Python 字典套件，不必重裝主程式或另外安裝同步軟體；完整 Setup.exe 會預先安裝字典。內建字體及授權檔隨程式更新，不需安裝系統字體。

安全更新：requirements 已更新 certifi／Pillow，並提供獨立 Python 3.13 執行環境的遷移腳本；**Update.exe 本身不更新 Python 核心或既有套件**。Node.js、Python／pip 與憑證事件的 PowerShell 指令及驗證範圍見 [2026 年 10 月安全更新說明](SECURITY_UPDATE_2026-10.md)。舊版內嵌 Python 3.11.9 需另外遷移，不能只更新系統 Python。
