#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Python Climate Web Application Entry Point

这是应用程序的主入口点，负责启动整个应用。
"""

import sys
import os

# 添加 src 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

if __name__ == "__main__":
    from src.python_clim_web.main import main
    main()
