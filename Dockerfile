FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV DATA_DIR=/data PORT=8000
VOLUME /data
EXPOSE 8000
# gthread workers so long streaming replies don't block other requests.
CMD gunicorn -w 1 -k gthread --threads 16 --timeout 0 -b 0.0.0.0:$PORT app:app
