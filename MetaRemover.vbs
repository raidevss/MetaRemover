Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
pyw = dir & "\venv\Scripts\pythonw.exe"
main = dir & "\main.py"

If Not fso.FileExists(pyw) Then
  MsgBox "Virtual environment not found." & vbCrLf & vbCrLf & _
    "In the MetaRemover folder run:" & vbCrLf & _
    "  python -m venv venv" & vbCrLf & _
    "  venv\Scripts\pip install -r requirements.txt", _
    vbCritical, "MetaRemover"
  WScript.Quit 1
End If

Set sh = CreateObject("Wscript.Shell")
sh.CurrentDirectory = dir

desk = sh.SpecialFolders("Desktop")
lnk = desk & "\MetaRemover.lnk"
If Not fso.FileExists(lnk) Then
  Set sc = sh.CreateShortcut(lnk)
  sc.TargetPath = pyw
  sc.Arguments = Chr(34) & main & Chr(34)
  sc.WorkingDirectory = dir
  sc.WindowStyle = 7
  sc.Description = "MetaRemover"
  sc.Save
End If

sh.Run Chr(34) & pyw & Chr(34) & " " & Chr(34) & main & Chr(34), 0, False
