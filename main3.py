#!/usr/bin/env python
# -*- coding: utf-8 -*-

from jobs import OnceJobThread
from jobs.job_web import WebThread
from common.keywords import load_keywords
from common.status import load_monitor_status, load_auto_order_status, load_monitor_interval, get_global_monitor_interval, load_batch_order_mode, load_test_mode, load_refresh_stats
from common.orders import load_orders_history

if __name__ == "__main__":

    load_keywords()
    load_monitor_status()
    load_auto_order_status()
    load_monitor_interval()  # 加载监控间隔配置
    load_batch_order_mode()  # 加载建单模式配置
    load_test_mode()  # 加载测试模式配置
    load_refresh_stats()  # 加载刷新统计配置
    load_orders_history()

    print(f"📊 初始监控间隔: {get_global_monitor_interval()}秒")

    # 启动Web服务
    webThread = OnceJobThread(WebThread())
    webThread.start()

    # 根据监控状态决定是否启动监控线程
    from common.status import get_global_monitor_status
    from jobs import start_monitor_thread

    if get_global_monitor_status():
        print("🚀 监控状态为启用，自动启动监控线程")
        start_monitor_thread()
    else:
        print("⏸️ 监控状态为关闭，不启动监控线程")

    print("🎛️ 监控间隔可在Web界面动态调整: http://localhost:5000")