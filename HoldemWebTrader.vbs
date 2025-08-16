Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' 현재 스크립트 경로 가져오기
strPath = objFSO.GetParentFolderName(WScript.ScriptFullName)

' backend 디렉토리로 이동
strBackendPath = strPath & "\backend"

' Python 서버를 백그라운드에서 실행
objShell.Run "cmd /c cd /d """ & strBackendPath & """ && python main.py", 0, False

' 3초 대기
WScript.Sleep 3000

' 브라우저 열기
objShell.Run "http://localhost:8000"