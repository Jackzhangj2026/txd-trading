# Auto-restart wrapper for uvicorn — never dies
Write-Host "=== TXD Server — Auto-Restart Wrapper ===" -ForegroundColor Cyan
Write-Host "Will auto-restart if server exits. Press Ctrl+C twice quickly to stop."
Write-Host ""

$env:PYTHONIOENCODING = 'utf-8'

while ($true) {
    Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') Starting server..." -ForegroundColor Green
    $proc = Start-Process -FilePath "uvicorn" `
        -ArgumentList "backend.main:app","--host","127.0.0.1","--port","8000" `
        -NoNewWindow -Wait -PassThru

    $exitCode = $proc.ExitCode
    Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') Server exited (code: $exitCode). Restarting in 5 seconds..." -ForegroundColor Yellow
    Start-Sleep 5
}
