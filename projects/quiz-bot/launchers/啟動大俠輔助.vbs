Dim fso, dir, script
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
script = fso.GetAbsolutePathName(fso.BuildPath(dir, "..\tools\daxi_bot.py"))
CreateObject("WScript.Shell").Run """D:\tset\FlyCatClaude\pythonw.exe"" """ & Chr(34) & script & Chr(34), 0, False
