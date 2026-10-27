' OpenMontage Silent Windows Launcher (Phase 12)
' Launches OpenMontage without an obtrusive command prompt window.

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strCurrentDir = fso.GetParentFolderName(WScript.ScriptFullName)

WshShell.CurrentDirectory = strCurrentDir
WshShell.Run """" & strCurrentDir & "\OpenMontage.bat""", 0, False
