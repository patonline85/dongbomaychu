FROM python:3.10-slim

# Cài đặt rsync, ssh và docker (để bot có thể gọi lệnh docker stop/start)
RUN apt-get update && apt-get install -y rsync openssh-client docker.io && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

CMD ["python", "bot.py"]