# Python 商品监控与自动下单系统

一个用于监控商品库存并自动下单的Web应用程序，支持关键词监控、智能下单和订单管理。

## 项目特性

- 🌐 **Web管理界面**: 基于Flask的用户友好控制面板
- 🔍 **智能监控**: 支持关键词商品库存实时监控
- 🛒 **自动下单**: 发现库存时自动执行购买流程
- 📦 **订单管理**: 完整的订单跟踪和状态管理
- 📱 **消息推送**: 库存变化和订单状态实时通知
- ⚡ **批量处理**: 支持多商品并发监控和批量下单
- 🔄 **后台任务**: 智能任务调度和处理
- 📝 **日志管理**: 完整的日志记录和轮换机制
- 🐳 **Docker支持**: 容器化部署
- 🧪 **测试框架**: 完整的单元测试支持

## 项目结构

```
python_clim_web/
├── README.md                    # 项目说明文档
├── main.py                      # 应用入口点
├── requirements.txt             # Python依赖包
├── Dockerfile                   # Docker构建文件
├── ClawCloud_docker.mk         # Docker构建脚本
├── .gitignore                  # Git忽略文件配置
├── config/                     # 配置文件目录
│   ├── config.json
│   └── requirements.txt
├── data/                       # 应用数据文件目录
│   ├── processed_keywords.txt
│   ├── refresh_stats.txt
│   ├── orders.txt
│   └── ...
├── runtime/                    # 运行时状态文件目录
│   ├── status.txt
│   ├── intensify_status.txt
│   └── ...
├── logs/                       # 日志文件目录
│   └── .gitkeep
├── src/                        # 源代码目录
│   └── python_clim_web/        # 主应用包
│       ├── __init__.py
│       ├── main.py             # 应用入口
│       ├── pushplus.py         # 推送服务
│       ├── common/             # 通用工具模块
│       │   ├── __init__.py
│       │   ├── control.py
│       │   ├── keywords.py
│       │   ├── logger.py
│       │   ├── orders.py
│       │   └── status.py
│       ├── jobs/               # 后台任务模块
│       │   ├── __init__.py
│       │   ├── job_checkout.py
│       │   └── job_web.py
│       ├── service/            # 服务层模块
│       │   ├── __init__.py
│       │   ├── product_checkout.py
│       │   └── web.py
│       └── templates/          # Web模板
│           ├── home.html
│           └── static/
└── tests/                      # 测试目录
    ├── __init__.py
    └── test_example.py
```

## 环境要求

- Python 3.8+
- Flask 2.3.3
- 其他依赖见 `requirements.txt`

## 安装指南

### 1. 克隆项目

```bash
git clone <repository-url>
cd python_clim_web
```

### 2. 创建虚拟环境

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置文件

确保 `config/config.json` 文件存在并配置正确。

## 运行指南

### 开发环境运行

```bash
# 进入源代码目录
cd src

# 运行主程序
python -m python_clim_web.main
```

### Docker运行

```bash
# 构建镜像
docker build -t python_clim_web .

# 运行容器
docker run -p 5000:5000 python_clim_web
```

### 使用Docker Makefile

```bash
make -f ClawCloud_docker.mk build
make -f ClawCloud_docker.mk run
```

## 访问应用

应用启动后，可通过以下地址访问：

- Web界面: http://localhost:5000
- 监控状态可在Web界面动态调整

## 测试

运行单元测试：

```bash
# 在项目根目录下运行
python -m pytest tests/

# 或者运行特定测试文件
python -m unittest tests.test_example
```

## 日志

应用日志存储在 `logs/` 目录下：
- `logs/app.log`: 当前日志文件
- `logs/app.log.YYYY-MM-DD`: 历史日志文件（按天轮换，保留7天）

## 开发指南

### 添加新功能

1. 在相应的模块目录下添加新文件
2. 更新 `__init__.py` 文件中的导入
3. 添加相应的测试用例
4. 更新文档

### 代码规范

- 遵循PEP 8代码风格
- 添加适当的注释和文档字符串
- 编写单元测试

## 贡献

欢迎提交Issue和Pull Request来改进项目。

## 许可证

[添加许可证信息]
