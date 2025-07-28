#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
from .config import AppConfig
from .common.logger import get_logger

logger = get_logger()

IS_DEBUG = False

class PushPlus():
    def __init__(self) -> None:
        self._token = AppConfig.PUSHPLUS_TOKEN
        self._url = AppConfig.PUSHPLUS_URL
        self._topic = AppConfig.PUSHPLUS_TOPIC
        # self._topic = '20240911'
        
    def sendMsg(self,title,content):
        if IS_DEBUG:
            return
        url = '{url}?token={token}&title={title}&content={content}&template=html&topic={topic}' \
            .format(url=self._url,
                    token=self._token,
                    title=title,
                    content=content,
                    topic=self._topic)
        response = requests.get(url)
        logger.debug(response)
