; Program files only: reuse the existing Python, packages, models and user data.
Unicode true
ManifestDPIAware true
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "TextFunc.nsh"
!define /file VERSION "..\VERSION"
!define REGKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\LeihuLiantai"
Name "雷虎練唱台 ${VERSION} 程式更新"
OutFile "out\LeihuLiantai-windows-ai-choice-${VERSION}-Update.exe"
InstallDir "$LOCALAPPDATA\LeihuLiantai"
InstallDirRegKey HKCU "${REGKEY}" "InstallLocation"
RequestExecutionLevel user
SetCompressor /SOLID lzma
Icon "payload\static\icon.ico"
VIProductVersion "${VERSION}.0"
VIAddVersionKey /LANG=1028 "ProductName" "雷虎練唱台"
VIAddVersionKey /LANG=1028 "FileDescription" "雷虎練唱台 ${VERSION} 程式更新（不安裝套件）"
VIAddVersionKey /LANG=1028 "FileVersion" "${VERSION}"
VIAddVersionKey /LANG=1028 "LegalCopyright" "© 2026 雷虎肯茲 (Leihustore)"
!define MUI_WELCOMEPAGE_TITLE "更新雷虎練唱台至 ${VERSION}"
!define MUI_WELCOMEPAGE_TEXT "適用已安裝的 Windows AI 選擇版 1.4.4／1.4.5／1.4.6／1.4.7／1.4.8。$\r$\n$\r$\n請先儲存錄音並關閉練唱台。這個更新只覆蓋程式檔，不下載或安裝 Python、套件、模型或其他軟體。歌曲庫、錄音、API 金鑰與設定會保留。$\r$\n$\r$\n請選擇原本的安裝資料夾。首次安裝請使用 Setup.exe。"
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchUpdated
!define MUI_FINISHPAGE_RUN_TEXT "開啟雷虎練唱台"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_LANGUAGE "TradChinese"
Function LaunchUpdated
  Exec '"$INSTDIR\python\pythonw.exe" "$INSTDIR\desktop.py"'
FunctionEnd
Section "Update"
  ${IfNot} ${FileExists} "$INSTDIR\python\python.exe"
    MessageBox MB_ICONSTOP "找不到既有的 Python。請選原安裝資料夾，首次安裝請使用 Setup.exe。"
    Abort
  ${EndIf}
  ${IfNot} ${FileExists} "$INSTDIR\installed.json"
    MessageBox MB_ICONSTOP "原本的安裝尚未完成。請先用 Setup.exe 修復安裝。"
    Abort
  ${EndIf}
  FileOpen $0 "$INSTDIR\VERSION" r
  IfErrors unsupported
  FileRead $0 $1
  FileClose $0
  ${TrimNewLines} $1 $1
  ${If} $1 != "1.4.4"
  ${AndIf} $1 != "1.4.5"
  ${AndIf} $1 != "1.4.6"
  ${AndIf} $1 != "1.4.7"
  ${AndIf} $1 != "1.4.8"
    Goto unsupported
  ${EndIf}
  StrCpy $2 "$WINDIR\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
  ${IfNot} ${FileExists} "$2"
    StrCpy $2 "$SYSDIR\WindowsPowerShell\v1.0\powershell.exe"
  ${EndIf}
  nsExec::Exec `"$2" -NoProfile -NonInteractive -Command "Get-CimInstance Win32_Process | Where-Object { $$_.ExecutablePath -like '$INSTDIR\python\*' } | ForEach-Object { Stop-Process -Id $$_.ProcessId -Force }"`
  Pop $0
  Sleep 1500
  SetOutPath "$INSTDIR"
  File /r "payload\*"
  WriteRegStr HKCU "${REGKEY}" "DisplayVersion" "${VERSION}"
  Goto done
unsupported:
  MessageBox MB_ICONSTOP "程式更新僅適用 Windows AI 選擇版 1.4.4／1.4.5／1.4.6／1.4.7／1.4.8。其他版本請使用 Setup.exe 的更新選項。"
  Abort
done:
SectionEnd
