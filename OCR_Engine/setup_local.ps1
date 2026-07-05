# OCR Service — Local Setup Script for Windows
# Run this in PowerShell from the ocr_service directory

Write-Host "=" * 60
Write-Host "  OCR Service Local Setup" -ForegroundColor Cyan
Write-Host "=" * 60

# Step 1: Create virtual environment
Write-Host "`n[1/5] Creating Python virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path "venv")) {
    python -m venv venv
    Write-Host "  Virtual environment created." -ForegroundColor Green
} else {
    Write-Host "  Virtual environment already exists." -ForegroundColor Green
}

# Step 2: Activate and install dependencies
Write-Host "`n[2/5] Installing dependencies..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt

# Step 3: Create storage directories
Write-Host "`n[3/5] Creating storage directories..." -ForegroundColor Yellow
$dirs = @("storage\incoming", "storage\processed", "storage\failed", "storage\archive", "models\fasttext")
foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}
Write-Host "  Storage directories created." -ForegroundColor Green

# Step 4: Download fastText model if not present
Write-Host "`n[4/5] Checking fastText model..." -ForegroundColor Yellow
if (-not (Test-Path "models\fasttext\lid.176.bin")) {
    Write-Host "  Downloading fastText language model (126 MB)..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin" -OutFile "models\fasttext\lid.176.bin"
    Write-Host "  fastText model downloaded." -ForegroundColor Green
} else {
    Write-Host "  fastText model already exists." -ForegroundColor Green
}

# Step 5: Check services
Write-Host "`n[5/5] Checking required services..." -ForegroundColor Yellow

# Check MongoDB
try {
    $mongo = Test-NetConnection -ComputerName localhost -Port 27017 -WarningAction SilentlyContinue
    if ($mongo.TcpTestSucceeded) {
        Write-Host "  MongoDB: RUNNING (port 27017)" -ForegroundColor Green
    } else {
        Write-Host "  MongoDB: NOT RUNNING - Start MongoDB service" -ForegroundColor Red
    }
} catch {
    Write-Host "  MongoDB: CANNOT CHECK - Verify manually" -ForegroundColor Yellow
}

# Check Redis
try {
    $redis = Test-NetConnection -ComputerName localhost -Port 6379 -WarningAction SilentlyContinue
    if ($redis.TcpTestSucceeded) {
        Write-Host "  Redis: RUNNING (port 6379)" -ForegroundColor Green
    } else {
        Write-Host "  Redis: NOT RUNNING - Start Redis/Memurai service" -ForegroundColor Red
    }
} catch {
    Write-Host "  Redis: CANNOT CHECK - Verify manually" -ForegroundColor Yellow
}

# Check Ollama
try {
    $ollama = Test-NetConnection -ComputerName localhost -Port 11434 -WarningAction SilentlyContinue
    if ($ollama.TcpTestSucceeded) {
        Write-Host "  Ollama: RUNNING (port 11434)" -ForegroundColor Green
    } else {
        Write-Host "  Ollama: NOT RUNNING - Start Ollama" -ForegroundColor Red
    }
} catch {
    Write-Host "  Ollama: CANNOT CHECK - Verify manually" -ForegroundColor Yellow
}

Write-Host "`n" + "=" * 60
Write-Host "  Setup Complete!" -ForegroundColor Cyan
Write-Host "=" * 60
Write-Host "`nTo start the service:" -ForegroundColor White
Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor Gray
Write-Host "  python main.py" -ForegroundColor Gray
Write-Host "`nAPI Docs: http://localhost:8000/api/docs" -ForegroundColor Gray
Write-Host "Health:   http://localhost:8000/api/v1/health" -ForegroundColor Gray
