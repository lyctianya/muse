FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai
COPY fetcher/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY fetcher/ ./fetcher/
# 默认启动 APScheduler 常驻进程
CMD ["python", "-m", "fetcher.scheduler"]
