# -*- coding:utf-8 -*-
#!/usr/bin/python

import requests
from bs4 import BeautifulSoup
import concurrent.futures
import time
from datetime import datetime, timedelta
from http import cookiejar
import urllib.parse
from flask import Flask, request, jsonify, render_template_string, redirect, url_for
import threading
from pushplus import PushPlus
import re


app = Flask(__name__)

status = False
keywords = []
orders_history = []

# 设置最大金额限制
max_money = 35000

login_user = {
    'name': '琴琴国内-国内',
    'password': '123456'
}

url_login = 'https://fenxiao.clim.cn/login/checkLogin.do'

# 请求头
headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-encoding': 'gzip, deflate, br, zstd',
    'content-type': 'application/x-www-form-urlencoded',
    'cookie': 'JSESSIONID=52E75FA6DCC05C4858625F412666175C',
    'host': 'fenxiao.clim.cn',
    'origin': 'https://fenxiao.clim.cn',
    'referer': 'https://fenxiao.clim.cn/shop/products.do',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0.0.0 Safari/537.36'
}

# URLs 和 参数
url_query_product = 'https://fenxiao.clim.cn/shop/products.do'
param_query_product = {
    'keyword': '',
    'recommendTypeCode': 1,
    'sort': 'desc',
    'sortFiled': 'online_time'
}

url_select_buy_product = 'https://fenxiao.clim.cn/shop/selectBuyProduct.do?skc='
url_save_cart = 'https://fenxiao.clim.cn/shop/saveCart.do'
param_save_cart = {'typeCode': 0, 'price': 0, 'productCode': 0, 'count': 0}
url_cart = 'https://fenxiao.clim.cn/shop/cart.do?v=4.0'
url_settle = 'https://fenxiao.clim.cn/shop/settle.do?checked='
url_settle_save = 'https://fenxiao.clim.cn/shop/settlesave.do?statuscode=5'

# 结算数据
settleData = {
    'rankCode': 0, 'tagCode': 0, 'shippingMethod': 1, 'thirdcode': None,
    'receiver': '李不帅', 'recvphone': '18529551929', 'provincecode': 19, 'citycode': 202, 'countycode': 1754,
    'recvaddr': '化龙镇山门大道700号', 'exchangeRate': 1, 'paid': 0, 'rmbAmount': 0, 'cartCodes': '0',
    'itemPrice': 0, 'itemRmbAmount': 0, 'defectNo': '', 'productcode': '0', 'counts': 0
}



# 付款码
# https://fenxiao.clim.cn/order/orderlist.do?statuscode=10&startTime=&endTime=&orderCode=&receiver=&phone=18529551929&thirdCode=&pageIndex=&pageSize=

url_orderlist = 'https://fenxiao.clim.cn/order/orderlist.do?statuscode=10&startTime=&endTime=&orderCode=&receiver=&phone=18529551929&thirdCode=&pageIndex=&pageSize='






'''
----------------------------------------web--------------------------------
'''
# 获取所有关键词
@app.route('/keywords', methods=['GET'])
def get_keywords():
    return jsonify({'keywords': keywords})

# 获取所有订单
@app.route('/orders', methods=['GET'])
def orders():
    orders = getOrders()
    new_orders = []
    for order in orders:
        if order not in orders_history:
            new_orders.append(order)
            orders_history.append(order)
            save_order(order)
    print('new_orders', new_orders)
    return jsonify({'orders': new_orders})


# 添加关键词
@app.route('/add_keyword', methods=['POST'])
def add_keyword():
    new_keyword = request.form.get('keyword', '').strip()
    print('new_keyword', new_keyword)
    print('keywords', keywords)
    if new_keyword and new_keyword not in keywords:
        keywords.append(new_keyword)
        save_keyword(new_keyword)  # 保存新添加的关键词
        return redirect(url_for('home'))  # 重定向到主页
    else:
        return redirect(url_for('home', error='Invalid or duplicate keyword'))

# 立即测试
@app.route('/enable_listener', methods=['POST'])
def enable_listener():
    global status
    status = True
    set_linsten_status(status)
    # return jsonify({"status": "success", "message": "yes"}), 200
    return redirect(url_for('home'))  # 重定向到主页

@app.route('/disable_listener', methods=['POST'])
def disable_listener():
    global status
    status = False
    set_linsten_status(status)
    # return jsonify({"status": "success", "message": "yes"}), 200
    return redirect(url_for('home'))  # 重定向到主页

# 删除关键字
@app.route('/delete_keyword', methods=['POST'])
def delete_keyword():
    keyword_to_delete = request.form.get('keyword')
    if not keyword_to_delete:
        return jsonify({"status": "error", "message": "Keyword is required"}), 400

    keywords = load_keywords()
    if keyword_to_delete not in keywords:
        return jsonify({"status": "error", "message": "Keyword not found"}), 404

    # Remove keyword
    keywords.remove(keyword_to_delete)
    print('keywords', keywords)
    with open('keywords.txt', 'w') as f:
        for keyword in keywords:
            f.write(f"{keyword}\n")

    return redirect(url_for('home'))  # 重定向到主页


# 主页
@app.route('/')
def home():
    keywords = load_keywords()
    error_message = request.args.get('error', '')
    keywords_list = '<br>'.join(keywords)  # 将关键词列表转为 HTML 格式的字符串
    status = linsten_status()
    return render_template_string('''
        <h1>规格名称管理</h1>
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
            fetchOrders();
            // 每隔 1 秒钟执行一次 fetchOrders
            setInterval(fetchOrders, 30000);
                                  
        </script>                         
    ''', status=status,keywords_list=keywords_list)






'''
----------------------------------------web--------------------------------
'''


# 登录
def do_login():
    print('do_login')
    response = requests.post(url=url_login, data=login_user)
    print(response.status_code)
    data = response.json()
    print(data)
    if data['result'] is True:
        cookies = requests.utils.dict_from_cookiejar(response.cookies)
        cookiesValue = ''
        for key in cookies.keys():
            cookiesValue += key + '=' + cookies.get(key) + ';'
        print(cookiesValue)
        save_cookie(cookiesValue)
        print('loadcookie', load_cookie())
        headers['cookie'] = cookiesValue
        print('-' * 50)

# 查询商品信息
def query_product(keyword):
    print('query_product', keyword)

    sku = None

    param_query_product['keyword'] = keyword
    headers['cookie'] = load_cookie()
    resp = requests.post(url=url_query_product, headers=headers, params=param_query_product)
    print(f'status_code: {resp.status_code}')
    print(f'url: {resp.url}')
    if 'login.do' in resp.url:
        do_login()
        return query_product(keyword)
    else:
        # print(f'content: {resp.content}')
        

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")
            rows = soup.select('tbody tr')
            print('商品列表:', len(rows))

            if rows:
                row_0 = rows[0]
                buttons = row_0.find_all('button')
                button_titles = [button.get('title') for button in buttons]
                print('商品编号:', button_titles)
                sku = button_titles[0] if button_titles else None

    return sku

# 选择商品并保存到购物车
def selectBuyDefect(sku):
    print('selectBuyDefect')
    sku = urllib.parse.quote(sku)
    print('sku', sku)
    resp = requests.get(url=f'{url_select_buy_product}{sku}', headers=headers)
    print(f'status_code: {resp.status_code}')
    # print('content:', resp.content.decode('utf-8'))
    
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")
        return saveCart(soup)
    return None

# 保存到购物车
def saveCart(soup: BeautifulSoup):
    print('saveCart')
    type_code = soup.find('input', {'name': 'typeCode'})['value']
    price = soup.find('input', {'name': 'price'})['value']
    product_code = soup.find('input', {'name': 'productCode'})['value']
    
    stock = soup.find('input', {'id': f'stock{product_code}'})['value']
    count = min(float(stock), max_money / float(price))
    count = int(count)
    param_save_cart.update({
        'typeCode': type_code,
        'price': price,
        'productCode': product_code,
        'count': count
    })

    print('param_save_cart', param_save_cart)

    resp = requests.post(url=url_save_cart, headers=headers, params=param_save_cart)
    print(f'status_code: {resp.status_code}')
    print('content:', resp.content.decode('utf-8'))
    if resp.status_code == 200:
        print('加入购物车成功')
        return product_code
    return None

# 查看购物车
def check_cart(product_code_value):
    resp = requests.get(url_cart, headers=headers)
    soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")
    rows = soup.select('tbody tr')

    for row in rows:
        rank_code = row.find('input', {'class': 'rankCode'})['value']
        product_code = row.find_all('td')[2].get_text(strip=True)
        if product_code == product_code_value:
            return checkout(row.find('input', {'type': 'checkbox'})['value'])
    return False

# 结算
def checkout(checkId):
    print(f'结算商品: {checkId}')
    resp = requests.get(url=f'{url_settle}{checkId}', headers=headers)
    soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")

    rows = soup.select('tbody tr')
    row_0 = rows[0]
    row_0_td = row_0.find_all('td')
    name = row_0_td[4].get_text(strip=True)
    print('name', name)
    
    # 获取结算数据
    settleData.update({
        'rankCode': soup.find('input', {'name': 'rankCode'})['value'],
        'tagCode': soup.find('input', {'name': 'tagCode'})['value'],
        'shippingMethod': soup.find('input', {'name': 'shippingMethod'})['value'],
        'thirdcode': soup.find('input', {'name': 'thirdcode'}).get('value', None),
        'exchangeRate': soup.find('input', {'name': 'exchangeRate'})['value'],
        'paid': soup.find('input', {'name': 'paid'})['value'],
        'rmbAmount': soup.find('input', {'name': 'rmbAmount'})['value'],
        'cartCodes': soup.find('input', {'name': 'cartCodes'})['value'],
        'itemPrice': soup.find('input', {'name': 'itemPrice'})['value'],
        'itemRmbAmount': soup.find('input', {'name': 'itemRmbAmount'})['value'],
        'productcode': soup.find('input', {'name': 'productcode'})['value'],
        'counts': soup.find('input', {'name': 'counts'})['value']
    })

    # table = soup.find('table', {'class': 'table table-striped'})
    # table_html = str(table)
    # print('table_html', table_html)

    
    resp = requests.post(url=url_settle_save, headers=headers, params=settleData)
    print(f'status_code: {resp.status_code}')
    content = resp.content.decode('utf-8')
    print('content:', )
    # return resp.status_code == 200
    data = resp.json()
    wxpush = PushPlus()
    if data['resultCode'] == 0:
        
        wxpush.sendMsg(name, f'下单 {name},数量{settleData["counts"]},金额{settleData["itemPrice"]}')
        return True
    wxpush.sendMsg(name, f'下单失败!{content}')
    return False


def getOrders():
    print('getOrder')
    resp = requests.get(url=url_orderlist, headers=headers)
    soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")
    # print('soup', soup)
    # 查找所有包含 'javascript:showOrder' 的 <a> 标签
    links = soup.find_all('a', href=True)
    orders = []
    for link in links:
        href = link['href']
        # 使用正则表达式提取订单号
        # 确保 href 属性包含 showOrder 调用
        if 'showOrder' in href:
            match = re.search(r"showOrder\('(\w+)'\)", href)
            if match:
                order_number = match.group(1)
                print(f"提取的订单号: {order_number}")
                orders.append(order_number)
    return orders

def is_within_time_range(start_hour=7, end_hour=12):
    """判断当前时间是否在指定的时间范围内"""
    now = datetime.now().time()
    start_time = datetime.now().replace(hour=start_hour, minute=0, second=0, microsecond=0).time()
    end_time = datetime.now().replace(hour=end_hour, minute=0, second=0, microsecond=0).time()
    return start_time <= now <= end_time

def linsten_status():
    try:
        with open('status.txt', 'r') as f:
            return f.readline().strip() == 'True'
    except FileNotFoundError:
        return False

def set_linsten_status(status: bool):
    """保存成功处理的关键字到文件中"""
    with open('status.txt', 'w') as f:
        f.write(f"{status}\n")

def save_keyword(keyword):
    """保存成功处理的关键字到文件中"""
    with open('keywords.txt', 'a') as f:
        f.write(f"{keyword}\n")

def load_keywords():
    """加载已成功处理的关键字"""
    try:
        with open('keywords.txt', 'r') as f:
            lines = f.readlines()
            return [line.strip() for line in lines]
    except FileNotFoundError:
        return []

def save_order(order):
    """保存成功处理的关键字到文件中"""
    with open('orders.txt', 'a') as f:
        f.write(f"{order}\n")

def load_orders():
    """加载已成功处理的关键字"""
    try:
        with open('orders.txt', 'r') as f:
            lines = f.readlines()
            return [line.strip() for line in lines]
    except FileNotFoundError:
        return []

def save_keyword_status(keyword):
    """保存成功处理的关键字到文件中"""
    with open('processed_keywords.txt', 'a') as f:
        f.write(f"{keyword},{datetime.now().date()}\n")

def load_processed_keywords():
    """加载已成功处理的关键字"""
    try:
        with open('processed_keywords.txt', 'r') as f:
            lines = f.readlines()
            return {line.split(',')[0]: line.split(',')[1].strip() for line in lines}
    except FileNotFoundError:
        return {}

def save_cookie(cookie):
    """保存成功处理的关键字到文件中"""
    with open('cookie.txt', 'w') as f:
        f.write(f"{cookie}")

def load_cookie():
    """保存成功处理的关键字到文件中"""
    try:
        with open('cookie.txt', 'r') as f:
            return f.readline()
    except FileNotFoundError:
        return ''

def process_keyword(keyword):
    # if not is_within_time_range():
    #     print("不在指定的时间范围内，等待...")
    #     return False

    processed_keywords = load_processed_keywords()
    
    # 如果今天已经处理过这个关键字，则跳过
    today_str = str(datetime.now().date())
    if keyword in processed_keywords and processed_keywords[keyword] == today_str:
        print(f"今天已经成功处理过关键字 {keyword}，跳过...")
        return False

    # 处理流程
    sku = query_product(keyword)
    print('sku', sku)
    if sku:
        product_code_value = selectBuyDefect(sku)
        if product_code_value:
            checkout_result = check_cart(product_code_value)
            if checkout_result:
                print(f"关键字 {keyword} 处理成功，停止今天对此关键字的处理。")
                save_keyword_status(keyword)
                return True

    return False


def run_flask():
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)

# 启动关键字处理器
def run_keyword_processor():
    while True:
        if status:
            foreach_keywords()
            # 每隔一段时间再重新检查是否需要继续处理关键词
            time.sleep(2)  # 每隔 60 秒检查一次

def foreach_keywords():
    keywords = load_keywords()
    print('keywords', keywords)
    # 使用 map 来将每个关键词交给 process_keyword 函数并行处理
    for keyword in keywords:
        process_keyword(keyword)

if __name__ == "__main__":
    # keywords = ['C2712QBMI5', 'CH137SVM6A']  # 要处理的关键词列表

    # do_login()
    headers['cookie'] = load_cookie()


    # status = linsten_status()
    # keywords = load_keywords()
    orders_history = load_orders()

    # 启动 Flask 应用程序
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    # run_keyword_processor()

    # getOrders()

    
