# ─── Build Stage ───
FROM python:3.11-slim AS builder

WORKDIR /app

# 仅拷贝依赖文件，利用 Docker 缓存
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# ─── Runtime Stage ───
FROM python:3.11-slim

WORKDIR /app

# 从 builder 阶段复制已安装的包
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# 拷贝项目代码
COPY . .

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
