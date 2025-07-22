# 步骤 1: 使用官方 Python 镜像作为构建环境
FROM python:3.11-slim AS builder

# 设置工作目录
WORKDIR /app

# 安装构建依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 步骤 2: 创建最终的生产镜像
FROM python:3.11-slim

# 设置时区（解决时间问题）
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

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
# --workers 4: 启动 4 个 worker 进程
# --threads 4: 每个 worker 启动 4 个线程
# --worker-class gevent: 使用 gevent 作为 worker 类
# --bind "0.0.0.0:$PORT": 监听所有网络接口的 PORT 环境变量指定的端口
# service.web:app: 指向 service/web.py 文件中的 app 对象
CMD gunicorn --workers 1 --threads 4 --worker-class gevent --bind "0.0.0.0:$PORT" service.web:app