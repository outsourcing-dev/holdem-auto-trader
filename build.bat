@echo off
echo Building Holdem Web Trader...

REM 기존 빌드 삭제
if exist dist\HoldemWebTrader.exe del dist\HoldemWebTrader.exe
if exist build rmdir /s /q build

REM PyInstaller 빌드
pyinstaller HoldemWebTrader.spec

echo.
echo Build complete! 
echo Executable: dist\HoldemWebTrader.exe
echo.
echo To run the application, double-click:
echo   dist\HoldemWebTrader.exe
echo.
echo Or use the batch file:
echo   HoldemWebTrader.bat
echo.
pause