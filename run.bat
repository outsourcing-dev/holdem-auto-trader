@echo off
echo 홀덤 웹 트레이더를 시작합니다...
cd /d "%~dp0\dist"
start HoldemWebTrader.exe
echo.
echo 프로그램이 시작되었습니다.
echo 브라우저에서 http://localhost:8000 으로 접속하세요.
pause