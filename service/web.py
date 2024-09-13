# -*- coding:utf-8 -*-
#!/usr/bin/python



from flask import Flask, request, jsonify, render_template_string, redirect, url_for
from common.keywords import load_keywords, save_keyword, remove_keyword
from common.status import load_refresh_status, set_refresh_status
from common.status import load_intensify_refresh_status, set_intensify_refresh_status
from common.orders import save_orders_history, get_global_orders_history, get_orders, set_orders
from jobs import OnceJobThread
from jobs.job_checkout import RefreshThread


app = Flask(__name__)

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


# 添加关键词
@app.route('/add_intensify_keyword', methods=['POST'])
def add_intensify_keyword():
    keywords = load_keywords(True)
    new_keyword = request.form.get('keyword', '').strip()
    print('new_keyword', new_keyword)
    print('keywords', keywords)
    if new_keyword and new_keyword not in keywords:
        save_keyword(new_keyword, True)  # 保存新添加的关键词
        return redirect(url_for('intensify'))  # 重定向到主页
    else:
        return redirect(url_for('intensify', error='Invalid or duplicate keyword'))

# 删除关键字
@app.route('/delete_intensify_keyword', methods=['POST'])
def delete_intensify_keyword():
    keyword_to_delete = request.form.get('keyword')
    if not keyword_to_delete:
        return jsonify({"status": "error", "message": "Keyword is required"}), 400

    keywords = load_keywords(True)
    if keyword_to_delete not in keywords:
        return jsonify({"status": "error", "message": "Keyword not found"}), 404

    remove_keyword(keyword_to_delete, True)

    return redirect(url_for('intensify'))  # 重定向到主页

# 启用监控
@app.route('/enable_listener', methods=['POST'])
def enable_listener():
    set_refresh_status(True)
    
    thread = OnceJobThread(RefreshThread())
    thread.start()
    # return jsonify({"status": "success", "message": "yes"}), 200
    return redirect(url_for('home'))  # 重定向到主页

@app.route('/disable_listener', methods=['POST'])
def disable_listener():
    set_refresh_status(False)
    # return jsonify({"status": "success", "message": "yes"}), 200
    return redirect(url_for('home'))  # 重定向到主页


# 启用下单
@app.route('/enable_order', methods=['POST'])
def enable_order():
    set_intensify_refresh_status(True)
    # return jsonify({"status": "success", "message": "yes"}), 200
    return redirect(url_for('intensify'))  # 重定向到主页

@app.route('/disable_order', methods=['POST'])
def disable_order():
    set_intensify_refresh_status(False)
    # return jsonify({"status": "success", "message": "yes"}), 200
    return redirect(url_for('intensify'))  # 重定向到主页



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
    return jsonify({'orders': new_orders})

# 主页
@app.route('/')
def home():
    keywords = load_keywords()
    error_message = request.args.get('error', '')
    keywords_list = '<br>'.join(keywords)  # 将关键词列表转为 HTML 格式的字符串
    status = load_refresh_status()
    return render_template_string('''
        <h1>库存监控</h1>
        <p style="color: red;">运行状态: {{ '开' if status else '关' }}</p>                        
        <form method="post" action="{{ url_for('add_keyword') }}">
            <input type="text" name="keyword" placeholder="输入规格名称" required>
            <button type="submit">添加规格</button>
        </form>

        <form method="post" action="{{ url_for('delete_keyword') }}">
            <input type="text" name="keyword" placeholder="输入规格名称" required>
            <button type="submit">删除规格</button>
        </form>
                                  
        <form method="post" action="{{ url_for('enable_listener') }}">
            <button type="submit">启用监控</button>
        </form>         
        <form method="post" action="{{ url_for('disable_listener') }}">
            <button type="submit">关闭监控</button>
        </form>                                                
        <p>当前规格:</p>
        <p>{{ keywords_list|safe }}</p>
              
    ''', status=status,keywords_list=keywords_list)



# 主页
@app.route('/intensify')
def intensify():
    keywords = load_keywords(True)
    error_message = request.args.get('error', '')
    keywords_list = '<br>'.join(keywords)  # 将关键词列表转为 HTML 格式的字符串
    intensify_status = load_intensify_refresh_status()
    return render_template_string('''
        <h1>下单监控</h1>
        <p style="color: red;">运行状态: {{ '开' if intensify_status else '关' }}</p>                        
        <form method="post" action="{{ url_for('add_intensify_keyword') }}">
            <input type="text" name="keyword" placeholder="输入规格名称" required>
            <button type="submit">添加规格</button>
        </form>

        <form method="post" action="{{ url_for('delete_intensify_keyword') }}">
            <input type="text" name="keyword" placeholder="输入规格名称" required>
            <button type="submit">删除规格</button>
        </form>
                                  
        <form method="post" action="{{ url_for('enable_order') }}">
            <button type="submit">启用监控</button>
        </form>         
        <form method="post" action="{{ url_for('disable_order') }}">
            <button type="submit">关闭监控</button>
        </form>                                                
        <p>当前规格:</p>
        <p>{{ keywords_list|safe }}</p>

        <!-- 订单展示 -->
        <h2>订单列表</h2>
        <div id="orders"></div>
                                                            
        <!-- Ajax 代码 -->
        <script>
            // https://fenxiao.clim.cn/alipay/topay.do?code=FX2024762983                     
            function openNewTab(pay_url) {
                // 打开新标签，指向 /new_tab 路由
                window.open(pay_url, "_blank");
            }
                                  
            function fetchOrders() {
                fetch('/orders')
                .then(response => response.json())
                .then(data => {
                    const ordersDiv = document.getElementById('orders');
                    ordersDiv.innerHTML = '';

                    if (data.orders && data.orders.length > 0) {
                        data.orders.forEach(order => {
                            ordersDiv.innerHTML += '<p>' + order + '</p>';
                            pay_url = 'https://fenxiao.clim.cn/alipay/topay.do?code=' + order;
                            openNewTab(pay_url);
                        });
                    } else {
                        ordersDiv.innerHTML = '<p>没有新订单</p>';
                    }
                })
                .catch(error => {
                    console.error('Error fetching orders:', error);
                });
            }
            // fetchOrders();
            // 每隔 5 秒钟执行一次 fetchOrders
            setInterval(fetchOrders, 5000);
        </script>               
    ''', intensify_status=intensify_status,keywords_list=keywords_list)

# https://fenxiao.clim.cn/alipay/topay.do?code=FX2024762983

'''
----------------------------------------web--------------------------------
'''



def run_flask(self):
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)