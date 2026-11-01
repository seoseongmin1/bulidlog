# 시연용 실행: 필요한 준비를 확인하고 서버를 켠다. 사용법: .\start.cmd  (포트를 바꾸려면 .\start.cmd -Port 8001)
param([int]$Port = 8000)

$root = $PSScriptRoot
$py = Join-Path $root "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "백엔드 파이썬 환경이 없습니다. README.md의 '처음 한 번' 단계를 먼저 하세요."
    exit 1
}
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    Write-Host "포트 $Port 를 이미 다른 프로그램이 쓰고 있습니다. -Port 로 다른 번호를 지정하세요."
    exit 1
}

if (-not (Test-Path (Join-Path $root "frontend\dist\index.html"))) {
    Write-Host "화면을 처음 한 번 빌드합니다..."
    Push-Location (Join-Path $root "frontend")
    try {
        npm install
        if ($LASTEXITCODE) { Write-Host "npm install에 실패했습니다."; exit 1 }
        npm run build
        if ($LASTEXITCODE) { Write-Host "화면 빌드에 실패했습니다."; exit 1 }
    } finally {
        Pop-Location
    }
}

Push-Location (Join-Path $root "backend")
try {
    # 데이터베이스에 전력 데이터가 없을 때만 원본 CSV에서 넣는다.
    & $py -m app.loader --if-missing
    if ($LASTEXITCODE) { exit $LASTEXITCODE }

    Write-Host "http://localhost:$Port 에서 열립니다. 끝내려면 Ctrl+C 를 누르세요."
    & $py -m uvicorn app.main:app --port $Port
} finally {
    Pop-Location
}
