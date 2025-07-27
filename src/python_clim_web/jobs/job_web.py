#!/usr/bin/env python
# -*- coding: utf-8 -*-

from . import ThreadHandler
from ..service.web import run_flask  # 移到类外部导入


class WebThread(ThreadHandler):
    def __init__(self) -> None:
        super().__init__()
        
    def startup(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def handle(self) -> None:
        run_flask()  # 直接调用函数
