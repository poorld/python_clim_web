#!/usr/bin/env python
# -*- coding: utf-8 -*-

import threading
from abc import ABC, abstractmethod
import schedule
import time
from common.logger import get_logger

logger = get_logger()

"""
ThreadHandler
"""
class ThreadHandler(ABC):
    @abstractmethod
    def startup(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    def shutdown(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    def handle(self) -> None:
        raise NotImplementedError()

"""
后台线程
"""
class JobThread(threading.Thread):
    def __init__(self, handler: ThreadHandler):
        super().__init__()
        self._handler = handler
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()
    
    def _stopped(self) -> bool:
        return self._stop_event.is_set()

    def run(self) -> None:
        self._handler.startup()
        while not self._stopped():
            self._handler.handle()
        self._handler.shutdown()


"""
只运行一次线程
"""
class OnceJobThread(JobThread):
    def __init__(self, handler: ThreadHandler):    
        super().__init__(handler)

    def run(self) -> None:
        self._handler.startup()
        self._handler.handle()
        self._stopped()
        self._handler.shutdown()

"""
定时任务: 整分运行
eg: 
    minutes=15
    run time = [:15, :30, :45, :00]
"""
class IntervalsMinutesScheduleJobThread(JobThread):
    def __init__(self, handler: ThreadHandler, minutes: int):    
        super().__init__(handler)
        self._minutes = minutes
        self._schedule = schedule.Scheduler()

    def run(self) -> None:
        self._handler.startup()
        if self._minutes < 0:
            self._stopped()
            self._handler.shutdown()
            return
        elif self._minutes == 0:
            self._schedule.every().hour.at(":00").do(self._handler.handle)
        else:
            # 60分钟内可以执行多少次
            schedule_count = int(60 / self._minutes)
            logger.debug(f'schedule_count: {schedule_count}')
            num = 0
            for i in range(schedule_count):
                num += self._minutes
                if (num == 60):
                    num = 0
                run_time = str((num < 10 and ':0' or ':') + str(num))
                
                # schedule.every().hour.at(':00').do(self.do_job, self.job_thread.job_func)
                logger.info(f'start job at time -> {run_time}')
                self._schedule.every().hour.at(run_time).do(self._handler.handle)
            
        while not self._stopped():
            self._schedule.run_pending()
            time.sleep(1)


"""
定时任务: 立即执行一次，之后按间隔指定分钟数运行
eg: 
    minutes=15
    run time = [启动时立即执行，然后每隔15分钟执行一次]
"""
class MinutesScheduleJobThread(JobThread):
    def __init__(self, handler: ThreadHandler, minutes: int):    
        super().__init__(handler)
        self._minutes = minutes
        self._schedule = schedule.Scheduler()

    def run(self) -> None:
        self._handler.startup()

        if self._minutes <= 0:
            self._stopped()
            self._handler.shutdown()
            return

        # 启动时立即执行一次任务
        logger.info('Executing job immediately...')
        self._handler.handle()

        # 设置间隔时间任务
        logger.info(f'Scheduling job with interval -> {self._minutes} minutes')
        self._schedule.every(self._minutes).minutes.do(self._handler.handle)

        while not self._stopped():
            self._schedule.run_pending()
            time.sleep(1)




"""
定时任务: 秒
eg: 
    seconds=5
"""
class SecondsScheduleJobThread(JobThread):
    def __init__(self, handler: ThreadHandler, seconds: str):    
        super().__init__(handler)
        self._seconds = seconds
        self._schedule = schedule.Scheduler()

    def run(self) -> None:
        logger.info('SecondsScheduleJobThread')
        self._handler.startup()

        self._schedule.every(self._seconds).seconds.do(self._handler.handle)
        logger.info(f'start job every {self._seconds} seconds')
        
        while not self._stopped():
            self._schedule.run_pending()
            time.sleep(1)



"""
定时任务: 每天几点运行
eg: 
    hours=10:15
    run time = 10:15
"""
class HoursScheduleJobThread(JobThread):
    def __init__(self, handler: ThreadHandler, hours: str):    
        super().__init__(handler)
        self._hours = hours
        self._schedule = schedule.Scheduler()

    def run(self) -> None:
        logger.info('HoursScheduleJobThread')
        self._handler.startup()

        self._schedule.every().day.at(self._hours).do(self._handler.handle)
        logger.info(f'start job at time -> {self._hours}')
        
        while not self._stopped():
            self._schedule.run_pending()
            time.sleep(1)

"""
定时任务: 整点运行
eg: 
    intervals=15
    run time = [:15, :30, :45, :00]
"""
class IntervalsHoursScheduleJobThread(JobThread):
    def __init__(self, handler: ThreadHandler, intervals: int):    
        super().__init__(handler)
        self._intervals = intervals
        self._schedule = schedule.Scheduler()

    def run(self) -> None:
        self._handler.startup()
        if self._intervals < 0:
            self._stopped()
            self._handler.shutdown()
            return

        # 24h内可以执行多少次
        schedule_count = int(24 / self._intervals)
        logger.debug(f'schedule_count: {schedule_count}')
        num = 0
        for i in range(schedule_count):
            num += self._intervals
            if (num == 24):
                num = 0
                
            run_time = '{}:00'.format(
                num < 10 and '0' + str(num) or str(num)
            )
                
            
            # schedule.every().hour.at(':00').do(self.do_job, self.job_thread.job_func)
            logger.info(f'start job at time -> {run_time}')
            self._schedule.every().day.at(run_time).do(self._handler.handle)
            
        while not self._stopped():
            self._schedule.run_pending()
            time.sleep(1)

"""
动态间隔调度器: 支持运行时调整间隔
"""
class DynamicSecondsScheduleJobThread(JobThread):
    def __init__(self, handler: ThreadHandler, get_interval_func):
        super().__init__(handler)
        self._get_interval_func = get_interval_func  # 获取当前间隔的函数
        self._current_interval = self._get_interval_func()

    def run(self) -> None:
        logger.info(f"🚀 动态调度器启动，初始间隔: {self._current_interval}秒")
        self._handler.startup()

        while not self._stopped():
            # 检查监控状态和解释器状态
            try:
                from common.status import get_global_monitor_status
                if not get_global_monitor_status():
                    logger.info("🛑 监控已关闭，线程即将停止")
                    break
            except (ImportError, ModuleNotFoundError):
                # 如果无法导入，可能是解释器正在关闭
                logger.warning("🛑 无法导入监控状态模块，解释器可能正在关闭")
                break
            except Exception as e:
                # 其他异常不应该导致线程退出，只记录错误
                logger.warning(f"⚠️ 检查监控状态时出错: {e}，继续运行")
                # 不break，继续运行

            try:
                self._handler.handle()
            except RuntimeError as e:
                if 'interpreter shutdown' in str(e):
                    logger.info("🛑 解释器正在关闭，停止监控线程")
                    break
                else:
                    logger.error(f"❌ 处理任务时出错: {e}", exc_info=True)
                    # 继续运行，不退出线程
            except Exception as e:
                logger.error(f"❌ 监控任务执行异常: {e}", exc_info=True)
                # 继续运行，不退出线程

            # 获取最新的间隔设置
            try:
                new_interval = self._get_interval_func()
                if new_interval != self._current_interval:
                    logger.info(f"⚡ 监控间隔已调整: {self._current_interval}秒 → {new_interval}秒")
                    self._current_interval = new_interval
            except Exception as e:
                # 如果无法获取间隔，使用当前间隔，记录错误但不退出
                logger.warning(f"⚠️ 获取监控间隔失败: {e}，使用当前间隔 {self._current_interval}秒")

            # 使用当前间隔等待，每秒检查一次停止信号
            for _ in range(self._current_interval):
                if self._stopped():
                    logger.info("🛑 收到停止信号，线程即将停止")
                    break
                time.sleep(1)

        self._handler.shutdown()

    def get_current_interval(self) -> int:
        return self._current_interval

# 全局监控线程管理
_monitor_thread = None

def get_monitor_thread():
    """获取当前监控线程"""
    return _monitor_thread


def start_monitor_thread():
    """启动监控线程"""
    global _monitor_thread

    if _monitor_thread is not None and _monitor_thread.is_alive():
        logger.warning("⚠️ 监控线程已在运行中")
        return

    try:
        from jobs.job_checkout import RefreshThread
        from common.status import get_global_monitor_interval

        # 创建新的监控线程
        _monitor_thread = DynamicSecondsScheduleJobThread(RefreshThread(), get_global_monitor_interval)
        _monitor_thread.daemon = True  # 设置为守护线程
        _monitor_thread.start()

        logger.info("✅ 监控线程启动成功")
    except Exception as e:
        logger.error(f"❌ 监控线程启动失败: {e}", exc_info=True)

def stop_monitor_thread():
    """停止监控线程"""
    global _monitor_thread

    if _monitor_thread is None or not _monitor_thread.is_alive():
        logger.warning("⚠️ 监控线程未运行")
        return

    try:
        _monitor_thread.stop()  # 发送停止信号
        _monitor_thread.join(timeout=5)  # 等待线程结束，最多5秒

        if _monitor_thread.is_alive():
            logger.warning("⚠️ 监控线程未能在5秒内停止")
        else:
            logger.info("✅ 监控线程已停止")

        _monitor_thread = None
    except Exception as e:
        logger.error(f"❌ 停止监控线程失败: {e}", exc_info=True)
