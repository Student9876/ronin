FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Force install the lightweight CPU-only version of PyTorch first
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install the rest
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir fastapi uvicorn

RUN python -c "from sentence_transformers import SentenceTransformer; Model = SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .

# Expose the API port
EXPOSE 8000

ENV PYTHONPATH=/app

# Boot FastAPI via Uvicorn
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]