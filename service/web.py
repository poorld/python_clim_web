# -*- coding:utf-8 -*-
#!/usr/bin/python

import os
import json
import time
import sys
import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, Response
from common.keywords import load_keywords, save_keyword, remove_keyword
from common.status import load_monitor_status, set_monitor_status
from common.status import load_auto_order_status, set_auto_order_status
from common.status import load_monitor_interval, set_monitor_interval, get_global_monitor_interval
from common.status import load_batch_order_mode, set_batch_order_mode, get_global_batch_order_mode
from common.status import load_test_mode, set_test_mode, get_global_test_mode
from common.status import get_refresh_stats
from common.orders import save_orders_history, get_global_orders_history, get_orders, set_orders
from jobs import OnceJobThread
from jobs.job_checkout import RefreshThread
import threading
import queue

# 获取项目根目录并设置模板路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
template_dir = os.path.join(project_root, 'templates')
static_dir = os.path.join(template_dir, 'static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

# 订单推送队列
order_queue = queue.Queue()
# 日志推送队列
log_queue = queue.Queue(maxsize=1000)  # 限制队列大小防止内存溢出
clients = []  # 存储SSE客户端连接

# 日志捕获类
class LogCapture:
    def __init__(self, original_stdout):
        self.original_stdout = original_stdout

    def write(self, message):
        # 写入原始stdout（保持控制台输出）
        self.original_stdout.write(message)
        self.original_stdout.flush()

        # 推送到Web界面（只推送非空消息）
        if message.strip():
            self.push_log_to_web(message.strip())

    def flush(self):
        self.original_stdout.flush()

    def push_log_to_web(self, message):
        """推送日志到Web界面"""
        try:
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            log_data = {
                "timestamp": timestamp,
                "message": message,
                "level": self.detect_log_level(message)
            }
            log_queue.put(log_data, block=False)
        except queue.Full:
            # 队列满时，移除最老的日志
            try:
                log_queue.get_nowait()
                log_queue.put(log_data, block=False)
            except queue.Empty:
                pass
        except Exception as e:
            # 避免日志系统本身出错影响主程序
            pass

    def detect_log_level(self, message):
        """检测日志级别"""
        message_lower = message.lower()
        if any(word in message_lower for word in ['error', '错误', 'failed', '失败']):
            return 'error'
        elif any(word in message_lower for word in ['warning', '警告', 'warn']):
            return 'warning'
        elif any(word in message_lower for word in ['success', '成功', 'complete', '完成']):
            return 'success'
        elif any(word in message_lower for word in ['info', '信息', 'start', '开始']):
            return 'info'
        else:
            return 'default'

# 初始化日志捕获
original_stdout = sys.stdout
log_capture = LogCapture(original_stdout)
sys.stdout = log_capture

# index = 0

'''
----------------------------------------web--------------------------------
'''
# 获取所有关键词
@app.route('/keywords', methods=['GET'])
def get_keywords():
    keywords = load_keywords()
    return jsonify({'keywords': keywords})


# 添加关键词
@app.route('/add_keyword', methods=['POST'])
def add_keyword():
    keywords = load_keywords()
    new_keyword = request.form.get('keyword', '').strip()
    print('new_keyword', new_keyword)
    print('keywords', keywords)
    if new_keyword and new_keyword not in keywords:
        save_keyword(new_keyword)  # 保存新添加的关键词
        return redirect(url_for('home'))  # 重定向到主页
    else:
        return redirect(url_for('home', error='Invalid or duplicate keyword'))

# 删除关键字
@app.route('/delete_keyword', methods=['POST'])
def delete_keyword():
    keyword_to_delete = request.form.get('keyword')
    if not keyword_to_delete:
        return jsonify({"status": "error", "message": "Keyword is required"}), 400

    keywords = load_keywords()
    if keyword_to_delete not in keywords:
        return jsonify({"status": "error", "message": "Keyword not found"}), 404

    remove_keyword(keyword_to_delete)

    return redirect(url_for('home'))  # 重定向到主页

# 启用监控
@app.route('/enable_monitor', methods=['POST'])
def enable_monitor():
    set_monitor_status(True)

    thread = OnceJobThread(RefreshThread())
    thread.start()
    return redirect(url_for('home'))  # 重定向到主页

@app.route('/disable_monitor', methods=['POST'])
def disable_monitor():
    set_monitor_status(False)
    return redirect(url_for('home'))  # 重定向到主页

# 启用自动下单
@app.route('/enable_auto_order', methods=['POST'])
def enable_auto_order():
    set_auto_order_status(True)
    return redirect(url_for('home'))  # 重定向到主页

@app.route('/disable_auto_order', methods=['POST'])
def disable_auto_order():
    set_auto_order_status(False)
    return redirect(url_for('home'))  # 重定向到主页

# 设置监控间隔
@app.route('/set_interval', methods=['POST'])
def set_interval():
    try:
        interval = int(request.form.get('interval', 5))
        if set_monitor_interval(interval):
            mode_text = ""
            if interval <= 5:
                mode_text = "🔥 高频抢购模式"
            elif interval <= 30:
                mode_text = "⚡ 正常监控模式"
            else:
                mode_text = "🛡️ 低频节能模式"

            print(f"⚡ 监控间隔已更新为: {interval}秒 ({mode_text})")
            return redirect(url_for('home'))
        else:
            return redirect(url_for('home', error='间隔必须在1-300秒之间'))
    except ValueError:
        return redirect(url_for('home', error='无效的间隔值'))

# 设置建单模式
@app.route('/set_batch_mode', methods=['POST'])
def set_batch_mode():
    mode = request.form.get('batch_mode') == 'true'
    set_batch_order_mode(mode)
    mode_text = "统一建单" if mode else "单独建单"
    print(f"🛒 建单模式已切换为: {mode_text}")
    return redirect(url_for('home'))

# 测试下单（只弹一次付款）- 异步版本
@app.route('/test_order', methods=['POST'])
def test_order():
    try:
        # 临时启用测试模式
        set_test_mode(True)
        print("🧪 测试模式已启用：只弹一次付款窗口")

        # 强制执行测试检测（跳过商品总数检查）
        from common.keywords import get_global_keywords

        keywords = get_global_keywords()
        if not keywords:
            print("❌ 没有设置关键词，无法执行测试")
            set_test_mode(False)
            return jsonify({'success': False, 'message': '没有设置关键词，无法执行测试'})

        print(f"🧪 测试模式：开始检测 {len(keywords)} 个关键词")

        # 在后台线程中执行测试
        import threading
        def run_test():
            try:
                from jobs.job_checkout import TestModeStrategy
                strategy = TestModeStrategy()
                strategy.execute(keywords)

                # 检测完成后关闭测试模式
                set_test_mode(False)
                print("🧪 测试模式已关闭")
            except Exception as e:
                print(f"❌ 测试执行失败: {e}")
                import traceback
                traceback.print_exc()
                set_test_mode(False)

        # 启动后台线程
        test_thread = threading.Thread(target=run_test)
        test_thread.daemon = True
        test_thread.start()

        return jsonify({'success': True, 'message': f'测试模式已启动，正在检测 {len(keywords)} 个关键词...'})

    except Exception as e:
        print(f"❌ 测试下单失败: {e}")
        import traceback
        traceback.print_exc()
        set_test_mode(False)  # 确保测试模式被关闭
        return jsonify({'success': False, 'message': f'测试下单失败: {str(e)}'})



# 获取所有订单
@app.route('/orders', methods=['GET'])
def orders():
    # global index
    # index = index + 1
    # if index == 2:
    #     set_orders(['FX2024423005', 'FX2024297042'])
    orders = get_orders()
    print('orders', orders)
    orders_history = get_global_orders_history()
    new_orders = []
    for order in orders:
        if order not in orders_history:
            new_orders.append(order)
            orders_history.append(order)
            save_orders_history(order)
    print('new_orders', new_orders)

    # 如果有新订单，推送到SSE客户端
    for order in new_orders:
        push_order_to_clients(order)

    return jsonify({'orders': new_orders})

# SSE订单推送端点
@app.route('/stream')
def stream():
    def event_stream():
        # 发送连接确认
        yield "data: {\"type\": \"connected\"}\n\n"

        while True:
            try:
                # 减少超时时间，提高响应速度
                order = order_queue.get(timeout=1)
                # 发送订单数据
                data = json.dumps({
                    "type": "new_order",
                    "order": order,
                    "timestamp": time.time()
                })
                print(f"📤 SSE发送订单: {order}")
                yield f"data: {data}\n\n"
                order_queue.task_done()
            except queue.Empty:
                # 发送心跳包保持连接
                yield "data: {\"type\": \"heartbeat\"}\n\n"
            except Exception as e:
                print(f"❌ SSE错误: {e}")
                break

    return Response(event_stream(), mimetype="text/event-stream", headers={
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Access-Control-Allow-Origin': '*'
    })

# 日志SSE推送端点
@app.route('/logs')
def logs_stream():
    def log_event_stream():
        try:
            # 发送连接确认
            yield "data: {\"type\": \"connected\"}\n\n"
            print("📡 新的日志SSE客户端已连接")

            while True:
                try:
                    # 等待新日志，超时时间30秒
                    log_data = log_queue.get(timeout=30)
                    # 发送日志数据
                    data = json.dumps({
                        "type": "log",
                        "timestamp": log_data["timestamp"],
                        "message": log_data["message"],
                        "level": log_data["level"]
                    })
                    yield f"data: {data}\n\n"
                    log_queue.task_done()
                except queue.Empty:
                    # 发送心跳包保持连接
                    yield "data: {\"type\": \"heartbeat\"}\n\n"
                except Exception as e:
                    print(f"🔴 日志SSE内部错误: {e}")
                    break
        except Exception as e:
            print(f"🔴 日志SSE连接错误: {e}")
            yield f"data: {{\"type\": \"error\", \"message\": \"连接错误: {str(e)}\"}}\n\n"

    response = Response(log_event_stream(), mimetype="text/event-stream")
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

# 日志系统状态检查端点
@app.route('/log-status')
def log_status():
    return jsonify({
        "log_capture_active": sys.stdout == log_capture,
        "log_queue_size": log_queue.qsize(),
        "log_queue_maxsize": log_queue.maxsize,
        "status": "ok"
    })

# 推送新订单到所有客户端
def push_order_to_clients(order):
    """将新订单推送到订单队列"""
    try:
        order_queue.put(order, block=False)
        print(f"📤 订单 {order} 已推送到队列，队列大小: {order_queue.qsize()}")
    except queue.Full:
        print("❌ 订单队列已满，跳过推送")

# 主页
@app.route('/')
def home():
    keywords = load_keywords()
    error_message = request.args.get('error', '')
    monitor_status = load_monitor_status()
    auto_order_status = load_auto_order_status()
    monitor_interval = get_global_monitor_interval()
    batch_order_mode = get_global_batch_order_mode()
    refresh_stats = get_refresh_stats()
    return render_template('home.html',
                         monitor_status=monitor_status,
                         auto_order_status=auto_order_status,
                         monitor_interval=monitor_interval,
                         batch_order_mode=batch_order_mode,
                         daily_refresh_count=refresh_stats['daily_count'],
                         hourly_refresh_count=refresh_stats['hourly_count'],
                         keywords=keywords,
                         error_message=error_message)




# https://fenxiao.clim.cn/alipay/topay.do?code=FX2024762983

'''
----------------------------------------web--------------------------------
'''



def run_flask():
    print("🚀 Flask Web服务启动中...")
    print("📡 实时日志推送系统已激活")
    print("🌐 访问地址: http://localhost:5000")
    print("🔧 日志捕获系统状态检查...")

    # 测试日志推送
    import threading
    def test_logs():
        import time
        time.sleep(2)  # 等待Web服务启动
        print("✅ 日志推送测试 - 这是一条测试日志")
        print("🟢 成功：日志系统工作正常")
        print("🔴 错误：这是一条错误测试日志")
        print("🟡 警告：这是一条警告测试日志")
        print("🔵 信息：这是一条信息测试日志")

    # 启动测试线程
    test_thread = threading.Thread(target=test_logs)
    test_thread.daemon = True
    test_thread.start()

    # 实际启动Flask服务
    try:
        print("🚀 尝试启动Flask服务...")
        app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
    except OSError as e:
        if "Address already in use" in str(e) or "WinError 10048" in str(e):
            print("❌ 端口5000被占用，尝试使用端口5001...")
            app.run(host="0.0.0.0", port=5001, debug=True, use_reloader=False)
        else:
            print(f"❌ Flask启动失败: {e}")
            raise

# ==================== 异步API路由 ====================

# 异步监控开关
@app.route('/api/toggle_monitor', methods=['POST'])
def api_toggle_monitor():
    try:
        data = request.get_json()
        enabled = data.get('enabled', False)

        if enabled:
            set_monitor_status(True)
            message = '监控已启用'
        else:
            set_monitor_status(False)
            message = '监控已关闭'

        return jsonify({'success': True, 'message': message, 'enabled': enabled})
    except Exception as e:
        return jsonify({'success': False, 'message': f'操作失败: {str(e)}'})

# 异步自动下单开关
@app.route('/api/toggle_auto_order', methods=['POST'])
def api_toggle_auto_order():
    try:
        data = request.get_json()
        enabled = data.get('enabled', False)

        if enabled:
            set_auto_order_status(True)
            # 自动下单需要监控支持
            if not load_monitor_status():
                set_monitor_status(True)
                message = '自动下单已开启，监控已同时启用'
            else:
                message = '自动下单已开启'
        else:
            set_auto_order_status(False)
            message = '自动下单已关闭'

        return jsonify({
            'success': True,
            'message': message,
            'enabled': enabled,
            'monitor_enabled': load_monitor_status()
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'操作失败: {str(e)}'})

# 异步建单模式切换
@app.route('/api/toggle_batch_mode', methods=['POST'])
def api_toggle_batch_mode():
    try:
        data = request.get_json()
        enabled = data.get('enabled', False)

        set_batch_order_mode(enabled)

        if enabled:
            message = '已切换到统一建单模式'
            mode_text = '统一建单'
        else:
            message = '已切换到单独建单模式'
            mode_text = '单独建单'

        return jsonify({
            'success': True,
            'message': message,
            'enabled': enabled,
            'mode_text': mode_text
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'操作失败: {str(e)}'})

# 异步监控间隔设置
@app.route('/api/set_interval', methods=['POST'])
def api_set_interval():
    try:
        data = request.get_json()
        interval = data.get('interval')

        if not interval:
            return jsonify({'success': False, 'message': '请输入监控间隔'})

        try:
            interval_int = int(interval)
            if interval_int < 1:
                return jsonify({'success': False, 'message': '监控间隔必须大于0秒'})
        except ValueError:
            return jsonify({'success': False, 'message': '请输入有效的数字'})

        set_monitor_interval(interval_int)
        return jsonify({
            'success': True,
            'message': f'监控间隔已设置为 {interval_int} 秒',
            'interval': interval_int
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'设置失败: {str(e)}'})

# 异步添加关键词
@app.route('/api/add_keyword', methods=['POST'])
def api_add_keyword():
    try:
        data = request.get_json()
        keyword = data.get('keyword', '').strip()

        if not keyword:
            return jsonify({'success': False, 'message': '请输入关键词'})

        keywords = load_keywords()
        if keyword in keywords:
            return jsonify({'success': False, 'message': '关键词已存在'})

        save_keyword(keyword)

        return jsonify({
            'success': True,
            'message': f'关键词 "{keyword}" 添加成功',
            'keyword': keyword,
            'total_count': len(keywords)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'添加失败: {str(e)}'})

# 异步删除关键词
@app.route('/api/delete_keyword', methods=['POST'])
def api_delete_keyword():
    try:
        data = request.get_json()
        keyword = data.get('keyword', '').strip()

        if not keyword:
            return jsonify({'success': False, 'message': '请选择要删除的关键词'})

        keywords = load_keywords()
        if keyword not in keywords:
            return jsonify({'success': False, 'message': '关键词不存在'})

        remove_keyword(keyword)

        return jsonify({
            'success': True,
            'message': f'关键词 "{keyword}" 删除成功',
            'keyword': keyword,
            'total_count': len(keywords)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'})

# 异步添加订单到历史记录
@app.route('/api/add_order_history', methods=['POST'])
def api_add_order_history():
    try:
        data = request.get_json()
        order = data.get('order', '').strip()

        if not order:
            return jsonify({'success': False, 'message': '订单号不能为空'})

        from common.orders import get_global_orders_history, save_orders_history

        orders_history = get_global_orders_history()
        if order in orders_history:
            return jsonify({'success': False, 'message': '订单已存在于历史记录'})

        save_orders_history(order)

        return jsonify({
            'success': True,
            'message': f'订单 {order} 已添加到历史记录',
            'order': order
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'添加失败: {str(e)}'})

# 强制关闭测试模式
@app.route('/api/close_test_mode', methods=['POST'])
def api_close_test_mode():
    try:
        set_test_mode(False)
        print("🧪 测试模式已强制关闭")
        return jsonify({
            'success': True,
            'message': '测试模式已关闭',
            'test_mode': False
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'关闭失败: {str(e)}'})

# 获取刷新统计数据
@app.route('/api/refresh_stats', methods=['GET'])
def api_get_refresh_stats():
    try:
        stats = get_refresh_stats()
        return jsonify({
            'success': True,
            'daily_count': stats['daily_count'],
            'hourly_count': stats['hourly_count'],
            'daily_date': stats['daily_date'],
            'hourly_hour': stats['hourly_hour']
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取失败: {str(e)}',
            'daily_count': 0,
            'hourly_count': 0
        })

if __name__ == '__main__':
    try:
        print("🚀 尝试启动Flask服务...")
        app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
    except OSError as e:
        if "Address already in use" in str(e) or "WinError 10048" in str(e):
            print("❌ 端口5000被占用，尝试使用端口5001...")
            app.run(host="0.0.0.0", port=5001, debug=True, use_reloader=False)
        else:
            print(f"❌ Flask启动失败: {e}")
            raise
