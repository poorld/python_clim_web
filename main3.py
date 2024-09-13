#!/usr/bin/env python
# -*- coding: utf-8 -*-

from jobs import OnceJobThread, IntervalsMinutesScheduleJobThread, SecondsScheduleJobThread, HoursScheduleJobThread, IntervalsHoursScheduleJobThread, MinutesScheduleJobThread
from jobs.job_checkout import RefreshThread, IntensifyRefreshThread
from jobs.job_web import WebThread
from common.keywords import load_keywords
from common.status import load_refresh_status
from common.orders import load_orders_history

if __name__ == "__main__":

    load_keywords()
    load_refresh_status()
    load_orders_history()

    webThread = OnceJobThread(WebThread())
    webThread.start()

    productThread = MinutesScheduleJobThread(RefreshThread(), 30)
    productThread.start()

    productThread = SecondsScheduleJobThread(IntensifyRefreshThread(), 5)
    productThread.start()