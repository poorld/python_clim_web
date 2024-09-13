#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests

class PushPlus():
    def __init__(self) -> None:
        self._token = '251cb35f680d46d994ef95a4470438c3'
        self._url = 'http://www.pushplus.plus/send'
        self._topic = '20240909'
        # self._topic = '20240911'
        
    def sendMsg(self,title,content):
        url = '{url}?token={token}&title={title}&content={content}&template=html&topic={topic}' \
            .format(url=self._url,
                    token=self._token,
                    title=title,
                    content=content,
                    topic=self._topic)
        response = requests.get(url)
        print(response)
   
# push_plus = PushPlus()
# push_plus.sendMsg('测试')