# -*- coding:utf-8 -*-
#!/usr/bin/python

import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import urllib.parse
import threading
from pushplus import PushPlus
import re
from common.orders import set_orders





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
# param_save_cart = {'typeCode': 0, 'price': 0, 'productCode': 0, 'count': 0}
url_cart = 'https://fenxiao.clim.cn/shop/cart.do?v=4.0'
url_settle = 'https://fenxiao.clim.cn/shop/settle.do?checked='
url_settle_save = 'https://fenxiao.clim.cn/shop/settlesave.do?statuscode=5'

# 结算数据
# settleData = {
#     'rankCode': 0, 'tagCode': 0, 'shippingMethod': 1, 'thirdcode': None,
#     'receiver': '李不帅', 'recvphone': '18529551929', 'provincecode': 19, 'citycode': 202, 'countycode': 1754,
#     'recvaddr': '化龙镇山门大道700号', 'exchangeRate': 1, 'paid': 0, 'rmbAmount': 0, 'cartCodes': '0',
#     'itemPrice': 0, 'itemRmbAmount': 0, 'defectNo': '', 'productcode': '0', 'counts': 0
# }

# 付款码
# https://fenxiao.clim.cn/order/orderlist.do?statuscode=10&startTime=&endTime=&orderCode=&receiver=&phone=18529551929&thirdCode=&pageIndex=&pageSize=

url_orderlist = 'https://fenxiao.clim.cn/order/orderlist.do?statuscode=10&startTime=&endTime=&orderCode=&receiver=&phone=18529551929&thirdCode=&pageIndex=&pageSize='

def getOrder():
    resp = requests.get(url=url_orderlist, headers=headers)
    soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")

    # 查找所有包含 'javascript:showOrder' 的 <a> 标签
    links = soup.find_all('a', href=True)
    for link in links:
        href = link['href']
        # 使用正则表达式提取订单号
        # 确保 href 属性包含 showOrder 调用
        if 'showOrder' in href:
            match = re.search(r"showOrder\('(\w+)'\)", href)
            if match:
                order_number = match.group(1)
                print(f"提取的订单号: {order_number}")



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
    product = None

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
                row_0_td = row_0.find_all('td')

                buttons = row_0.find_all('button')
                button_titles = [button.get('title') for button in buttons]
                print('商品编号:', button_titles)
                
                sku = button_titles[0] if button_titles else None

                brand_category = row_0_td[1].get_text(strip=True)
                image_url = row_0.find('img')['src']
                name = row_0.find('a').get_text(strip=True)
                weight = row_0_td[4].get_text(strip=True)
                distribution_price = row_0_td[5].get_text(strip=True)
                market_price = row_0_td[6].get_text(strip=True)
                listing_time = row_0_td[7].get_text(strip=True)

                product = {
                    'keyword': keyword,
                    'sku': sku,
                    'brand_category': brand_category,
                    'image_url': image_url,
                    'name': name,
                    'distribution_price': distribution_price,
                    'market_price': market_price,
                    'listing_time': listing_time,
                }
    return product

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
    # count = min(float(stock), max_money / float(price))
    count = int(stock)
    param_save_cart = {'typeCode': 0, 'price': 0, 'productCode': 0, 'count': 0}
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
        return param_save_cart
    return None

# 查看购物车
def check_cart(product_code_value, count):
    resp = requests.get(url_cart, headers=headers)
    soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")
    rows = soup.select('tbody tr')

    for row in rows:
        rank_code = row.find('input', {'class': 'rankCode'})['value']
        product_code = row.find_all('td')[2].get_text(strip=True)
        if product_code == product_code_value:
            checkId = row.find('input', {'type': 'checkbox'})['value']
            return checkout(checkId, count)
    return False

# 结算
def checkout(checkId, count):
    print(f'结算商品: {checkId}')
    resp = requests.get(url=f'{url_settle}{checkId}', headers=headers)
    soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")

    rows = soup.select('tbody tr')
    row_0 = rows[0]
    row_0_td = row_0.find_all('td')
    name = row_0_td[4].get_text(strip=True)
    print('name', name)
    
    settleData = {
        'rankCode': 0, 'tagCode': 0, 'shippingMethod': 1, 'thirdcode': None,
        'receiver': '李不帅', 'recvphone': '18529551929', 'provincecode': 19, 'citycode': 202, 'countycode': 1754,
        'recvaddr': '化龙镇山门大道700号', 'exchangeRate': 1, 'paid': 0, 'rmbAmount': 0, 'cartCodes': '0',
        'itemPrice': 0, 'itemRmbAmount': 0, 'defectNo': '', 'productcode': '0', 'counts': 0
    }
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
        # 'counts': soup.find('input', {'name': 'counts'})['value']
        'counts': count
    })

    # table = soup.find('table', {'class': 'table table-striped'})
    # table_html = str(table)
    # print('table_html', table_html)

    # {'rankCode': '68', 'tagCode': '30', 'shippingMethod': '1', 'thirdcode': None, 'receiver': '李不帅', 'recvphone': '18529551929', 'provincecode': 19, 'citycode': 202, 'countycode': 1754, 'recvaddr': '化龙镇山门大道700号', 'exchangeRate': '1', 'paid': '4821.0', 'rmbAmount': '4821.00', 'cartCodes': '70708', 'itemPrice': '1607.0', 'itemRmbAmount': '1607.00', 'defectNo': '', 'productcode': '101877501', 'counts': 3}
    print('settleData', settleData)

    wxpush = PushPlus()

    # 校验总价
    int_price = int(float(settleData['itemPrice']))
    int_total_price = int_price * count
    int_rmb_amount = int(float(settleData['rmbAmount']))
    print('int_total_price', int_total_price)
    print('int_rmb_amount', int_rmb_amount)
    if int_total_price != int_rmb_amount:
        wxpush.sendMsg(name, f'下单失败!单价{int_price},数量{count},计算总价{int_total_price},系统总价{int_rmb_amount}') 
        return False

    
    resp = requests.post(url=url_settle_save, headers=headers, params=settleData)
    print(f'status_code: {resp.status_code}')
    content = resp.content.decode('utf-8')
    print('content:', )
    # return resp.status_code == 200
    data = resp.json()
    
    if data['resultCode'] == 0:
        
        wxpush.sendMsg(name, f'下单 {name},数量{settleData["counts"]},金额{settleData["itemPrice"]}')
        refresh_orders()
        return True
    wxpush.sendMsg(name, f'下单失败!{content}')
    return False


def is_within_time_range(start_hour=7, end_hour=12):
    """判断当前时间是否在指定的时间范围内"""
    now = datetime.now().time()
    start_time = datetime.now().replace(hour=start_hour, minute=0, second=0, microsecond=0).time()
    end_time = datetime.now().replace(hour=end_hour, minute=0, second=0, microsecond=0).time()
    return start_time <= now <= end_time


    
def save_keyword_status(keyword):
    """保存成功处理的关键字到文件中"""
    with open('processed_keywords.txt', 'a') as f:
        f.write(f"{keyword},{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

def load_processed_keywords():
    """加载已成功处理的关键字"""
    try:
        with open('processed_keywords.txt', 'r') as f:
            lines = f.readlines()
            return {line.split(',')[0]: datetime.strptime(line.split(',')[1].strip(), '%Y-%m-%d %H:%M:%S') for line in lines}
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

def process_keyword(self, keyword, intensify = False):

    processed_keywords = load_processed_keywords()
    
    # 如果今天已经处理过这个关键字，则跳过
    today_str = str(datetime.now().date())
    if keyword in processed_keywords:
        last_processed_time = processed_keywords[keyword]
        if datetime.now() - last_processed_time < timedelta(minutes=10):
            print(f"10分钟内已经成功处理过关键字 {keyword}，跳过...")
            return False

    # 处理流程
    product = query_product(keyword)
    print('product', product)
    if product:
        param_save_cart = selectBuyDefect(product['sku'])

        if param_save_cart:
            product_code_value = param_save_cart['productCode']
            count = param_save_cart['count']

            if intensify:
                checkout_result = check_cart(product_code_value, count)
                if checkout_result:
                    print(f"关键字 {keyword} 处理成功")
                    save_keyword_status(keyword)
                    return True
            else:
                wxpush = PushPlus()
                msg = f'库存更新 {product["name"]},\
                            <br />数量 {count}\
                            <br />金额 {product["distribution_price"]}\
                            <br /><img src="{product["image_url"]}" width="200px" height="200px" />'
                wxpush.sendMsg(keyword, msg)
                print('msg', msg)
                print(f"关键字 {keyword} 处理成功")
                save_keyword_status(keyword)
                return True
        
    return False


    
def refresh_orders():
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
    if orders:
        for ord in orders:
            set_orders(ord)
    return orders