FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# /data is where Railway will mount the persistent volume
RUN mkdir -p /data

CMD ["python", "main.py"]
