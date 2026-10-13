; Standalone launcher: no application Python or package dependency.
Unicode true
!include "LogicLib.nsh"
RequestExecutionLevel user
SilentInstall silent
SetCompressor /SOLID lzma
!define /file VERSION "..\VERSION"
Name "雷虎練唱台 ${VERSION} 一鍵完整移除"
OutFile "out\LeihuLiantai-windows-ai-choice-${VERSION}-CleanUninstall.exe"
Icon "..\static\icon.ico"
Section
  StrCpy $0 "$EXEDIR"
  ${IfNot} ${FileExists} "$0\app.py"
    ReadRegStr $0 HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LeihuLiantai" "InstallLocation"
    ${If} $0 == ""
      StrCpy $0 "$LOCALAPPDATA\LeihuLiantai"
    ${EndIf}
  ${EndIf}
  System::Call 'kernel32::GetCurrentProcessId() i.r1'
  StrCpy $2 "$TEMP\LeihuCleanup-$1"
  SetOutPath "$2"
  File /oname=clean-uninstall.ps1 "..\setup\clean-uninstall.ps1"
  StrCpy $3 "$WINDIR\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
  ${IfNot} ${FileExists} "$3"
    StrCpy $3 "$SYSDIR\WindowsPowerShell\v1.0\powershell.exe"
  ${EndIf}
  ; Exit immediately so the PowerShell cleanup can delete this launcher too.
!ifdef LOCAL_MODEL
  Exec '"$3" -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "$2\clean-uninstall.ps1" -AppDir "$0" -LocalModel -HybridAI'
!else
  Exec '"$3" -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "$2\clean-uninstall.ps1" -AppDir "$0"'
!endif
  ${If} ${Errors}
    MessageBox MB_ICONSTOP "無法啟動完整移除工具，請確認 Windows PowerShell 可用。"
    SetErrorLevel 1
  ${EndIf}
SectionEnd
