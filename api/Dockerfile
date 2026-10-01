# 多阶段构建：先用 node 构建前端，再与 FastAPI 打包成一个镜像
# 构建上下文为项目根（stock-data/），供 docker-compose 调用

# ---- 阶段1：构建前端 ----
# 注意：web/public/folio 体积很大，构建机需足够磁盘与内存（npm run build）
FROM node:24-slim AS webbuild
WORKDIR /build
COPY web/package.json web/package-lock.json* web/.npmrc ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ---- 阶段2：运行 API ----
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai \
    WEB_DIST=/app/web_dist
COPY api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY api/ ./api/
COPY sql/ ./sql/
COPY --from=webbuild /build/dist ./web_dist
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
