#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 监控状态
monitor_status = False
# 自动下单开关
auto_order_status = False
# 监控间隔（秒）
monitor_interval = 5
# 建单模式：True=统一建单，False=单独建单
batch_order_mode = False
# 测试模式：True=测试模式（只弹一次付款），False=正常模式
test_mode = False
# 刷新次数统计
daily_refresh_count = 0
hourly_refresh_count = 0
daily_refresh_date = None
hourly_refresh_hour = None

file_name_monitor_status = 'monitor_status.txt'
file_name_auto_order_status = 'auto_order_status.txt'
file_name_monitor_interval = 'monitor_interval.txt'
file_name_batch_order_mode = 'batch_order_mode.txt'
file_name_test_mode = 'test_mode.txt'
file_name_refresh_stats = 'refresh_stats.txt'

def load_monitor_status():
    global monitor_status
    try:
        with open(file_name_monitor_status, 'r') as f:
            monitor_status = f.readline().strip() == 'True'
            return monitor_status
    except FileNotFoundError:
        return False

def set_monitor_status(status: bool):
    global monitor_status
    monitor_status = status
    """保存监控状态到文件中"""
    with open(file_name_monitor_status, 'w') as f:
        f.write(f"{status}\n")

    # 实际控制监控线程
    try:
        from jobs import get_monitor_thread, start_monitor_thread, stop_monitor_thread

        if status:
            print("🚀 启动监控线程...")
            start_monitor_thread()
            print("✅ 监控线程已启动")
        else:
            print("🛑 停止监控线程...")
            stop_monitor_thread()
            print("✅ 监控线程已停止")
    except ImportError:
        # 如果监控线程管理函数不存在，只打印状态
        print(f"📊 监控状态已设置为: {'启用' if status else '关闭'}")
    except Exception as e:
        print(f"⚠️ 监控线程控制失败: {e}")

def get_global_monitor_status():
    return monitor_status

# --------------------------------------------
def load_auto_order_status():
    global auto_order_status
    try:
        with open(file_name_auto_order_status, 'r') as f:
            auto_order_status = f.readline().strip() == 'True'
            return auto_order_status
    except FileNotFoundError:
        return False

def set_auto_order_status(status: bool):
    global auto_order_status
    auto_order_status = status
    """保存自动下单状态到文件中"""
    with open(file_name_auto_order_status, 'w') as f:
        f.write(f"{status}\n")

    # 实质性动作：自动下单需要监控支持
    if status:
        # 开启自动下单时，必须同时开启监控
        if not get_global_monitor_status():
            print("🔗 自动下单需要监控支持，同时启动监控...")
            set_monitor_status(True)
        print("⚡ 自动下单已启用：发现库存将自动下单")
    else:
        print("📢 自动下单已关闭：切换为通知模式，只发送库存通知")

def get_global_auto_order_status():
    return auto_order_status

# --------------------------------------------
# 监控间隔管理
def load_monitor_interval():
    global monitor_interval
    try:
        with open(file_name_monitor_interval, 'r') as f:
            interval = int(f.readline().strip())
            # 限制间隔范围：1-300秒
            if 1 <= interval <= 300:
                monitor_interval = interval
            else:
                monitor_interval = 5  # 默认值
            return monitor_interval
    except (FileNotFoundError, ValueError):
        return 5  # 默认5秒

def set_monitor_interval(interval: int):
    global monitor_interval
    # 限制间隔范围：1-300秒
    if 1 <= interval <= 300:
        old_interval = monitor_interval
        monitor_interval = interval
        """保存监控间隔到文件中"""
        with open(file_name_monitor_interval, 'w') as f:
            f.write(f"{interval}\n")

        # 实质性动作：动态调整监控频率
        mode_text = ""
        if interval <= 5:
            mode_text = "🔥 高频抢购模式"
        elif interval <= 30:
            mode_text = "⚡ 正常监控模式"
        else:
            mode_text = "🛡️ 低频节能模式"

        print(f"⚡ 监控间隔已调整: {old_interval}秒 → {interval}秒 ({mode_text})")

        # 如果监控线程正在运行，间隔会自动调整（DynamicSecondsScheduleJobThread）
        try:
            from jobs import get_monitor_thread
            thread = get_monitor_thread()
            if thread and thread.is_alive():
                print("🔄 监控线程将在下次循环时应用新间隔")
        except:
            pass

        return True
    return False

def get_global_monitor_interval():
    return monitor_interval

# --------------------------------------------
# 建单模式管理
def load_batch_order_mode():
    global batch_order_mode
    try:
        with open(file_name_batch_order_mode, 'r') as f:
            mode = f.readline().strip().lower()
            batch_order_mode = mode == 'true'
            return batch_order_mode
    except FileNotFoundError:
        return False  # 默认单独建单

def set_batch_order_mode(mode: bool):
    global batch_order_mode
    batch_order_mode = mode
    """保存建单模式到文件中"""
    with open(file_name_batch_order_mode, 'w') as f:
        f.write(f"{mode}\n")

    # 实质性动作：清理购物车状态
    try:
        from service.product_checkout import clear_batch_cart, reset_batch_round

        if mode:
            print("🛒 切换为统一建单模式：")
            print("   - 发现库存 → 加入购物车")
            print("   - 等待所有关键词检测完成")
            print("   - 批量提交订单")
            # 重置批量状态
            reset_batch_round()
        else:
            print("⚡ 切换为单独建单模式：")
            print("   - 发现库存 → 立即下单")
            print("   - 不使用购物车")
            # 清空现有购物车
            clear_batch_cart()

    except ImportError:
        print(f"🛒 建单模式已设置为: {'统一建单' if mode else '单独建单'}")
    except Exception as e:
        print(f"⚠️ 建单模式切换时清理失败: {e}")

def get_global_batch_order_mode():
    return batch_order_mode

# --------------------------------------------
# 测试模式管理
def load_test_mode():
    global test_mode
    try:
        with open(file_name_test_mode, 'r') as f:
            mode = f.readline().strip().lower()
            test_mode = mode == 'true'
            return test_mode
    except FileNotFoundError:
        return False  # 默认非测试模式

def set_test_mode(mode: bool):
    global test_mode
    test_mode = mode
    """保存测试模式到文件中"""
    with open(file_name_test_mode, 'w') as f:
        f.write(f"{mode}\n")

    # 实质性动作：测试模式管理
    if mode:
        print("🧪 测试模式已启用：")
        print("   - 强制执行检测（忽略商品总数变化）")
        print("   - 只弹一次付款窗口")
        print("   - 测试完成后自动关闭")
    else:
        print("🧪 测试模式已关闭：恢复正常监控模式")
        # 清理测试状态
        try:
            from service.product_checkout import reset_batch_round
            reset_batch_round()
        except:
            pass

def get_global_test_mode():
    return test_mode

# --------------------------------------------
# 刷新次数管理（每小时和每天）
def load_refresh_stats():
    """加载刷新统计数据"""
    global daily_refresh_count, hourly_refresh_count, daily_refresh_date, hourly_refresh_hour
    from datetime import datetime
    import json

    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    current_hour = now.strftime('%Y-%m-%d-%H')

    try:
        with open(file_name_refresh_stats, 'r') as f:
            data = json.load(f)

            # 加载每日统计
            if data.get('daily_date') == today:
                daily_refresh_count = data.get('daily_count', 0)
                daily_refresh_date = today
            else:
                daily_refresh_count = 0
                daily_refresh_date = today

            # 加载每小时统计
            if data.get('hourly_hour') == current_hour:
                hourly_refresh_count = data.get('hourly_count', 0)
                hourly_refresh_hour = current_hour
            else:
                hourly_refresh_count = 0
                hourly_refresh_hour = current_hour

    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        # 文件不存在或格式错误，初始化
        daily_refresh_count = 0
        hourly_refresh_count = 0
        daily_refresh_date = today
        hourly_refresh_hour = current_hour

    save_refresh_stats()
    return daily_refresh_count, hourly_refresh_count

def save_refresh_stats():
    """保存刷新统计数据到文件"""
    global daily_refresh_count, hourly_refresh_count, daily_refresh_date, hourly_refresh_hour
    import json

    data = {
        'daily_date': daily_refresh_date,
        'daily_count': daily_refresh_count,
        'hourly_hour': hourly_refresh_hour,
        'hourly_count': hourly_refresh_count
    }

    with open(file_name_refresh_stats, 'w') as f:
        json.dump(data, f, indent=2)

def increment_refresh_count():
    """增加刷新次数（同时更新每小时和每天）"""
    global daily_refresh_count, hourly_refresh_count, daily_refresh_date, hourly_refresh_hour
    from datetime import datetime

    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    current_hour = now.strftime('%Y-%m-%d-%H')

    # 检查是否是新的一天
    if daily_refresh_date != today:
        daily_refresh_count = 0
        daily_refresh_date = today

    # 检查是否是新的小时
    if hourly_refresh_hour != current_hour:
        hourly_refresh_count = 0
        hourly_refresh_hour = current_hour

    # 增加计数
    daily_refresh_count += 1
    hourly_refresh_count += 1

    save_refresh_stats()

    print(f"📊 刷新统计 - 今日: {daily_refresh_count}次, 本小时: {hourly_refresh_count}次")
    return daily_refresh_count, hourly_refresh_count

def get_refresh_stats():
    """获取刷新统计数据"""
    global daily_refresh_count, hourly_refresh_count, daily_refresh_date, hourly_refresh_hour
    from datetime import datetime

    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    current_hour = now.strftime('%Y-%m-%d-%H')

    # 检查是否是新的一天
    if daily_refresh_date != today:
        daily_refresh_count = 0
        daily_refresh_date = today

    # 检查是否是新的小时
    if hourly_refresh_hour != current_hour:
        hourly_refresh_count = 0
        hourly_refresh_hour = current_hour

    save_refresh_stats()
    return {
        'daily_count': daily_refresh_count,
        'hourly_count': hourly_refresh_count,
        'daily_date': daily_refresh_date,
        'hourly_hour': hourly_refresh_hour
    }

def get_daily_refresh_count():
    """获取当天刷新次数（保持向后兼容）"""
    stats = get_refresh_stats()
    return stats['daily_count']

def get_hourly_refresh_count():
    """获取当前小时刷新次数"""
    stats = get_refresh_stats()
    return stats['hourly_count']

# 兼容旧接口
def load_refresh_status():
    return load_monitor_status()

def set_refresh_status(status: bool):
    set_monitor_status(status)

def load_intensify_refresh_status():
    return load_auto_order_status()

def set_intensify_refresh_status(status: bool):
    set_auto_order_status(status)
