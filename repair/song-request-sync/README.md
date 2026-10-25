# 點歌系統 404 相容修復包

適用於使用者提供的這套點歌系統：`server/leihu.js` 匯出 `start/getStatus/getLibrary/setLink/...`，`server/index.js` 已有 `/api/leihu/status`，但缺少練唱台 1.6.6 使用的 `/api/integrations/leihu/selection`。

這不是替換原有的雷虎整合。新增 `server/leihu-selection-compat.js`，只在既有 `/api/leihu/status` 前加入一行掛載。保留 `server/leihu.js`、`server/queue.js`、.env、song-links.json、package.json、套件及既有匯入／歌詞／遠端開歌功能。使用原有 Node.js，不需 Git、ngrok 或額外服務；不必重裝練唱台。

## 安裝

先完成或記錄目前尚未唱完的佇列；若點歌系統只在記憶體保存佇列，重新啟動後不會自動恢復。本工具保留原始碼與設定備份，不會重建重啟前的記憶體狀態。

1. 在執行點歌系統 `npm start` 的視窗按 Ctrl+C。安裝工具會拒絕在 3000 埠仍被監聽時繼續；不會自動終止其他程序。
2. 下載並解壓本修復包，先核對提供的 SHA-256 並檢視腳本。
3. 從解壓資料夾執行：

```powershell
powershell -NoProfile -ExecutionPolicy RemoteSigned -File '.\install.ps1' -ProjectDir 'E:\songRequest'
```

腳本會檢查檔案、佇列函式介面及現有路由位置。介面不同時會停止，不會猜測覆寫。既有 index.js 會逐位元組備份至 `E:\songRequest\backups\leihu-sync-時間-隨機碼\index.js`，並產生可安全還原的紀錄。BOM、換行與其他路由保留。寫入前會用 `node --check` 檢查原檔、模組及修改後的檔案；套用失敗會回復原 index.js。重複安裝會停止。

工具依提供的模組匯出和既有佇列 API 編寫；未取得使用者完整 queue.js。安裝工具會檢查已知函式簽章，但 Windows 安裝／使用者實際佇列行為仍需下面的啟動驗證。

4. 重新啟動並保持視窗開啟：

```powershell
Set-Location -LiteralPath 'E:\songRequest'
npm start
```

5. 在另一個 PowerShell 視窗確認：

```powershell
Invoke-RestMethod 'http://127.0.0.1:3000/api/integrations/leihu/selection'
```

應回傳 `revision` 和 `nowPlaying`（空佇列時 nowPlaying 為 null）。回到練唱台關閉再勾選同步，將一首歌移到正在播放，確認自動開歌；再從練唱台選另一首歌，確認點歌系統同步並保留上一首及點歌者。

若出現 EADDRINUSE，仍有其他服務占用 3000 埠。若出現 500／Unsupported queue，請保留伺服器錯誤訊息並還原，不要重複覆寫其他檔案。此包不會呼叫 Twitch／Google API，也不會改動授權設定。

## 還原

先 Ctrl+C 停止點歌系統，再從同一份解壓資料夾執行：

```powershell
powershell -NoProfile -ExecutionPolicy RemoteSigned -File '.\install.ps1' -ProjectDir 'E:\songRequest' -Undo
```

還原會檢查檔案 SHA-256；若安裝後您又改動 index.js 或相容模組，工具會停止，避免抹掉後續變更。可依備份資料夾手動合併。

## 驗證範圍

8 項 Node 測試涵蓋實際 HTTP 端點、既有原生 API 保留、只綁定不替換歌曲、保留 requester/key/isRandom、反向選歌、上一首保留、空白正在播放但已有佇列、新增歌曲、待確認候選歌手選擇、唱過歌曲重用、版本衝突、跨來源與格式驗證、重複請求、備份、編碼／換行保留及安全還原。

測試使用獨立的記憶體佇列測試檔，源自點歌系統既有公開佇列 API，不操作您的實際佇列或 .env。測試可選擇在 E:\songRequest 執行，依賴現有 express：

```powershell
node --test '修復包解壓位置\tests\compat.test.js'
```

另以真實 Flask 與 Chromium 驗證相容 API 配合練唱台的模糊比對、正反向同步、保留點歌者、跳歌、配對重新載入與日文功能。Windows PowerShell 包裝腳本及使用者完整部署尚未實機驗證。
