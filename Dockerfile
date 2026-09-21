FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y ffmpeg git && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir -U yt-dlp
COPY main.py .
CMD ["python", "main.py"]
