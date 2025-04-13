@echo off
chcp 65001 > nul
echo JD Soft 빌드 스크립트 (엑셀 제거됨)
echo =======================================

REM 필요한 패키지 설치
echo 필요한 패키지 설치 여부 확인 중...
pip install -r requirements.txt
pip install pycryptodome
pip install pyinstaller

REM 설정 파일이 존재하는지 확인
echo 설정 파일 확인 중...
if not exist settings.json (
    echo settings.json 파일이 없습니다. 기본 설정 파일을 생성합니다.
    echo {"site1": "https://drdr-1230.com/","site2": "https://drdr-1230.com/","site3": "www.ygosu.com","martin_count": 3,"martin_amounts": [2000,3000,4000],"target_amount": 80000} > settings.json
)

if not exist room_settings.json (
    echo room_settings.json 파일이 없습니다. 빈 파일을 생성합니다.
    echo [] > room_settings.json
)

REM 빌드 시작
echo PyInstaller로 빌드 시작...
pyinstaller --clean "JD Soft.spec"

echo.
echo 빌드 완료!
echo 실행 파일 위치: dist\JD Soft\JD Soft.exe
echo.

REM 파일 복사
echo 필수 파일 복사 확인 중...
if exist "dist\JD Soft" (
    echo 필요한 파일들을 dist 폴더로 복사합니다...

    copy /Y settings.json "dist\JD Soft\"
    copy /Y room_settings.json "dist\JD Soft\"

    REM 아이콘 및 음향 파일 복사
    if exist lover-icon.ico (
        mkdir "dist\JD Soft\_internal" 2>nul
        copy /Y lover-icon.ico "dist\JD Soft\_internal\"
        echo 아이콘 파일을 _internal 폴더로 복사했습니다.
    )

    if exist bbang.wav (
        mkdir "dist\JD Soft\_internal" 2>nul
        copy /Y bbang.wav "dist\JD Soft\_internal\"
        echo 음악 파일을 _internal 폴더로 복사했습니다.
    )

    echo 파일 복사 완료!

    REM 배포용 폴더 생성
    echo 배포용 폴더 생성 중...
    if not exist "dist\JD Soft 배포용" mkdir "dist\JD Soft 배포용"

    xcopy /E /Y "dist\JD Soft\*" "dist\JD Soft 배포용\"

    echo 바로가기 생성 중...
    powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('dist\JD Soft 배포용\JD Soft.lnk'); $Shortcut.TargetPath = '.\JD Soft.exe'; $Shortcut.Save()"

    echo 배포용 폴더 생성 완료!
)

:end
pause
