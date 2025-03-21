@echo off
chcp 65001 > nul
echo Holdem Auto Trader 빌드 스크립트 (암호화 Excel 적용)
echo ======================================================

REM 가상환경 활성화 (가상환경을 사용하는 경우)
REM call venv\Scripts\activate

REM 필요한 패키지 설치 여부 확인
echo 필요한 패키지 설치 여부 확인 중...
pip install -r requirements.txt
pip install pycryptodome

REM PyInstaller 설치 확인
pip install pyinstaller

REM Excel 파일 확인 및 암호화
echo Excel 파일 확인 중...
if not exist AUTO.xlsx (
    echo AUTO.xlsx 파일이 없습니다. 이 파일은 반드시 필요합니다.
    echo 빌드를 중단합니다.
    goto :end
)

REM Excel 파일 암호화 코드 수정
echo Excel 파일을 암호화합니다...
python -c "from utils.excel_encrypted_distribution import encrypt_excel_for_distribution; encrypt_excel_for_distribution('AUTO.xlsx')" || (
    echo Excel 파일 암호화에 실패했습니다.
    echo 빌드를 중단합니다.
    goto :end
)

echo Excel 파일 암호화 완료!

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

REM 수정된 spec 파일 사용하여 빌드
echo PyInstaller로 빌드 시작...
pyinstaller --clean holdem_auto_trader.spec

echo.
echo 빌드 완료!
echo 실행 파일 위치: dist\holdem_auto_trader\holdem_auto_trader.exe
echo.

REM 영문 폴더 이름을 사용하여 빌드 후 필요한 파일 복사
echo 필수 파일 복사 확인 중...
if exist dist\holdem_auto_trader (
    echo 필요한 파일들을 dist 폴더로 복사합니다...
    
    REM 설정 파일 복사
    copy /Y settings.json dist\holdem_auto_trader\
    copy /Y room_settings.json dist\holdem_auto_trader\
    
    REM 암호화된 Excel 파일만 복사 (원본 Excel은 복사하지 않음)
    copy /Y AUTO.encrypted dist\holdem_auto_trader\

    REM 아이콘 파일 복사
    if exist lover-icon.ico (
        mkdir dist\holdem_auto_trader\_internal 2>nul
        copy /Y lover-icon.ico dist\holdem_auto_trader\_internal\
        echo 아이콘 파일을 _internal 폴더로 복사했습니다.
    )        
    REM style.qss 수동 복사 제거 - PyInstaller에 의해 자동으로 포함됨
    REM (주석 처리로 변경 사항 표시)
    REM if not exist dist\holdem_auto_trader\ui mkdir dist\holdem_auto_trader\ui
    REM copy /Y ui\style.qss dist\holdem_auto_trader\ui\
    REM echo UI 스타일 파일 복사 완료!
    
    echo 파일 복사 완료!

    REM 상용 배포용 폴더 생성 (한글 이름)
    echo 배포용 폴더 생성 중...
    if not exist "dist\홀덤 자동 매매" mkdir "dist\홀덤 자동 매매"
    
    REM 영문 폴더의 내용을 한글 폴더로 복사
    xcopy /E /Y dist\holdem_auto_trader\* "dist\홀덤 자동 매매\"
    
    REM Windows 바로가기 생성
    echo 바로가기 생성 중...
    powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('dist\홀덤 자동 매매\홀덤 자동 매매.lnk'); $Shortcut.TargetPath = '.\holdem_auto_trader.exe'; $Shortcut.Save()"
    
    echo 배포용 폴더 생성 완료!
)

:end
REM 빌드 결과 확인을 위해 잠시 대기
pause