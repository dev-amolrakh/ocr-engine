# OCR Service — Local Setup Guide (Windows, No Docker)

Complete step-by-step guide to run the OCR service on your Windows laptop for testing with Postman.

---

## Prerequisites

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.11+ | Runtime |
| MongoDB | 7.x | Document database |
| Redis | 7.x | Message queue (via Memurai or WSL) |
| Ollama | Latest | Local LLM inference |
| Git | Any | Version control |
| Postman | Any | API testing |

---

## Step 1: Install MongoDB

1. Download MongoDB Community Server from:
   https://www.mongodb.com/try/download/community

2. Choose "Windows x64" → MSI package

3. During installation:
   - Select "Complete" installation
   - Check "Install MongoDB as a Service" (auto-starts on boot)
   - Install MongoDB Compass (GUI tool — optional but helpful)

4. Verify installation:
   ```powershell
   mongosh --eval "db.runCommand({ping:1})"
   ```
   You should see: `{ ok: 1 }`

---

## Step 2: Install Redis

Redis doesn't have an official Windows build. Use one of these options:

### Option A: Memurai (Recommended — Native Windows Redis)

1. Download from: https://www.memurai.com/get-memurai
2. Install the free Developer Edition
3. It runs as a Windows Service automatically
4. Verify:
   ```powershell
   redis-cli ping
   ```
   Response: `PONG`

### Option B: Redis via WSL2 (if you have WSL installed)

```powershell
# In WSL terminal:
sudo apt update
sudo apt install redis-server
sudo service redis-server start
redis-cli ping
```

### Option C: Redis Windows Port (Unofficial)

Download from: https://github.com/tporadowski/redis/releases
- Download `Redis-x64-5.0.14.1.msi`
- Install and it runs as a Windows Service

---

## Step 3: Install Ollama

1. Download from: https://ollama.com/download/windows
2. Run the installer
3. After installation, Ollama runs in the system tray
4. Pull the required models (open PowerShell):

```powershell
# Vision model for handwriting OCR (4.7 GB)
ollama pull qwen2.5vl:7b

# Text extraction model (9 GB)
ollama pull qwen2.5:14b
```

5. Verify Ollama is running:
   ```powershell
   curl http://localhost:11434/api/tags
   ```
   You should see both models listed.

> **Note:** These models require ~16 GB RAM total. If your laptop has less RAM,
> you can use smaller models:
> ```powershell
> ollama pull qwen2.5vl:3b    # smaller vision model
> ollama pull qwen2.5:7b      # smaller extraction model
> ```
> Then update `.env` file: `QWEN_VL_MODEL=qwen2.5vl:3b` and `EXTRACTION_MODEL=qwen2.5:7b`

---

## Step 4: Set Up Python Environment

```powershell
# Navigate to the project
cd "D:\OCR Engine\ocr_service"

# Create virtual environment
python -m venv venv

# Activate it
.\venv\Scripts\Activate.ps1

# If you get execution policy error, run this first:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Upgrade pip
python -m pip install --upgrade pip
```

---

## Step 5: Install Python Dependencies

```powershell
# Install all dependencies (CPU mode)
pip install -r requirements.txt
```

### If you face issues with PaddlePaddle:

```powershell
# Try installing PaddlePaddle separately first
pip install paddlepaddle==2.6.1

# If that fails, try the latest version
pip install paddlepaddle

# Then install remaining deps
pip install -r requirements.txt
```

### If you face issues with torch:

```powershell
# Install CPU-only PyTorch (smaller download)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Then install remaining deps
pip install -r requirements.txt
```

---

## Step 6: Download fastText Language Model

```powershell
# Create models directory
mkdir -p models\fasttext

# Download the language identification model (126 MB)
Invoke-WebRequest -Uri "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin" -OutFile "models\fasttext\lid.176.bin"
```

Or manually download from the URL and place at: `D:\OCR Engine\ocr_service\models\fasttext\lid.176.bin`

---

## Step 7: Create Storage Directories

```powershell
mkdir storage\incoming
mkdir storage\processed
mkdir storage\failed
mkdir storage\archive
```

---

## Step 8: Verify .env Configuration

The `.env` file is already configured for local testing. Key settings:

```ini
PADDLE_USE_GPU=false          # CPU mode for testing
DEBUG=true                     # Enables auto-reload
MONGO_URI=mongodb://localhost:27017
REDIS_URL=redis://localhost:6379
OLLAMA_BASE_URL=http://localhost:11434
```

---

## Step 9: Start the Service

Make sure MongoDB, Redis, and Ollama are all running, then:

```powershell
cd "D:\OCR Engine\ocr_service"
.\venv\Scripts\Activate.ps1

python main.py
```

You should see output like:
```
INFO:     all_workers_started count=7
INFO:     application_started app=ocr-service
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## Step 10: Verify the Service is Running

Open browser: http://localhost:8000/api/docs

This opens the Swagger UI with all available endpoints.

---

## Testing with Postman

### Import These Requests:

---

### Test 1: Health Check (Basic)

```
GET http://localhost:8000/api/v1/health
```

**Expected Response (200):**
```json
{
    "status": "ok"
}
```

---

### Test 2: Detailed Health Check

```
GET http://localhost:8000/api/v1/health/detailed
```

**Expected Response (200):**
```json
{
    "status": "ok",
    "components": {
        "mongodb": {"status": "ok", "latency_ms": 2},
        "redis": {"status": "ok", "latency_ms": 1},
        "nfs": {"status": "ok", "writable": true},
        "ollama_qwen_vl": {"status": "ok", "model_loaded": true},
        "ollama_extraction": {"status": "ok", "model_loaded": true},
        "paddleocr": {"status": "ok"},
        "indictrans2": {"status": "unavailable"},
        "fasttext": {"status": "ok"}
    }
}
```

> Note: `indictrans2` will show "unavailable" unless you download the model separately. This is fine for basic testing — translation will just pass through the original text.

---

### Test 3: Upload a PDF

```
POST http://localhost:8000/api/v1/upload
```

**Postman Setup:**
1. Method: `POST`
2. URL: `http://localhost:8000/api/v1/upload`
3. Go to **Body** tab
4. Select **form-data**
5. Add key: `file` → Change type to **File** → Select a PDF file
6. (Optional) Add key: `metadata` → Type: Text → Value: `{"source": "test"}`
7. Click **Send**

**Expected Response (202):**
```json
{
    "job_id": "JOB-A3F9C2D1E4B7",
    "status": "queued",
    "total_pages": 3,
    "poll_url": "/api/v1/jobs/JOB-A3F9C2D1E4B7"
}
```

---

### Test 4: Upload an Image

```
POST http://localhost:8000/api/v1/upload
```

Same as above, but select a `.jpg`, `.png`, or `.tiff` image file.

---

### Test 5: Check Job Status

```
GET http://localhost:8000/api/v1/jobs/{job_id}
```

Replace `{job_id}` with the ID from the upload response.

**Expected Response (200):**
```json
{
    "job_id": "JOB-A3F9C2D1E4B7",
    "status": "ocr",
    "total_pages": 3,
    "processed_pages": 1,
    "failed_pages": 0,
    "progress_pct": 33.3,
    "doc_type": "unknown",
    "ocr_stats": {
        "paddle_pages": 1,
        "qwen_vl_pages": 0,
        "handwritten_pages": 0
    }
}
```

---

### Test 6: Get Final Results (after job completes)

```
GET http://localhost:8000/api/v1/results/{job_id}
```

**Expected Response (200):**
```json
{
    "job_id": "JOB-A3F9C2D1E4B7",
    "status": "completed",
    "doc_type": "invoice",
    "extracted_data": {
        "invoice_number": "INV-2024-001",
        "vendor_name": "ABC Corp",
        "total_amount": 15000.00
    },
    "confidence": 1.0,
    "ocr_summary": {
        "total_pages": 3,
        "languages_detected": ["en"],
        "pages_translated": 0,
        "paddle_pages": 3,
        "qwen_vl_pages": 0,
        "handwritten_pages": 0
    }
}
```

---

### Test 7: Get Single Page OCR

```
GET http://localhost:8000/api/v1/pages/{job_id}/1
```

**Expected Response (200):**
```json
{
    "job_id": "JOB-A3F9C2D1E4B7",
    "page": 1,
    "language": "en",
    "is_handwritten": false,
    "ocr_source": "paddle",
    "ocr_confidence": 0.92,
    "ocr_text": "Invoice No: INV-2024-001\nDate: 15-01-2024...",
    "translated_text": null,
    "status": "completed"
}
```

---

### Test 8: Get All Pages (Paginated)

```
GET http://localhost:8000/api/v1/pages/{job_id}?page=1&limit=10
```

---

### Test 9: Bulk Status Check

```
POST http://localhost:8000/api/v1/jobs/status
Content-Type: application/json

{
    "job_ids": ["JOB-A3F9C2D1E4B7", "JOB-B4E8F1A2C3D6"]
}
```

---

### Test 10: Retry a Failed Job

```
POST http://localhost:8000/api/v1/jobs/{job_id}/retry
```

---

### Test 11: Delete a Job

```
DELETE http://localhost:8000/api/v1/jobs/{job_id}
```

---

### Test 12: Bulk Upload

```
POST http://localhost:8000/api/v1/upload/bulk
```

**Postman Setup:**
1. Method: `POST`
2. Body → form-data
3. Add key: `files` → Type: **File** → Select multiple files
4. Send

---

### Test 13: Prometheus Metrics

```
GET http://localhost:8000/metrics
```

Returns raw Prometheus metrics (counters, histograms, gauges).

---

## Postman Collection (Quick Import)

Create a new Postman Collection called "OCR Service" and add these requests:

| # | Method | URL | Description |
|---|--------|-----|-------------|
| 1 | GET | `http://localhost:8000/api/v1/health` | Liveness |
| 2 | GET | `http://localhost:8000/api/v1/health/detailed` | Full health |
| 3 | POST | `http://localhost:8000/api/v1/upload` | Upload file |
| 4 | POST | `http://localhost:8000/api/v1/upload/bulk` | Bulk upload |
| 5 | GET | `http://localhost:8000/api/v1/jobs/{{job_id}}` | Job status |
| 6 | POST | `http://localhost:8000/api/v1/jobs/status` | Bulk status |
| 7 | GET | `http://localhost:8000/api/v1/results/{{job_id}}` | Results |
| 8 | GET | `http://localhost:8000/api/v1/pages/{{job_id}}` | All pages |
| 9 | GET | `http://localhost:8000/api/v1/pages/{{job_id}}/1` | Single page |
| 10 | POST | `http://localhost:8000/api/v1/jobs/{{job_id}}/retry` | Retry job |
| 11 | DELETE | `http://localhost:8000/api/v1/jobs/{{job_id}}` | Delete job |

> **Tip:** Set a Postman variable `{{job_id}}` and update it after each upload.

---

## Troubleshooting

### "Module not found" errors
```powershell
# Make sure you're in the ocr_service directory
cd "D:\OCR Engine\ocr_service"
# Make sure venv is activated
.\venv\Scripts\Activate.ps1
```

### MongoDB connection refused
```powershell
# Check if MongoDB service is running
Get-Service MongoDB
# Start it if stopped
Start-Service MongoDB
```

### Redis connection refused
```powershell
# If using Memurai
Get-Service Memurai
Start-Service Memurai

# If using WSL Redis
wsl sudo service redis-server start
```

### Ollama not responding
```powershell
# Check if Ollama is running (system tray)
# Or start manually:
ollama serve

# Verify models are downloaded:
ollama list
```

### PaddleOCR GPU errors
The `.env` is set to `PADDLE_USE_GPU=false`. If you still get CUDA errors:
```powershell
pip uninstall paddlepaddle-gpu
pip install paddlepaddle
```

### Port 8000 already in use
```powershell
# Find what's using port 8000
netstat -ano | findstr :8000
# Kill the process
taskkill /PID <pid> /F
```

### Slow first request
The first OCR request will be slow because:
- PaddleOCR models download on first use (~300 MB)
- Ollama loads models into RAM on first call

Subsequent requests will be fast.

---

## Processing Flow (What Happens When You Upload)

```
1. Upload file → Saved to ./storage/incoming/{year}/{month}/{job_id}/
2. RendererWorker → Converts PDF pages to PNG (300 DPI)
3. PreprocessorWorker → Grayscale, denoise, deskew, CLAHE, binarize
4. OCRWorker → PaddleOCR (fast) or Qwen-VL (if handwritten/low confidence)
5. LangDetectWorker → Detects language per page (fastText)
6. TranslationWorker → Translates non-English to English (IndicTrans2)
7. ExtractionWorker → Extracts structured fields (Qwen2.5 via Ollama)
8. ValidationWorker → Validates against Pydantic schemas → Job complete!
```

---

## Quick Start Checklist

- [ ] MongoDB installed and running on port 27017
- [ ] Redis (Memurai) installed and running on port 6379
- [ ] Ollama installed with `qwen2.5vl:7b` and `qwen2.5:14b` pulled
- [ ] Python 3.11+ with virtual environment activated
- [ ] `pip install -r requirements.txt` completed
- [ ] fastText model at `./models/fasttext/lid.176.bin`
- [ ] `./storage/` directories created
- [ ] `python main.py` starts without errors
- [ ] `GET /api/v1/health` returns `{"status": "ok"}`
- [ ] Upload a test PDF and check job status
