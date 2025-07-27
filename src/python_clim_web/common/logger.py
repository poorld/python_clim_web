import logging
import sys
import os
from logging.handlers import TimedRotatingFileHandler

# 1. 创建一个日志记录器（logger）
logger = logging.getLogger("AppLogger")
logger.setLevel(logging.DEBUG)  # 设置这个logger的最低日志级别

# 2. 创建一个格式化器（formatter）
log_format = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 3. 创建一个处理器（handler），用于将日志输出到控制台
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)  # 控制台只显示INFO及以上级别的日志
console_handler.setFormatter(log_format)

# 4. 创建一个处理器，用于将日志写入文件（按天轮换）
# TimedRotatingFileHandler 会在指定的时间间隔创建新的日志文件
# when='midnight' 表示每天午夜轮换，backupCount=7 表示保留最近7天的日志

# 确保 logs 目录存在
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)

file_handler = TimedRotatingFileHandler(
    os.path.join(log_dir, 'app.log'), when='midnight', interval=1, backupCount=7, encoding='utf-8'
)
file_handler.setLevel(logging.DEBUG)  # 文件中记录所有DEBUG及以上级别的日志
file_handler.setFormatter(log_format)

# 5. 将处理器添加到日志记录器
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# 防止日志传播到根记录器（如果根记录器有自己的处理器）
logger.propagate = False

# 导出logger实例，以便其他模块使用
def get_logger():
    return logger

