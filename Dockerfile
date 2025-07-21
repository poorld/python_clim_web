# 使用官方的 Python 基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt requirements.txt

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制所有源代码到工作目录
COPY . .

# 容器暴露的端口（文档作用，实际由`app.run`决定）
EXPOSE 5000

# 设置启动命令
CMD ["python", "main3.py"]
