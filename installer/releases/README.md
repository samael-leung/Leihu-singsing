# Windows AI 選擇版 1.4.4

- [安裝檔](./LeihuLiantai-windows-ai-choice-1.4.4-Setup.exe)
- [完整移除工具](./LeihuLiantai-windows-ai-choice-1.4.4-CleanUninstall.exe)

首次啟動可選本機 Ollama 或 Claude／Gemini／OpenAI API。API 模式不下載 Ollama 或語言模型。本機模式在儲存設定後依硬體選模、下載並驗證；也可指定模型。

已有安裝請關閉程式，安裝到原資料夾並選更新，保留歌曲、錄音、設定及模型。完整移除預設保留資料，API-only 安裝不會清理其他程式的本機模型；曾使用本機模式時仍可清理已記錄的模型。

來源提交：`400849111294808cf500d379a7aeaa9ec84afb58`。以 NSIS 3.11 建置，SHA-256 見 [SHA256SUMS](./SHA256SUMS)。供應商合約、設定介面、硬體選模及清理測試通過；Windows GUI／GPU、真實 API 帳戶仍需實機驗證。安裝檔未簽章。此目錄其他 localModel 檔案為歷史版本，請使用上方 AI 選擇版下載。

新增音訊強制對齊：中文普通話／英文，以 Wav2Vec2／CTC 對齊主唱音訊並儲存逐字時間，不需要 API。首次按「依音訊強制對齊」會下載對齊模型；請貼上整首、同版本的完整歌詞。已有 1.4.4 請重新下載安裝檔更新，以安裝新增套件。
