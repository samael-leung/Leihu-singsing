# 雷虎練唱台

在自己電腦上跑的 Windows 練歌工具。匯入一首歌（音訊檔或 YouTube 網址），它會：

- 用 AI 模型把歌拆成**主唱、合音、伴奏**三軌
- 分析主唱的**旋律**，可切換「原聲曲線」或「音符區塊」顯示
- **辨識歌詞**並對上時間，中文轉成台灣繁體；也會到 LRCLIB、網易雲、酷狗搜尋歌詞，與辨識結果比對後讓你選一版；也可以匯入 LRC／SRT／TXT 歌詞檔
- **升降 KEY、調整速度**練唱（用所有 CPU 核心轉換）；唱的時候會依你的音域**建議適合的 KEY**
- 可以關掉旋律只看歌詞（五行）；也有給 OBS 用的**去背直播歌詞**畫面，跟著播放同步上色
- 開麥克風時即時顯示你的音高，有音量表、增益與自動調整、防爆音；錄音後在本機**自動評分**，標出最需要練的句子
- 把你的錄音和合音、伴奏混音後**匯出 MP3／WAV、直式影片（旋律線條＋歌詞）或成績卡圖片**，一鍵開啟 FB、IG、X、Threads 分享
- 歌曲庫可自訂分類（例如中文歌、日文歌）並用關鍵字搜尋

歌曲與錄音處理在本機執行。首次啟動會開啟設定，讓使用者選擇 **本機模型** 或 **API**；API 可選 **Claude、Gemini、OpenAI**，之後隨時可以切換。

## Windows 安裝（windows-ai-choice）

到 [installer/releases](installer/releases) 下載 `LeihuLiantai-windows-ai-choice-1.4.4-Setup.exe`。安裝到可寫入的資料夾，首次開啟後選擇 AI 模式。安裝程式先準備 Python、音訊套件及 UVR／Whisper；這一步不會下載 Ollama 或本機語言模型。已有安裝請關閉程式，安裝到原位置並選「更新」，保留歌曲、錄音與設定。

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
