Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")
projectFolder = fileSystem.GetParentFolderName(WScript.ScriptFullName)
shell.Run """" & projectFolder & "\Start_EDITH.bat"" hidden", 0, False
