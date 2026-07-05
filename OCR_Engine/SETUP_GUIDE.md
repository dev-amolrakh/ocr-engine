# OCR Service — Local Setup Guide (Windows)

This guide provides a complete, step-by-step setup for running this OCR Engine locally on a Windows machine. It covers the required services, Python environment, model downloads, worker-specific prerequisites, and verification steps.

---

## 1. Prerequisites

| Software | Version  | Purpose                         |
| -------- | -------- | ------------------------------- |
| Python   | 3.11+    | Runtime                         |
| MongoDB  | 7.x      | Metadata and job storage        |
| Redis    | 7.x      | Background worker orchestration |
| Ollama   | Latest   | Local LLM inference for Qwen-VL |
| Git      | Any      | Version control                 |
| Postman  | Optional | API testing                     |

Recommended minimum hardware:

- 16 GB RAM minimum
- SSD storage preferred
- Internet access for installing dependencies and models

---

## 2. Install system dependencies

### 2.1 MongoDB

1. Download MongoDB Community Server.
2. Install it as a Windows service.
3. Verify it is running:

```powershell
mongosh --eval "db.runCommand({ping:1})"
```

Expected output:

```text
{ ok: 1 }
```

### 2.2 Redis

Redis is required for the asynchronous worker pipeline.

Recommended options on Windows:

- Memurai (recommended)
- Redis via WSL2
- Redis Windows build

Verify Redis:

```powershell
redis-cli ping
```

Expected output:

```text
PONG
```

### 2.3 Ollama

Ollama is used by the Qwen-VL OCR worker.

1. Install Ollama for Windows.
2. Start the service.
3. Pull the required models:

```powershell
ollama pull qwen2.5vl:7b
ollama pull qwen2.5:14b
```

Verify the models are available:

```powershell
curl http://localhost:11434/api/tags
```

If your machine has limited RAM, try smaller models:

```powershell
ollama pull qwen2.5vl:3b
ollama pull qwen2.5:7b
```

Then update the environment variables accordingly.

---

## 3. Clone the repository

```powershell
cd D:\
mkdir OCR Engine
cd OCR Engine
git clone <your-repo-url> ocr_service
cd ocr_service
```

---

## 4. Create a Python virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

If PowerShell blocks script execution, run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## 5. Install Python dependencies

Install the project requirements:

```powershell
pip install -r requirements.txt
```

### Common troubleshooting

#### PaddleOCR / PaddlePaddle

If install issues occur:

```powershell
pip install paddlepaddle==2.6.2
pip install paddleocr==2.8.1
```

#### PyTorch

For CPU-only setup:

```powershell
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

#### GPU setup

If you want GPU acceleration, ensure your machine has a compatible CUDA environment before installing GPU-enabled packages.

---

## 6. Download required model files

### 6.1 fastText language model

The language detection worker depends on fastText.

Create the directory:

```powershell
mkdir models\fasttext
```

Download the model:

```powershell
Invoke-WebRequest -Uri "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin" -OutFile "models\fasttext\lid.176.bin"
```

### 6.2 IndicTrans2 translation model

The translation worker can use IndicTrans2 when a compatible model is available.

Expected directory:

```text
./models/indictrans2
```

If the model is not present, the service will gracefully fall back to the original text without translation.

### 6.3 Storage folders

Create the storage structure used by the service:

```powershell
mkdir storage\incoming
mkdir storage\processed
mkdir storage\failed
mkdir storage\archive
```

---

## 7. Configure environment variables

Copy the example configuration:

```powershell
copy .env.example .env
```

Then update .env with local values such as:

```env
APP_NAME=ocr-service
DEBUG=true
LOG_LEVEL=INFO

MONGO_URI=mongodb://localhost:27017
MONGO_DB=ocr_db

REDIS_URL=redis://localhost:6379

OLLAMA_BASE_URL=http://localhost:11434
QWEN_VL_MODEL=qwen2.5vl:7b
EXTRACTION_MODEL=qwen2.5:14b

PADDLE_USE_GPU=false
PADDLE_CONFIDENCE_THRESHOLD=0.75
PADDLE_LANG=en

FASTTEXT_MODEL_PATH=./models/fasttext/lid.176.bin
INDICTRANS2_MODEL_PATH=./models/indictrans2
```

### Notes

- Use PADDLE_USE_GPU=false for CPU-only machines.
- If you use smaller Ollama models, update the model names accordingly.
- If IndicTrans2 is unavailable, translation will simply pass through the original text.

---

## 8. Start the infrastructure services

Make sure MongoDB, Redis, and Ollama are running before launching the app.

If you use Docker Compose:

```powershell
docker-compose up -d mongodb redis ollama prometheus grafana loki
```

Otherwise ensure these endpoints are reachable:

- MongoDB: localhost:27017
- Redis: localhost:6379
- Ollama: localhost:11434

---

## 9. Start the OCR service

```powershell
cd "D:\OCR Engine\ocr_service"
.\venv\Scripts\Activate.ps1
python main.py
```

Expected startup output:

```text
INFO:     all_workers_started count=7
INFO:     application_started app=ocr-service
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## 10. Verify the setup

Open the Swagger UI:

```text
http://localhost:8000/api/docs
```

Test the health endpoint:

```powershell
curl http://localhost:8000/api/v1/health
```

Expected response:

```json
{ "status": "ok" }
```

Detailed health check:

```powershell
curl http://localhost:8000/api/v1/health/detailed
```

---

## 11. Worker-specific setup notes

### OCR worker

This worker uses:

- PaddleOCR for printed text
- Qwen-VL through Ollama for handwritten or fallback OCR

Required setup:

- PaddleOCR installed
- Ollama running
- Qwen-VL model pulled locally

### Language detection worker

Required setup:

- fastText model downloaded at the configured path

### Translation worker

Required setup:

- IndicTrans2 model if full translation is desired
- If absent, the worker will skip translation and return the source text

### Extraction worker

This worker uses rule-based extraction for known document types and optional LLM-based extraction behavior through the configured models.

### Validation worker

No extra setup is required beyond the main app environment.

---

## 12. Troubleshooting

### PaddleOCR import issues

Run:

```powershell
pip install -r requirements.txt
```

### fastText model not found

Check that the file exists:

```powershell
Test-Path .\models\fasttext\lid.176.bin
```

### Ollama model not found

Verify with:

```powershell
curl http://localhost:11434/api/tags
```

### Redis connection issues

Check Redis:

```powershell
redis-cli ping
```

### MongoDB connection issues

Check MongoDB:

```powershell
mongosh --eval "db.runCommand({ping:1})"
```

---

## 13. Quick test flow

1. Start MongoDB and Redis
2. Start Ollama and pull required models
3. Activate the virtual environment
4. Install dependencies
5. Download the fastText model
6. Configure .env
7. Run the service
8. Upload a sample PDF or image via the API

---

## 14. API testing examples

### Health check

```http
GET http://localhost:8000/api/v1/health
```

### Detailed health check

```http
GET http://localhost:8000/api/v1/health/detailed
```

### Upload a file

```http
POST http://localhost:8000/api/v1/upload
Content-Type: multipart/form-data
```

Form field:

- file: your PDF/image file

### Check job status

```http
GET http://localhost:8000/api/v1/jobs/{job_id}
```

### Get final results

```http
GET http://localhost:8000/api/v1/results/{job_id}
```

---

## 15. Summary

To run this project locally, you need:

- Python environment
- MongoDB
- Redis
- Ollama
- PaddleOCR
- fastText model
- Optional IndicTrans2 translation model

Once these are configured, the full OCR pipeline can run end-to-end locally.

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

| #   | Method | URL                                                  | Description |
| --- | ------ | ---------------------------------------------------- | ----------- |
| 1   | GET    | `http://localhost:8000/api/v1/health`                | Liveness    |
| 2   | GET    | `http://localhost:8000/api/v1/health/detailed`       | Full health |
| 3   | POST   | `http://localhost:8000/api/v1/upload`                | Upload file |
| 4   | POST   | `http://localhost:8000/api/v1/upload/bulk`           | Bulk upload |
| 5   | GET    | `http://localhost:8000/api/v1/jobs/{{job_id}}`       | Job status  |
| 6   | POST   | `http://localhost:8000/api/v1/jobs/status`           | Bulk status |
| 7   | GET    | `http://localhost:8000/api/v1/results/{{job_id}}`    | Results     |
| 8   | GET    | `http://localhost:8000/api/v1/pages/{{job_id}}`      | All pages   |
| 9   | GET    | `http://localhost:8000/api/v1/pages/{{job_id}}/1`    | Single page |
| 10  | POST   | `http://localhost:8000/api/v1/jobs/{{job_id}}/retry` | Retry job   |
| 11  | DELETE | `http://localhost:8000/api/v1/jobs/{{job_id}}`       | Delete job  |

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
