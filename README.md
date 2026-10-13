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

歌曲處理都在本機完成（有 NVIDIA 顯示卡時用 GPU 加速）。「AI 精準對齊歌詞」與「練習建議」改由本機 Ollama 執行，無需 API 金鑰或雲端模型費用。

## 本機模型分支（localModel）

1. Windows 安裝程式會沿用現有 Ollama；若尚未安裝，會下載官方安裝檔、驗證 Windows 簽章後靜默安裝。
2. 安裝與「修復與更新」會啟動 Ollama，自動下載設定中的模型（預設 `qwen2.5:14b`，約 9GB），並執行短回覆驗證。已有模型會重用，中斷可續傳；失敗時不會留下安裝完成標記。建議 24GB 顯示記憶體，長上下文會增加需求。
3. 在練唱台「設定」確認 Ollama 網址 `http://127.0.0.1:11434` 與模型 `qwen2.5:14b`。服務未啟動或模型未下載時，狀態會顯示不可用。
4. 歌詞對齊使用 Ollama JSON Schema，練習建議使用繁體中文文字回覆。請先用短歌詞測試；模型效果不保證與雲端模型相同。

每次呼叫完成後以 `keep_alive: 0` 釋放模型，減少與 Whisper／UVR 搶 GPU 記憶體。呼叫最多等待 10 分鐘。本機 token 紀錄保存在 `usage-local.json`，API 費用為零，未包含電力與硬體成本。模型預設存在 `%USERPROFILE%\.ollama\models`，或你已設定的 `OLLAMA_MODELS` 目錄，不會複製進練唱台資料夾。Ollama 是共用的獨立程式；一般解除安裝會保留 Ollama 與模型；新版「完整移除」工具可一併清理，見下方說明。Ollama 安裝本體至少需約 4GB，另加 9GB 模型與原本音訊模型，請預留約 20GB 磁碟空間。Windows 需 10 22H2 以上，NVIDIA 建議驅動 551.61 以上。

## 更新至 1.4.4

此分支已合併上游 1.4.2／1.4.3／1.4.4：旋律辨識補斷點與修正八度、舊歌曲「更新旋律分析」、旋律顯示開關、OBS 去背直播歌詞。新增可關閉失敗訊息，以及實際測試 CUDA 運算、必要時退回相容版本或 CPU 的功能。模型設定與完整移除工具保留。

已有安裝：關閉程式，以本分支新版安裝檔安裝到原位置，選「是：更新」。不用先解除安裝；歌曲、錄音、設定及已下載模型會保留。舊歌曲可按「更新旋律分析」，只重做旋律，不會重新分軌或改動歌詞、錄音。

練習建議的輸出上限提高至 3,000 tokens；只有回覆被截斷時，才以 12,000 tokens 上限重試一次。OpenAI 版會記錄兩次實際用量與費用，本機版沒有 API 費用。第二次仍被截斷時會顯示錯誤，不會儲存不完整的建議。

OBS 使用者可在練唱畫面按「直播歌詞」，複製網址到 OBS 的「瀏覽器」來源；練唱台要保持開著。

## 從原始碼執行與測試

Linux 後端使用 `requirements.txt`；Windows 桌面版使用 `requirements-win.txt` 並由原安裝流程處理 PyTorch。

```sh
python -m venv .venv
# 啟用虛擬環境後：
python -m pip install -r requirements.txt
python app.py --no-browser
```

```sh
python -m unittest discover -s tests -v
# 若環境有 Node.js，可驗證前端設定操作：
node tests/settings_smoke.js
node tests/overlay_smoke.js
```

測試以模擬服務驗證請求格式、錯誤、用量、設定金鑰遮罩及 Flask 對齊／建議流程，不需付費金鑰或下載大型模型。實際 AI 品質仍需在安裝模型或提供 API 金鑰後檢驗。

## 安裝

到 [Releases](../../releases) 下載最新版的 `LeihuLiantai-<版本>-Setup.exe`（雷虎練唱台安裝檔），雙擊安裝。安裝程式會自動：

1. 下載內嵌版 Python 3.11（不影響電腦上原本的 Python）
2. 偵測顯示卡，安裝對應的 PyTorch（CUDA 12.8／12.6 或 CPU 版）
3. 下載分離與辨識模型（約 2 GB）
4. 安裝 Ollama 並下載本機語言模型（預設 Qwen2.5 14B，約 9 GB）
5. 建立桌面與開始選單捷徑

安裝視窗會顯示總進度和下載速度。第一次安裝需要連網，依網速可能需要 30–90 分鐘，之後可以離線使用。安裝中斷時重新執行安裝檔即可，會接著下載並自動修復不完整的檔案。詳細操作見 [使用說明](static/help.html)。

系統需求：Windows 10 22H2／11 64 位元、建議預留約 20 GB 磁碟空間；建議 NVIDIA 顯示卡（驅動支援 CUDA 12.6 以上）。

## 一鍵完整移除

安裝後可從桌面或開始選單點「雷虎練唱台 完整移除」，也可以下載本分支 `installer/releases/` 中的 `CleanUninstall.exe`。工具不依賴練唱台的 Python 或第三方套件。若安裝中斷且尚未登錄安裝位置，請從安裝資料夾內執行 `clean-uninstall.exe`。

確認後會關閉練唱台，移除內嵌 Python／套件、音訊模型、下載暫存、程式與捷徑。預設保留歌曲庫、錄音及設定（含 API 金鑰）；取消勾選保留選項才會一併刪除。

本機版會刪除目前設定與安裝紀錄中的 Ollama 模型。其他模型與其共用模型層會保留；遠端 Ollama 不會被清理。若沒有其他模型，可勾選一併解除安裝 Ollama 並清除未完成的模型下載暫存。新版安裝程式會記錄是否由練唱台安裝 Ollama；舊版或來源不明時，Ollama 預設保留，需自行勾選。

不會移除系統 Python、顯示卡驅動或其他程式套件。不會跟隨資料夾連結刪除外部檔案。清理失敗會保留進度紀錄，可重新執行。Windows 的一般「解除安裝」維持原本流程；要清除本機 AI 共用資源，請使用「完整移除」。

## 從原始碼建置安裝檔

從原始碼執行時，仍需自行安裝 [Ollama](https://ollama.com/download) 並執行 `ollama pull qwen2.5:14b`。程式在 Windows 啟動時會嘗試啟動已安裝的本機 Ollama；自訂遠端網址需自行提供服務。

需要 [NSIS](https://nsis.sourceforge.io/)：

```sh
sh installer/build.sh
```

產生的安裝檔在 `installer/out/`。

## 檔案結構

| 檔案 | 用途 |
| --- | --- |
| `app.py` | 本機伺服器（Flask） |
| `desktop.py` | 桌面視窗（pywebview），伺服器在另一個行程執行 |
| `pipeline.py` | 分軌、音高、歌詞辨識、線上歌詞搜尋、歌曲庫 |
| `ai_api.py` | 呼叫本機 AI 並記錄 token 用量與費用 |
| `share.py` | 錄音混音、匯出音訊、直式影片與成績卡 |
| `ollama_setup.py` | 尋找／啟動 Ollama、續傳模型下載與載入檢查 |
| `installer.py` | 安裝時偵測顯示卡、安裝套件、下載模型 |
| `setup/install.ps1` | 安裝檔呼叫的 PowerShell 安裝腳本 |
| `installer/leihu.nsi` | NSIS 安裝檔腳本 |
| `static/` | 介面（HTML／JS／CSS）與使用說明 |

API 金鑰、歌曲庫、用量紀錄都存在安裝資料夾裡的 `config.json`、`library/`、`usage-local.json`，不會被提交到這個 repo（見 `.gitignore`）。

## 使用的開源專案

[audio-separator](https://github.com/nomadkaraoke/python-audio-separator)（UVR MDX-Net 模型）、[torchcrepe](https://github.com/maxrporter/torchcrepe)、[faster-whisper](https://github.com/SYSTRAN/faster-whisper)、[OpenCC](https://github.com/BYVoid/OpenCC)、[pedalboard](https://github.com/spotify/pedalboard)、[yt-dlp](https://github.com/yt-dlp/yt-dlp)、[pywebview](https://github.com/r0x0r/pywebview)、[LRCLIB](https://lrclib.net/)。

## 授權

雷虎練唱台 © 2026 雷虎肯茲（Leihustore）。授權條款見 [LICENSE.md](LICENSE.md)（PolyForm Noncommercial 1.0.0，加上作者的附加許可）：

- **可以**：個人練唱、學習，以及實況直播使用（包含有訂閱、贊助收入的實況）
- **可以**：修改並免費分享原版或修改版，但須註明來源（雷虎練唱台／雷虎肯茲 Leihustore，附上本專案網址）並保留 LICENSE.md
- **不可以**：把本工具或修改後的版本打包販售、收費散布，或做成付費商品、付費服務

本工具使用 AI 開發，並調度多項 AI 工具協作，可能發生不明狀況。免費提供，安裝或使用即視同同意：使用過程中發生的任何狀況與損害由使用者自行承擔，開發者不負損害賠償責任。

使用的第三方套件和模型各有自己的授權。匯入的歌曲與歌詞版權屬於原權利人，請只匯入你有權使用的音樂。
