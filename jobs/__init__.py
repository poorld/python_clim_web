#!/usr/bin/env python
# -*- coding: utf-8 -*-

import threading
from abc import ABC, abstractmethod
import schedule
import time

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
            print('schedule_count', schedule_count)
            num = 0
            for i in range(schedule_count):
                num += self._minutes
                if (num == 60):
                    num = 0
                run_time = str((num < 10 and ':0' or ':') + str(num))
                
                # schedule.every().hour.at(':00').do(self.do_job, self.job_thread.job_func)
                print('start job at time -> ' + run_time)
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
        print('Executing job immediately...')
        self._handler.handle()

        # 设置间隔时间任务
        print(f'Scheduling job with interval -> {self._minutes} minutes')
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
        print('SecondsScheduleJobThread')
        self._handler.startup()

        self._schedule.every(self._seconds).seconds.do(self._handler.handle)
        print('start job every {} seconds'.format(self._seconds))
        
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
        print('HoursScheduleJobThread')
        self._handler.startup()

        self._schedule.every().day.at(self._hours).do(self._handler.handle)
        print('start job at time -> ' + self._hours)
        
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
        print('schedule_count', schedule_count)
        num = 0
        for i in range(schedule_count):
            num += self._intervals
            if (num == 24):
                num = 0
                
            run_time = '{}:00'.format(
                num < 10 and '0' + str(num) or str(num)
            )
                
            
            # schedule.every().hour.at(':00').do(self.do_job, self.job_thread.job_func)
            print('start job at time -> ' + run_time)
            self._schedule.every().day.at(run_time).do(self._handler.handle)
            
        while not self._stopped():
            self._schedule.run_pending()
            time.sleep(1)