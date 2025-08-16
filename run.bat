@echo off
echo ========================================
echo   홀덤 자동 트레이더 웹 버전 실행
echo ========================================
echo.

:: 백엔드 서버 실행
echo [1/3] 백엔드 서버 시작...
cd backend
start /B python main.py
timeout /t 3 /nobreak > nul

:: 프론트엔드 서버 실행
echo [2/3] 프론트엔드 서버 시작...
cd ..\frontend
start /B npm start
echo.

:: 브라우저 열기 대기
echo [3/3] 브라우저 실행 대기 중...
timeout /t 5 /nobreak > nul

:: 브라우저 자동 열기
echo.
echo ========================================
echo   서버가 실행되었습니다!
echo   브라우저에서 http://localhost:3000 접속
echo ========================================
echo.
echo 종료하려면 이 창을 닫으세요.
echo.

:: 서버 유지
pause > nul