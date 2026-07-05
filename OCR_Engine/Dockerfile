FROM python:3.11-slim

# System deps for PaddleOCR + OpenCV
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgomp1 \
    libgcc-s1 \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download fastText model
RUN mkdir -p /models/fasttext && \
    wget -q https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin \
    -O /models/fasttext/lid.176.bin

COPY . .

EXPOSE 8000

# Single command — starts API + all workers
CMD ["python", "main.py"]
