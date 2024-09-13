#!/usr/bin/env python
# -*- coding: utf-8 -*-

from jobs import ThreadHandler


class WebThread(ThreadHandler):
    def __init__(self) -> None:
        super().__init__()
        
    def startup(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def handle(self) -> None:
        self.run_flask()
        
    from service.web import run_flask