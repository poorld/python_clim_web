#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试所有模块的导入是否正常工作
"""

import unittest
import sys
import os

# 添加 src 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestImports(unittest.TestCase):
    """测试模块导入"""

    def test_common_modules_import(self):
        """测试 common 模块导入"""
        try:
            from python_clim_web.common import logger, keywords, status, orders
            self.assertTrue(True, "Common modules imported successfully")
        except ImportError as e:
            self.fail(f"Failed to import common modules: {e}")

    def test_jobs_modules_import(self):
        """测试 jobs 模块导入"""
        try:
            from python_clim_web.jobs import job_web, job_checkout
            self.assertTrue(True, "Jobs modules imported successfully")
        except ImportError as e:
            self.fail(f"Failed to import jobs modules: {e}")

    def test_service_modules_import(self):
        """测试 service 模块导入"""
        try:
            from python_clim_web.service import web, product_checkout
            self.assertTrue(True, "Service modules imported successfully")
        except ImportError as e:
            self.fail(f"Failed to import service modules: {e}")

    def test_main_module_import(self):
        """测试主模块导入"""
        try:
            from python_clim_web import main
            self.assertTrue(hasattr(main, 'main'), "Main function exists")
        except ImportError as e:
            self.fail(f"Failed to import main module: {e}")

    def test_pushplus_import(self):
        """测试 pushplus 模块导入"""
        try:
            from python_clim_web import pushplus
            self.assertTrue(True, "Pushplus module imported successfully")
        except ImportError as e:
            self.fail(f"Failed to import pushplus module: {e}")

    def test_logger_functionality(self):
        """测试日志功能"""
        try:
            from python_clim_web.common.logger import get_logger
            logger = get_logger()
            self.assertIsNotNone(logger)
            # 测试日志方法存在
            self.assertTrue(hasattr(logger, 'info'))
            self.assertTrue(hasattr(logger, 'error'))
            self.assertTrue(hasattr(logger, 'warning'))
            self.assertTrue(hasattr(logger, 'debug'))
        except Exception as e:
            self.fail(f"Logger functionality test failed: {e}")


if __name__ == '__main__':
    unittest.main()
