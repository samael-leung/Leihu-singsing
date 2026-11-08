# sheng7337 點歌系統：雷虎同步 404 修復

適用於 [sheng7337/twitch-song-request-system](https://github.com/sheng7337/twitch-song-request-system) 的 2026.11-1／`master`（`00d83d0422fb5ae9b207094f8956005b23f38277`），以及先前使用者提供的原生雷虎整合版本。已在原作者完整原始碼上實際安裝修復、啟動伺服器、呼叫兩組 API 並重新啟動驗證。

練唱台 1.6.9 的「點歌系統回應錯誤（404）」是點歌伺服器缺少 `/api/integrations/leihu/selection`。不需要重裝或更新練唱台；原作者的 `/api/leihu/status` 等原生功能會保留。

工具只新增／更新 `server/leihu-selection-compat.js`，並在 index.js 的 `/api/leihu/status` 前掛載一行。保留原有 server/leihu.js、server/queue.js、package.json、相依套件、.env、song-links.json、queue-state.json、聊天室及其他本機設定。沿用現有 Node.js，不需 Git、ngrok 或其他軟體。修復不呼叫 Twitch／Google API。

## 安裝

1. 先在點歌系統 `npm start` 的視窗按 Ctrl+C。原作者新版會保存近期佇列並於六小時內重啟恢復；更舊版本可能只有記憶體佇列，請先記錄未唱完的歌曲。
2. 下載 ZIP，核對 [SHA256SUMS](../SHA256SUMS) 後解壓縮；檢視腳本。
3. 在修復包解壓資料夾執行：

```powershell
powershell -NoProfile -ExecutionPolicy RemoteSigned -File '.\install.ps1' -ProjectDir 'E:\songRequest'
```

PowerShell 包裝腳本會在 3000 埠仍被占用時停止，不會自行終止程序。若直接使用既有 Node.js 執行，請先自行停止伺服器：

```powershell
node '.\install.js' 'E:\songRequest'
if ($LASTEXITCODE -ne 0) { throw '修復失敗，請保留上方訊息。' }
```

工具先檢查檔案、佇列函式與原生路由，並用 node --check 檢查語法。會將原 index.js、已知舊相容模組與舊修復紀錄逐位元組備份至 `E:\songRequest\backups\leihu-sync-時間-隨機碼`。保留 BOM 和換行，寫入失敗會回復；介面不符或相容模組有自訂修改時停止，不猜測覆寫。

已是新版時，重複安裝不再修改檔案。若原作者更新覆蓋 index.js，遺留了先前的相容模組／修復紀錄，可以重新套用；已知舊修復會備份後升級。

4. 在原專案啟動並保持視窗開啟：

```powershell
Set-Location -LiteralPath 'E:\songRequest'
npm start
```

5. 在另一個 PowerShell 驗證：

```powershell
Invoke-RestMethod 'http://127.0.0.1:3000/api/integrations/leihu/selection'
```

應回傳 revision 與 nowPlaying；空佇列時 nowPlaying 為 null。回到練唱台關閉再勾選同步。點歌系統將歌曲移至「正在播放」後，練唱台應自動選取；從練唱台選另一首歌曲時，點歌系統應同步且保留上一首和點歌者。

同步使用原生佇列公開函式。只綁定對應或修正待審核候選後，會透過原生儲存／廣播路徑保存 queue-state.json，重新啟動仍可恢復 leihuId 與正確候選；保留點數兌換，唱完才依原作者規則完成，不在選歌時提前完成或退還。原生 setLink 會保存 song-links.json，保留原作者的歌曲狀態與 KEY 功能。

仍然 404 時，請確認重新啟動的是 `E:\songRequest`，且只有預期的伺服器監聽 3000 埠。EADDRINUSE 表示仍有其他服務占用該埠，不應另外啟動更多副本。

## 還原

Ctrl+C 停止點歌系統後，從同一份修復包執行：

```powershell
node '.\install.js' 'E:\songRequest' --undo
```

工具會檢查 SHA-256，拒絕抹掉安裝後的修改。還原此輪之前的 index.js、舊相容模組與舊修復紀錄；首次安裝則移除新增模組。備份會保留。已修改過檔案時請從備份手動合併。

## 驗證範圍

11 項 Node 測試涵蓋 HTTP API、候選歌手／調音／點歌者、上一首保留、重複與過期請求、跨來源檢查、空白目前歌曲、原生 queue-state.json 保存、點數兌換、備份還原、重複安裝、舊修復升級與原作者更新後重新套用。

測試直接使用上方原作者提交的完整 queue.js（tests/queue-fixture.js），每次寫入獨立暫存資料夾，不操作實際佇列或 .env。可選擇從點歌系統專案執行：

```powershell
Set-Location -LiteralPath 'E:\songRequest'
node --test '修復包解壓位置\tests\compat.test.js'
```

雲端另在未修改的 sheng7337/master 完整原始碼安裝本修復包，確認 leihu.js、queue.js、package.json 位元組不變；原生狀態與選歌端點成功、正反向選歌、原生配對保存、重新啟動後的歌曲／點歌者／KEY／佇列恢復通過。合併版也通過實際 Flask／Node／Chromium 的模糊配對、雙向同步與配對重新載入測試。PowerShell 包裝腳本先前已由使用者執行成功；本次更新的 Node 安裝邏輯未在 Windows 雲端執行。
