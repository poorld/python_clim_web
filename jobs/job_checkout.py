#!/usr/bin/env python
# -*- coding: utf-8 -*-

from jobs import ThreadHandler, OnceJobThread


class RefreshThread(ThreadHandler):
    def __init__(self) -> None:
        super().__init__()
        self.first_run = True  # 增加一个标记，默认第一次运行

    def startup(self) -> None:
        # print(self.__class__, 'startup')
        pass

    def shutdown(self) -> None:
        # print(self.__class__, 'shutdown')
        pass

    def handle(self) -> None:
        if self.get_global_refresh_status() is False:
            return
        
        keywords = self.get_global_keywords()
        print(self.__class__, 'handle keywords' + str(keywords))

        for keyword in keywords:
            # thread = OnceJobThread(ProductRefreshThread(keyword))
            # thread.start()
            self.process_keyword(keyword, False)
        
    from common.keywords import get_global_keywords
    from common.status import get_global_refresh_status
    from service.product_checkout import process_keyword

class IntensifyRefreshThread(ThreadHandler):
    def __init__(self) -> None:
        super().__init__()

    def startup(self) -> None:
        # print(self.__class__, 'startup')
        pass

    def shutdown(self) -> None:
        # print(self.__class__, 'shutdown')
        pass

    def handle(self) -> None:
        if self.get_global_intensify_refresh_status() is False:
            return
        
        keywords = self.get_global_intensify_keywords()
        print(self.__class__, 'handle keywords' + str(keywords))

        for keyword in keywords:
            # thread = OnceJobThread(ProductRefreshThread(keyword))
            # thread.start()
            self.process_keyword(keyword, True)
        
    from common.keywords import get_global_keywords, get_global_intensify_keywords
    from common.status import get_global_intensify_refresh_status
    from service.product_checkout import process_keyword


class ProductRefreshThread(ThreadHandler):
    def __init__(self, keyword) -> None:
        super().__init__()
        self._keyword = keyword

    def startup(self) -> None:
        # print(self.__class__, 'startup')
        pass

    def shutdown(self) -> None:
        # print(self.__class__, 'shutdown')
        pass

    def handle(self) -> None:
        print(self.__class__, 'handle ' + self._keyword)
        self.process_keyword(self._keyword)
        
    from service.product_checkout import process_keyword