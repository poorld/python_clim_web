# 步骤 1: 使用官方 Python 镜像作为构建环境
FROM python:3.11-slim AS builder

# 设置工作目录
WORKDIR /app

# 安装构建依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 步骤 2: 创建最终的生产镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 从构建环境中复制已安装的依赖
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# 复制应用代码
COPY . .

# 设置环境变量，告诉应用在生产模式下运行
ENV ENV=production

# 暴露 Gunicorn 将要监听的端口
EXPOSE 80

# 使用 Gunicorn 启动应用
# -w 4: 启动 4 个 worker 进程 (可以根据您的服务器配置调整)
# -b 0.0.0.0:5000: 监听所有网络接口的 5000 端口
# service.web:run_flask: 指向 service/web.py 文件中的 run_flask 函数
# ClawCloud 会自动设置 PORT 环境变量，我们在这里使用它
#CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:5000", "service.web:app"]
CMD gunicorn --workers 4 --threads 4 --worker-class gevent --bind "0.0.0.0:$PORT" service.web:app