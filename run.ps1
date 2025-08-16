Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   홀덤 자동 트레이더 웹 버전 실행" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 백엔드 서버 실행
Write-Host "[1/3] 백엔드 서버 시작..." -ForegroundColor Green
$backend = Start-Process -FilePath "python" -ArgumentList "main.py" -WorkingDirectory ".\backend" -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 3

# 프론트엔드 서버 실행
Write-Host "[2/3] 프론트엔드 서버 시작..." -ForegroundColor Green
$frontend = Start-Process -FilePath "npm" -ArgumentList "start" -WorkingDirectory ".\frontend" -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 5

# 브라우저 열기
Write-Host "[3/3] 브라우저 실행..." -ForegroundColor Green
Start-Process "http://localhost:3000"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   서버가 실행되었습니다!" -ForegroundColor Yellow
Write-Host "   브라우저에서 자동으로 열립니다." -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "종료하려면 Ctrl+C를 누르거나 창을 닫으세요." -ForegroundColor Gray

# 프로세스 모니터링
try {
    while ($true) {
        Start-Sleep -Seconds 1
    }
}
finally {
    # 종료 시 프로세스 정리
    Write-Host "`n서버 종료 중..." -ForegroundColor Red
    Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue
    Write-Host "종료 완료" -ForegroundColor Green
}