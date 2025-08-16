@echo off
title 홀덤 웹 트레이더

echo ============================================================
echo 홀덤 자동 트레이더 웹 서버
echo ============================================================
echo.

REM 포트 8000을 사용하는 프로세스 종료
echo 기존 서버를 확인 중...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo 기존 서버 종료 중 (PID: %%a)
    taskkill /PID %%a /F >nul 2>&1
    timeout /t 2 /nobreak >nul
)

echo 서버를 시작합니다...
cd /d "%~dp0backend"

REM 백그라운드에서 Python 서버 시작
start /B python main.py

REM 3초 대기
timeout /t 3 /nobreak >nul

REM 브라우저 열기
echo 브라우저를 엽니다...
start http://localhost:8000

echo.
echo ============================================================
echo 서버가 실행 중입니다.
echo 종료하려면 이 창을 닫거나 Ctrl+C를 누르세요.
echo ============================================================
echo.

REM 서버 프로세스 유지
python -c "import time; time.sleep(999999)"