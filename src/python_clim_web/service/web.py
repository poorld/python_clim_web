# -*- coding:utf-8 -*-
#!/usr/bin/python

import os
import json
import time
import sys
import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, Response
from ..common.keywords import load_keywords, save_keyword, remove_keyword, get_global_keywords
from ..common.status import load_monitor_status, set_monitor_status
from ..common.status import load_auto_order_status, set_auto_order_status
from ..common.status import load_monitor_interval, set_monitor_interval, get_global_monitor_interval
from ..common.status import load_batch_order_mode, set_batch_order_mode, get_global_batch_order_mode
from ..common.status import load_test_mode, set_test_mode, get_global_test_mode
from ..common.status import load_group_enabled, set_group_enabled, get_global_group_enabled
from ..common.status import load_group_size, set_group_size, get_global_group_size
from ..common.status import get_refresh_stats
from ..common.orders import save_orders_history, get_global_orders_history, get_orders, set_orders
from ..jobs import OnceJobThread
from ..jobs.job_checkout import RefreshThread
import threading
from flask import send_file
import io
import queue
import logging
from ..common.logger import get_logger

logger = get_logger()

# 获取模板目录路径
current_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(current_dir, '..', 'templates')
static_dir = os.path.join(template_dir, 'static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

# 订单推送队列
order_queue = queue.Queue()
# 日志推送队列
log_queue = queue.Queue(maxsize=1000)  # 限制队列大小防止内存溢出
clients = []  # 存储SSE客户端连接

# Web UI 日志处理器
class WebLogHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        try:
            # 格式化日志消息
            log_entry = self.format(record)
            
            # 准备要推送到前端的数据
            log_data = {
                "timestamp": datetime.datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                "message": log_entry,
                "level": record.levelname.lower()
            }
            
            # 将日志数据放入队列
            self.log_queue.put(log_data, block=False)
        except queue.Full:
            # 队列满时，可以考虑丢弃最旧的日志
            try:
                self.log_queue.get_nowait()
                self.log_queue.put(log_data, block=False)
            except queue.Empty:
                pass
        except Exception:
            # 忽略日志处理中的异常，防止程序崩溃
            self.handleError(record)

# 创建并配置Web日志处理器
web_log_handler = WebLogHandler(log_queue)
web_log_handler.setLevel(logging.INFO)  # 设置推送到Web的最低日志级别
formatter = logging.Formatter('%(message)s') # Web界面只显示纯消息
web_log_handler.setFormatter(formatter)

# 将Web处理器添加到主logger
logger.addHandler(web_log_handler)

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
    logger.debug(f'new_keyword: {new_keyword}')
    logger.debug(f'keywords: {keywords}')
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

            logger.info(f"⚡ 监控间隔已更新为: {interval}秒 ({mode_text})")
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
    logger.info(f"🛒 建单模式已切换为: {mode_text}")
    return redirect(url_for('home'))

# 测试下单（只弹一次付款）- 异步版本
@app.route('/test_order', methods=['POST'])
def test_order():
    try:
        # 临时启用测试模式
        set_test_mode(True)
        logger.info("🧪 测试模式已启用：只弹一次付款窗口")

        # 强制执行测试检测（跳过商品总数检查）
        from ..common.keywords import get_global_keywords

        keywords = get_global_keywords()
        if not keywords:
            logger.error("❌ 没有设置关键词，无法执行测试")
            set_test_mode(False)
            return jsonify({'success': False, 'message': '没有设置关键词，无法执行测试'})

        logger.info(f"🧪 测试模式：开始检测 {len(keywords)} 个关键词")

        # 在后台线程中执行测试
        import threading
        def run_test():
            try:
                from ..jobs.job_checkout import TestModeStrategy
                strategy = TestModeStrategy()
                strategy.execute(keywords)

                # 检测完成后关闭测试模式
                set_test_mode(False)
                logger.info("🧪 测试模式已关闭")
            except Exception as e:
                logger.error(f"❌ 测试执行失败: {e}", exc_info=True)
                set_test_mode(False)

        # 启动后台线程
        test_thread = threading.Thread(target=run_test)
        test_thread.daemon = True
        test_thread.start()

        return jsonify({'success': True, 'message': f'测试模式已启动，正在检测 {len(keywords)} 个关键词...'})

    except Exception as e:
        logger.error(f"❌ 测试下单失败: {e}", exc_info=True)
        set_test_mode(False)  # 确保测试模式被关闭
        return jsonify({'success': False, 'message': f'测试下单失败: {str(e)}'})



# 获取所有订单
@app.route('/orders', methods=['GET'])
def orders():
    orders = get_orders()
    logger.debug(f'orders: {orders}')
    orders_history = get_global_orders_history()
    new_orders = []
    for order in orders:
        if order not in orders_history:
            new_orders.append(order)
            orders_history.append(order)
            save_orders_history(order)
    logger.debug(f'new_orders: {new_orders}')

    return jsonify({'orders': new_orders})

# SSE订单推送端点
@app.route('/stream')
def stream():
    def event_stream():
        yield "data: {\"type\": \"connected\"}\n\n"

        while True:
            try:
                message = order_queue.get(timeout=1)

                if isinstance(message, dict):
                    data = json.dumps(message)
                    logger.debug(f"📤 SSE发送消息: {message}")
                else:
                    data = json.dumps({
                        "type": "new_order",
                        "order": message,
                        "timestamp": time.time()
                    })
                    logger.debug(f"📤 SSE发送订单: {message}")

                yield f"data: {data}\n\n"
                order_queue.task_done()
            except queue.Empty:
                yield "data: {\"type\": \"heartbeat\"}\n\n"
            except Exception as e:
                logger.error(f"❌ SSE错误: {e}")
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
            yield "data: {\"type\": \"connected\"}\n\n"
            logger.info("📡 新的日志SSE客户端已连接")

            while True:
                try:
                    log_data = log_queue.get(timeout=30)
                    data = json.dumps({
                        "type": "log",
                        "timestamp": log_data["timestamp"],
                        "message": log_data["message"],
                        "level": log_data["level"]
                    })
                    yield f"data: {data}\n\n"
                    log_queue.task_done()
                except queue.Empty:
                    yield "data: {\"type\": \"heartbeat\"}\n\n"
                except Exception as e:
                    logger.error(f"🔴 日志SSE内部错误: {e}")
                    break
        except Exception as e:
            logger.error(f"🔴 日志SSE连接错误: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'连接错误: {str(e)}'}, ensure_ascii=False)}\n\n"

    response = Response(log_event_stream(), mimetype="text/event-stream")
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response



# 推送新订单到所有客户端
def push_order_to_clients(order):
    """将新订单推送到订单队列"""
    try:
        order_queue.put(order, block=False)
        logger.info(f"📤 订单 {order} 已推送到队列，队列大小: {order_queue.qsize()}")
    except queue.Full:
        logger.warning("❌ 订单队列已满，跳过推送")

def remove_paid_orders(paid_orders):
    """移除已付款的订单"""
    from ..common.orders import orders

    for order in paid_orders:
        if order in orders:
            orders.remove(order)
            logger.info(f"🗑️ 已从订单列表移除: {order}")

            try:
                removal_data = {
                    "type": "remove_order",
                    "order": order,
                    "timestamp": time.time()
                }
                order_queue.put(removal_data, block=False)
                logger.info(f"📤 订单移除消息已推送: {order}")
            except queue.Full:
                logger.warning("❌ 订单队列已满，跳过移除消息推送")

# 主页
@app.route('/')
def home():
    keywords = load_keywords()
    error_message = request.args.get('error', '')
    success_message = request.args.get('success', '')
    monitor_status = load_monitor_status()
    auto_order_status = load_auto_order_status()
    monitor_interval = get_global_monitor_interval()
    batch_order_mode = get_global_batch_order_mode()
    group_enabled = get_global_group_enabled()
    group_size = get_global_group_size()
    refresh_stats = get_refresh_stats()
    return render_template('home.html',
                         monitor_status=monitor_status,
                         auto_order_status=auto_order_status,
                         monitor_interval=monitor_interval,
                         batch_order_mode=batch_order_mode,
                         group_enabled=group_enabled,
                         group_size=group_size,
                         daily_refresh_count=refresh_stats['daily_count'],
                         hourly_refresh_count=refresh_stats['hourly_count'],
                         keywords=keywords,
                         error_message=error_message,
                         success_message=success_message)


@app.route('/health')
def health_check():
    """
    一个专门给平台健康检查用的路径。
    它不做任何事，只为了快速返回一个 200 OK 状态码。
    """
    return "OK", 200




'''
----------------------------------------web--------------------------------
'''

def run_flask():
    logger.info("🚀 Flask Web服务启动中...")
    logger.info("📡 实时日志推送系统已激活")
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🌐 访问地址: http://0.0.0.0:{port}")
    logger.info("🔧 日志捕获系统状态检查...")

    import threading
    def test_logs():
        import time
        time.sleep(2)
        logger.info("✅ 日志推送测试 - 这是一条测试日志")
        logger.info("🟢 成功：日志系统工作正常")
        logger.error("🔴 错误：这是一条错误测试日志")
        logger.warning("🟡 警告：这是一条警告测试日志")

    test_thread = threading.Thread(target=test_logs)
    test_thread.daemon = True
    test_thread.start()

    try:
        logger.info("🚀 尝试启动Flask服务...")
        app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)
    except OSError as e:
        if "Address already in use" in str(e) or "WinError 10048" in str(e):
            logger.error(f"❌ 端口 {port} 被占用，请使用其他端口。")
        else:
            logger.error(f"❌ Flask启动失败: {e}", exc_info=True)
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

# 异步分组开关
@app.route('/api/toggle_group_enabled', methods=['POST'])
def api_toggle_group_enabled():
    try:
        data = request.get_json()
        enabled = data.get('enabled', False)

        set_group_enabled(enabled)

        if enabled:
            message = '分组模式已启用'
        else:
            message = '分组模式已禁用'

        return jsonify({
            'success': True,
            'message': message,
            'enabled': enabled
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'操作失败: {str(e)}'})

# 异步分组大小设置
@app.route('/api/update_group_size', methods=['POST'])
def api_update_group_size():
    try:
        data = request.get_json()
        size = data.get('size', 5)

        if not isinstance(size, int) or size < 1 or size > 20:
            return jsonify({'success': False, 'message': '分组大小必须在1-20之间'})

        set_group_size(size)

        return jsonify({
            'success': True,
            'message': f'分组大小已设置为{size}个',
            'size': size
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

        from ..common.orders import get_global_orders_history, save_orders_history

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
        logger.info("🧪 测试模式已强制关闭")
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


# 手动检查订单状态
@app.route('/api/check_order_status', methods=['POST'])
def api_check_order_status():
    try:
        from ..service.product_checkout import check_order_payment_status
        check_order_payment_status()
        return jsonify({'success': True, 'message': '订单状态检查完成'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'检查失败: {str(e)}'})
    
# 关键词导出
@app.route('/api/export_keywords', methods=['GET'])
def api_export_keywords():
    try:
        keywords = get_global_keywords()
        if not keywords:
            return redirect(url_for('home', error='没有关键词可以导出'))

        # 创建一个包含所有关键词的字符串，每行一个
        file_content = "\n".join(keywords)
        
        # 创建一个内存中的文本文件
        buffer = io.BytesIO(file_content.encode('utf-8'))
        buffer.seek(0)

        # 创建带时间戳的文件名
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"keywords_export_{timestamp}.txt"

        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='text/plain'
        )
    except Exception as e:
        logger.error(f"❌ 导出关键词失败: {e}", exc_info=True)
        return redirect(url_for('home', error=f'导出失败: {str(e)}'))

# 关键词导入
@app.route('/api/import_keywords', methods=['POST'])
def api_import_keywords():
    if 'file' not in request.files:
        return redirect(url_for('home', error='未选择文件'))
    
    file = request.files['file']

    if file.filename == '':
        return redirect(url_for('home', error='未选择文件'))

    if file and file.filename.endswith('.txt'):
        try:
            content = file.read().decode('utf-8')
            imported_keywords = [line.strip() for line in content.splitlines() if line.strip()]
            
            if not imported_keywords:
                return redirect(url_for('home', error='文件为空或格式不正确'))

            current_keywords = get_global_keywords()
            new_keywords_count = 0
            for keyword in set(imported_keywords): # 使用set去重
                if keyword not in current_keywords:
                    save_keyword(keyword)
                    new_keywords_count += 1
            
            message = f"导入成功！新增 {new_keywords_count} 个关键词。"
            logger.info(message)
            return redirect(url_for('home', success=message))
        except Exception as e:
            logger.error(f"❌ 导入关键词失败: {e}", exc_info=True)
            return redirect(url_for('home', error=f'导入失败: {str(e)}'))
    else:
        return redirect(url_for('home', error='请上传.txt格式的文件'))

# 智能发现API
@app.route('/api/find_updates', methods=['GET'])
def api_find_updates():
    """
    一个用于测试智能发现功能的API端点。
    支持手动指定排序字段进行测试, e.g., /api/find_updates?sort_field=update_time
    """
    try:
        # 从查询参数获取用户手动指定的排序字段
        sort_field_override = request.args.get('sort_field', None)

        from ..service.product_checkout import find_latest_updated_products
        latest_products_by_field = find_latest_updated_products(sort_field_override=sort_field_override)
        
        if latest_products_by_field:
            num_found_fields = len(latest_products_by_field)
            return jsonify({
                'success': True,
                'message': f"扫描完成！共发现 {num_found_fields} 个有效的排序字段。",
                'results': latest_products_by_field
            })
        else:
            if sort_field_override:
                message = f"使用指定字段 '{sort_field_override}' 未发现商品，或该字段无效。"
            else:
                message = "自动扫描完成，未能找到有效的更新排序字段或无新商品。"
            return jsonify({'success': True, 'message': message, 'results': {}})
    except Exception as e:
        logger.error(f"执行智能发现时出错: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'执行智能发现时出错: {str(e)}'})

if __name__ == '__main__':
    # run_flask()
    pass