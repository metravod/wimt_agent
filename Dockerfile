FROM python:3.12-slim
WORKDIR /bot
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
ENV PYTHONUNBUFFERED=1 DATA_DIR=/data
VOLUME /data
CMD ["python", "-m", "app"]
