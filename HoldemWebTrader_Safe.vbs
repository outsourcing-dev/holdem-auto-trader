Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' 현재 스크립트 경로 가져오기
strPath = objFSO.GetParentFolderName(WScript.ScriptFullName)

' 포트 8000을 사용하는 프로세스 종료
' netstat로 포트 8000 사용 중인 프로세스 찾기
Set objExec = objShell.Exec("cmd /c netstat -ano | findstr :8000")
strOutput = objExec.StdOut.ReadAll()

If Len(strOutput) > 0 Then
    ' 포트 8000을 사용하는 프로세스가 있으면
    arrLines = Split(strOutput, vbCrLf)
    For Each strLine in arrLines
        If InStr(strLine, "LISTENING") > 0 Then
            ' PID 추출
            arrParts = Split(Trim(strLine), " ")
            strPID = ""
            For i = UBound(arrParts) To 0 Step -1
                If IsNumeric(arrParts(i)) And Len(arrParts(i)) > 0 Then
                    strPID = arrParts(i)
                    Exit For
                End If
            Next
            
            If strPID <> "" Then
                ' 프로세스 종료
                objShell.Run "taskkill /PID " & strPID & " /F", 0, True
                WScript.Sleep 1000 ' 1초 대기
            End If
        End If
    Next
End If

' backend 디렉토리로 이동
strBackendPath = strPath & "\backend"

' Python 서버를 백그라운드에서 실행
objShell.Run "cmd /c cd /d """ & strBackendPath & """ && python main.py", 0, False

' 3초 대기
WScript.Sleep 3000

' 브라우저 열기
objShell.Run "http://localhost:8000"

' 사용자가 프로그램을 종료할 때까지 대기
MsgBox "홀덤 웹 트레이더가 실행 중입니다." & vbCrLf & vbCrLf & "프로그램을 종료하려면 확인을 누르세요.", vbInformation, "홀덤 웹 트레이더"

' 서버 종료
Set objExec = objShell.Exec("cmd /c netstat -ano | findstr :8000")
strOutput = objExec.StdOut.ReadAll()

If Len(strOutput) > 0 Then
    arrLines = Split(strOutput, vbCrLf)
    For Each strLine in arrLines
        If InStr(strLine, "LISTENING") > 0 Then
            arrParts = Split(Trim(strLine), " ")
            strPID = ""
            For i = UBound(arrParts) To 0 Step -1
                If IsNumeric(arrParts(i)) And Len(arrParts(i)) > 0 Then
                    strPID = arrParts(i)
                    Exit For
                End If
            Next
            
            If strPID <> "" Then
                objShell.Run "taskkill /PID " & strPID & " /F", 0, True
            End If
        End If
    Next
End If