# 홀덤 웹 트레이더 PowerShell 런처

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "홀덤 자동 트레이더 웹 서버" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 포트 8000을 사용하는 프로세스 확인 및 종료
Write-Host "기존 서버를 확인 중..." -ForegroundColor Gray
$connections = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($connections) {
    foreach ($conn in $connections) {
        $pid = $conn.OwningProcess
        Write-Host "기존 서버 종료 중 (PID: $pid)" -ForegroundColor Yellow
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
}

# 서버 시작
Write-Host "서버를 시작합니다..." -ForegroundColor Green
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendPath = Join-Path $scriptPath "backend"
Set-Location $backendPath

# 백그라운드에서 Python 서버 시작
$pythonProcess = Start-Process python -ArgumentList "main.py" -PassThru -WindowStyle Hidden

# 서버 시작 대기
Write-Host "서버 시작 대기 중..." -ForegroundColor Gray
Start-Sleep -Seconds 3

# 브라우저 열기
Write-Host "브라우저를 엽니다..." -ForegroundColor Green
Start-Process "http://localhost:8000"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "서버가 실행 중입니다." -ForegroundColor Green
Write-Host "종료하려면 Enter를 누르세요." -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan

# 사용자 입력 대기
Read-Host

# 서버 종료
Write-Host "서버를 종료합니다..." -ForegroundColor Red
if ($pythonProcess -and !$pythonProcess.HasExited) {
    Stop-Process -Id $pythonProcess.Id -Force
}

# 포트 8000을 사용하는 모든 프로세스 종료
$connections = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($connections) {
    foreach ($conn in $connections) {
        Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "프로그램이 종료되었습니다." -ForegroundColor Gray