# 本機模型版 Windows 安裝與完整移除工具

- [安裝檔](./LeihuLiantai-localModel-1.4.1-Setup.exe)：自動準備 Ollama 與 Qwen2.5 14B，首次需網路與約 20GB 磁碟空間。
- [一鍵完整移除](./LeihuLiantai-localModel-1.4.1-CleanUninstall.exe)：確認後移除套件、音訊與本機 AI 模型，預設保留歌曲、錄音與設定，可取消勾選一併清除。

沒有其他模型時可一併移除 Ollama 與模型下載暫存；舊版或來源不明的 Ollama 預設保留，需自行勾選。其他模型、系統 Python、顯示卡驅動會保留。新版安裝檔會建立「完整移除」捷徑。若安裝中斷且尚未登錄路徑，請從安裝資料夾內執行 clean-uninstall.exe。

來源提交：`35484936cd853cd35cb69b04183e970ea4b4fdcf`。以 NSIS 3.11 建置，SHA-256 見 [SHA256SUMS](./SHA256SUMS)。檔案未經程式碼簽章；清理邏輯已測試，Windows GUI 與實際解除安裝仍需實機驗證。
