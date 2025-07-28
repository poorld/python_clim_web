#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import os
from .logger import get_logger

logger = get_logger()
CONFIG_FILE = 'config.json'

# 刷新次数统计
daily_refresh_count = 0
hourly_refresh_count = 0
daily_refresh_date = None
hourly_refresh_hour = None

# 确保 data 目录存在
os.makedirs('data', exist_ok=True)
file_name_refresh_stats = 'data/refresh_stats.txt'

def _load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def load_monitor_status():
    return _load_config().get('MONITOR_STATUS', False)

def set_monitor_status(status: bool):
    config = _load_config()
    config['MONITOR_STATUS'] = status
    _save_config(config)
    # 实际控制监控线程
    try:
        from ..jobs import get_monitor_thread, start_monitor_thread, stop_monitor_thread

        if status:
            logger.info("🚀 启动监控线程...")
            start_monitor_thread()
            logger.info("✅ 监控线程已启动")
        else:
            logger.info("🛑 停止监控线程...")
            stop_monitor_thread()
            logger.info("✅ 监控线程已停止")
    except ImportError:
        # 如果监控线程管理函数不存在，只打印状态
        logger.info(f"📊 监控状态已设置为: {'启用' if status else '关闭'}")
    except Exception as e:
        logger.error(f"⚠️ 监控线程控制失败: {e}")

def get_global_monitor_status():
    return load_monitor_status()

# --------------------------------------------
def load_auto_order_status():
    return _load_config().get('AUTO_ORDER_STATUS', False)

def set_auto_order_status(status: bool):
    config = _load_config()
    config['AUTO_ORDER_STATUS'] = status
    _save_config(config)
    # 实质性动作：自动下单需要监控支持
    if status:
        # 开启自动下单时，必须同时开启监控
        if not get_global_monitor_status():
            logger.info("🔗 自动下单需要监控支持，同时启动监控...")
            set_monitor_status(True)
        logger.info("⚡ 自动下单已启用：发现库存将自动下单")
    else:
        logger.info("📢 自动下单已关闭：切换为通知模式，只发送库存通知")

def get_global_auto_order_status():
    return load_auto_order_status()

# --------------------------------------------
# 监控间隔管理
def load_monitor_interval():
    return _load_config().get('MONITOR_INTERVAL', 15)

def set_monitor_interval(interval: int):
    # 限制间隔范围：1-300秒
    if 1 <= interval <= 300:
        config = _load_config()
        old_interval = config.get('MONITOR_INTERVAL', 15)
        config['MONITOR_INTERVAL'] = interval
        _save_config(config)

        # 实质性动作：动态调整监控频率
        mode_text = ""
        if interval <= 5:
            mode_text = "🔥 高频抢购模式"
        elif interval <= 30:
            mode_text = "⚡ 正常监控模式"
        else:
            mode_text = "🛡️ 低频节能模式"

        logger.info(f"⚡ 监控间隔已调整: {old_interval}秒 → {interval}秒 ({mode_text})")

        # 如果监控线程正在运行，间隔会自动调整（DynamicSecondsScheduleJobThread）
        try:
            from ..jobs import get_monitor_thread
            thread = get_monitor_thread()
            if thread and thread.is_alive():
                logger.info("🔄 监控线程将在下次循环时应用新间隔")
        except:
            pass

        return True
    return False

def get_global_monitor_interval():
    return load_monitor_interval()

# --------------------------------------------
# 建单模式管理
def load_batch_order_mode():
    return _load_config().get('BATCH_ORDER_MODE', False)

def set_batch_order_mode(mode: bool):
    config = _load_config()
    config['BATCH_ORDER_MODE'] = mode
    _save_config(config)
    # 实质性动作：清理购物车状态
    try:
        from ..service.product_checkout import clear_batch_cart, reset_batch_round

        if mode:
            logger.info("🛒 切换为统一建单模式：")
            logger.info("   - 发现库存 → 加入购物车")
            logger.info("   - 等待所有关键词检测完成")
            logger.info("   - 批量提交订单")
            # 重置批量状态
            reset_batch_round()
        else:
            logger.info("⚡ 切换为单独建单模式：")
            logger.info("   - 发现库存 → 购物车 → 立即下单")
            # 清空现有购物车
            clear_batch_cart()

    except ImportError:
        logger.info(f"🛒 建单模式已设置为: {'统一建单' if mode else '单独建单'}")
    except Exception as e:
        logger.error(f"⚠️ 建单模式切换时清理失败: {e}")

def get_global_batch_order_mode():
    return load_batch_order_mode()

# 分组配置管理
def load_group_enabled():
    config = _load_config()
    return config.get('GROUP_ENABLED', False)

def set_group_enabled(enabled: bool):
    config = _load_config()
    config['GROUP_ENABLED'] = enabled
    _save_config(config)
    logger.info(f"🔧 分组模式已设置为: {'启用' if enabled else '禁用'}")

def get_global_group_enabled():
    return load_group_enabled()

def load_group_size():
    config = _load_config()
    return config.get('GROUP_SIZE', 5)

def set_group_size(size: int):
    config = _load_config()
    config['GROUP_SIZE'] = max(1, min(20, size))  # 限制在1-20之间
    _save_config(config)
    logger.info(f"🔧 分组大小已设置为: {config['GROUP_SIZE']}个")

def get_global_group_size():
    return load_group_size()

# --------------------------------------------
# 测试模式管理
def load_test_mode():
    return _load_config().get('TEST_MODE', False)

def set_test_mode(mode: bool):
    config = _load_config()
    config['TEST_MODE'] = mode
    _save_config(config)
    # 实质性动作：测试模式管理
    if mode:
        logger.info("🧪 测试模式已启用：")
        logger.info("   - 强制执行检测（忽略商品总数变化）")
        logger.info("   - 只弹一次付款窗口")
        logger.info("   - 测试完成后自动关闭")
    else:
        logger.info("🧪 测试模式已关闭：恢复正常监控模式")
        # 清理测试状态
        try:
            from ..service.product_checkout import reset_batch_round
            reset_batch_round()
        except:
            pass

def get_global_test_mode():
    return load_test_mode()

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

    logger.info(f"📊 刷新统计 - 今日: {daily_refresh_count}次, 本小时: {hourly_refresh_count}次")
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
