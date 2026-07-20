# GPU inference image — needs NVIDIA runtime (~8 GB VRAM for the 2B model)
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3-pip libsndfile1 git && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY requirements.txt .
RUN pip3 install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cu124 \
 && pip3 install --no-cache-dir -r requirements.txt

COPY app ./app

ENV MODEL_ID=sumnim/VoxCPM2-Khmer \
    HF_HOME=/models \
    LAZY_LOAD=0

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s \
  CMD python3 -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
