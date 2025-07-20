# -*- coding:utf-8 -*-
#!/usr/bin/python

import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import urllib.parse
import threading
import concurrent.futures
from pushplus import PushPlus
import re
from common.orders import set_orders
from common.status import get_global_batch_order_mode, get_global_test_mode
import json


class ProductCheckoutConfig:
    """产品下单配置管理类"""

    # 系统配置
    MAX_MONEY = 35000  # 最大金额限制

    # 登录配置
    LOGIN_USER = {
        'name': '琴琴境内-境内',
        'password': '888888'
    }

    # 批量下单配置
    MAX_PRODUCTS_PER_ORDER = 8  # 每单最多商品种类
    MAX_QUANTITY_PER_ORDER = 30  # 每单最多数量
    MAX_AMOUNT_PER_ORDER = 40000  # 每单最大金额

    # 多轮检测配置
    MAX_DETECTION_ROUNDS = 5  # 最多检测轮数
    ROUND_INTERVAL = 4  # 轮次间隔（秒）
    THREAD_TIMEOUT = 30  # 线程超时时间（秒）
    MAX_CONCURRENT_THREADS = 10  # 最大并发线程数

    # API URL配置
    BASE_URL = 'https://fenxiao.clim.cn'

    # 登录相关URL
    URL_LOGIN = f'{BASE_URL}/login/checkLogin.do'

    # 商品相关URL
    URL_QUERY_PRODUCT = f'{BASE_URL}/shop/products.do'
    # URL_QUERY_PRODUCT_COUNTS = f'{BASE_URL}/home/main.do'
    # https://fenxiao.clim.cn/shop/products.do
    URL_QUERY_PRODUCT_COUNTS = f'{BASE_URL}/shop/products.do'
    URL_SELECT_BUY_PRODUCT = f'{BASE_URL}/shop/selectBuyProduct.do'

    # 购物车相关URL
    URL_SAVE_CART = f'{BASE_URL}/shop/saveCart.do'
    URL_CART = f'{BASE_URL}/shop/cart.do?v=4.0'

    # 结算相关URL
    URL_SETTLE = f'{BASE_URL}/shop/settle.do'
    URL_SETTLE_SAVE = f'{BASE_URL}/shop/settlesave.do?statuscode=5'

    # 订单相关URL
    URL_ORDERLIST = f'{BASE_URL}/order/orderlist.do?statuscode=10&startTime=&endTime=&orderCode=&receiver=&phone=18529551929&thirdCode=&pageIndex=&pageSize='

    # 支付相关URL
    URL_PAY_ALIPAY = f'{BASE_URL}/alipay/topay.do'  # 支付宝支付
    URL_PAY_WECHAT = f'{BASE_URL}/pay/topay.do'     # 微信支付

    # 支付类型配置
    PAY_TYPE_ALIPAY = '1'  # 支付宝
    PAY_TYPE_WECHAT = '2'  # 微信支付（默认）

    # 请求头配置
    HEADERS = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-encoding': 'gzip, deflate, br, zstd',
        'content-type': 'application/x-www-form-urlencoded',
        'cookie': 'JSESSIONID=52E75FA6DCC05C4858625F412666175C',
        'host': 'fenxiao.clim.cn',
        'origin': f'{BASE_URL}',
        'referer': f'{BASE_URL}/shop/products.do',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0.0.0 Safari/537.36'
    }

    # 查询商品参数配置
    PARAM_QUERY_PRODUCT = {
        'keyword': '',
        'recommendTypeCode': 1,
        'sort': 'desc',
        'sortFiled': 'online_time'
    }


class ProductCheckoutState:
    """产品下单状态管理类"""

    def __init__(self):
        # 批量下单状态
        self.batch_cart_items = []  # 批量购物车商品
        self.batch_lock = threading.Lock()  # 线程锁
        self.processed_keywords_batch = {}  # 批量模式下关键词处理记录
        self.batch_round_count = 0  # 当前检测轮次

        # 商品检测状态
        self.last_product_count = {}  # 保存上次查询的总数
        self._last_total_count = None  # 上次总数
        self._last_check_time = None  # 上次检查时间

    def reset_batch_state(self):
        """重置批量状态"""
        with self.batch_lock:
            old_cart_count = len(self.batch_cart_items)
            old_keywords_count = len(self.processed_keywords_batch)

            self.batch_cart_items.clear()
            self.processed_keywords_batch.clear()
            self.batch_round_count = 0

            print(f"🔄 [STATE] 批量状态已重置:")
            print(f"   清空购物车: {old_cart_count} → 0")
            print(f"   清空关键词记录: {old_keywords_count} → 0")
            print(f"   重置轮次计数: → 0")

    def get_batch_cart_items(self):
        """获取批量购物车商品"""
        with self.batch_lock:
            items = self.batch_cart_items.copy()
            print(f"🔍 [STATE] 获取购物车商品: {len(items)} 件")
            for i, item in enumerate(items):
                print(f"   商品{i+1}: {item.get('name', 'Unknown')} (关键词: {item.get('keyword', 'Unknown')})")
            return items

    def add_batch_cart_item(self, item):
        """添加商品到批量购物车"""
        with self.batch_lock:
            old_count = len(self.batch_cart_items)
            self.batch_cart_items.append(item)
            new_count = len(self.batch_cart_items)

            print(f"📦 [STATE] 商品已添加到购物车:")
            print(f"   商品名称: {item.get('name', 'Unknown')}")
            print(f"   关键词: {item.get('keyword', 'Unknown')}")
            print(f"   购物车ID: {item.get('cart_id', 'Unknown')}")
            print(f"   购物车数量: {old_count} → {new_count}")

    def clear_batch_cart(self):
        """清空批量购物车"""
        with self.batch_lock:
            old_count = len(self.batch_cart_items)
            self.batch_cart_items.clear()
            print(f"🧹 [STATE] 批量购物车已清空: {old_count} → 0")


# 全局实例
config = ProductCheckoutConfig()
state = ProductCheckoutState()

def add_to_batch_cart(product_info, cart_result):
    """添加商品到批量购物车"""
    print(f"🔄 [FUNC] add_to_batch_cart 被调用:")
    print(f"   product_info: {product_info}")
    print(f"   cart_result: {cart_result}")

    item = {
        'keyword': product_info['keyword'],
        'product_code': product_info['product_code'],
        'cart_id': cart_result['cart_id'],
        'count': cart_result['count'],
        'price': product_info['price'],
        'name': product_info['name']
    }

    print(f"📦 [FUNC] 准备添加商品到购物车: {item}")

    # 调用状态管理器添加商品
    state.add_batch_cart_item(item)

    # 验证添加结果
    current_items = state.get_batch_cart_items()
    print(f"✅ [FUNC] 添加完成，当前购物车总数: {len(current_items)}")

    # 添加调试信息
    test_mode = get_global_test_mode()
    if test_mode:
        print(f"📦 商品已加入测试购物车: {product_info['name']} (购物车ID: {cart_result['cart_id']})")
    else:
        print(f"📦 商品已加入批量购物车: {product_info['name']} (购物车ID: {cart_result['cart_id']})")

def get_batch_cart_items():
    """获取批量购物车商品"""
    print(f"🔍 [FUNC] get_batch_cart_items 被调用")
    items = state.get_batch_cart_items()
    print(f"🔍 [FUNC] 返回 {len(items)} 件商品")
    return items

def clear_batch_cart():
    """清空批量购物车"""
    state.clear_batch_cart()
    print("🧹 批量购物车已清空")

def reset_batch_round():
    """重置批量检测轮次"""
    state.reset_batch_state()
    print("🔄 批量检测轮次已重置")

def split_cart_into_orders(cart_items):
    """
    将购物车商品按规则分组为多个订单
    规则：每单最多8种款号规格，总数量不超过30个，金额不超过4万元
    """
    if not cart_items:
        return []

    orders = []
    current_order = []
    current_count = 0
    current_amount = 0.0
    current_products = set()  # 当前订单中的款号

    for item in cart_items:
        item_price = float(item['price'])
        item_count = int(item['count'])
        item_total = item_price * item_count
        product_code = item['product_code']

        # 检查是否可以加入当前订单
        can_add = True

        # 规则1: 最多N种不同款号规格
        if product_code not in current_products and len(current_products) >= config.MAX_PRODUCTS_PER_ORDER:
            can_add = False

        # 规则2: 总数量不超过N个
        if current_count + item_count > config.MAX_QUANTITY_PER_ORDER:
            can_add = False

        # 规则3: 金额不超过N元
        if current_amount + item_total > config.MAX_AMOUNT_PER_ORDER:
            can_add = False

        if can_add and current_order:
            # 可以加入当前订单
            current_order.append(item)
            current_count += item_count
            current_amount += item_total
            current_products.add(product_code)
        else:
            # 需要创建新订单
            if current_order:
                orders.append({
                    'items': current_order,
                    'total_count': current_count,
                    'total_amount': current_amount,
                    'product_count': len(current_products)
                })

            # 开始新订单
            current_order = [item]
            current_count = item_count
            current_amount = item_total
            current_products = {product_code}

    # 添加最后一个订单
    if current_order:
        orders.append({
            'items': current_order,
            'total_count': current_count,
            'total_amount': current_amount,
            'product_count': len(current_products)
        })

    print(f"🛒 购物车商品已分组为 {len(orders)} 个订单")
    for i, order in enumerate(orders, 1):
        print(f"   订单{i}: {order['product_count']}种商品, {order['total_count']}件, ¥{order['total_amount']:.2f}")

    return orders

def execute_batch_checkout():
    """执行批量下单"""
    cart_items = get_batch_cart_items()
    if not cart_items:
        print("📦 批量购物车为空，无需下单")
        return

    print(f"🛒 开始批量下单，共 {len(cart_items)} 件商品")

    # 检查是否为测试模式
    test_mode = get_global_test_mode()

    if test_mode:
        # 测试模式：所有商品合并成一个订单
        print("🧪 测试模式：将所有商品合并成一个订单")
        orders = [{
            'items': cart_items,
            'total_count': sum(int(item['count']) for item in cart_items),
            'total_amount': sum(float(item['price']) * int(item['count']) for item in cart_items),
            'product_count': len(cart_items)
        }]
        print(f"🛒 测试订单: {orders[0]['product_count']}种商品, {orders[0]['total_count']}件, ¥{orders[0]['total_amount']:.2f}")
    else:
        # 正常模式：按规则分组订单
        orders = split_cart_into_orders(cart_items)

    if not orders:
        print("❌ 订单分组失败")
        return

    # 执行每个订单
    for i, order in enumerate(orders, 1):
        try:
            print(f"🚀 正在处理第 {i}/{len(orders)} 个订单...")

            # 构建多商品URL
            cart_ids = [item['cart_id'] for item in order['items']]
            checked_params = "&".join([f"checked={cart_id}" for cart_id in cart_ids])
            settle_url = f"https://fenxiao.clim.cn/shop/settle.do?{checked_params}"

            print(f"📋 订单详情: {order['product_count']}种商品, {order['total_count']}件, ¥{order['total_amount']:.2f}")
            print(f"🔗 结算链接: {settle_url}")

            # 执行下单
            checkout_result = submit_batch_order(settle_url, order)

            if checkout_result:
                print(f"✅ 第 {i} 个订单下单成功")

                # 立即获取最新订单并推送（这样可以立即弹窗）
                try:
                    print("🔍 开始立即推送流程...")
                    from service.web import push_order_to_clients
                    from common.orders import get_orders

                    # 获取最新订单
                    latest_orders = get_orders()
                    print(f"🔍 获取到的订单列表: {latest_orders}")

                    if latest_orders:
                        # 推送最新的订单号（真实订单号）
                        for order_code in latest_orders[-1:]:  # 只推送最新的订单
                            print(f"🚀 立即推送真实订单号: {order_code}")
                            push_order_to_clients(order_code)
                    else:
                        print("⚠️ 获取到的订单列表为空，无法立即推送")

                except Exception as e:
                    print(f"❌ 推送订单失败: {e}")
                    import traceback
                    traceback.print_exc()

            else:
                print(f"❌ 第 {i} 个订单下单失败")

        except Exception as e:
            print(f"❌ 处理第 {i} 个订单时出错: {e}")

    # 清空批量购物车
    clear_batch_cart()
    print("🎉 批量下单处理完成")

def submit_batch_order(settle_url, order):
    """提交批量订单"""
    try:
        print(f"💳 正在提交批量订单: {settle_url}")

        # 1. 访问结算页面获取表单数据
        resp = requests.get(url=settle_url, headers=headers)
        if resp.status_code != 200:
            print(f"❌ 访问结算页面失败: {resp.status_code}")
            return False

        soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")

        # 2. 构建批量订单数据
        settle_data = {
            'rankCode': '68',
            'tagCode': '30',
            'shippingMethod': '1',
            'thirdcode': '',
            'payType': '2',  # 1=支付宝, 2=微信
            'receiver': '李小峰',
            'recvphone': '18529551929',
            'provincecode': '19',
            'citycode': '202',
            'countycode': '1754',
            'recvaddr': '化龙镇山门大道700号',
            'zip': '',
            'idno': '',
            'exchangeRate': '1',
            'description': ''
        }

        # 3. 从页面获取基础数据（如果存在）
        try:
            if soup.find('input', {'name': 'rankCode'}):
                settle_data['rankCode'] = soup.find('input', {'name': 'rankCode'})['value']
            if soup.find('input', {'name': 'tagCode'}):
                settle_data['tagCode'] = soup.find('input', {'name': 'tagCode'})['value']
            if soup.find('input', {'name': 'shippingMethod'}):
                settle_data['shippingMethod'] = soup.find('input', {'name': 'shippingMethod'})['value']
            if soup.find('input', {'name': 'exchangeRate'}):
                settle_data['exchangeRate'] = soup.find('input', {'name': 'exchangeRate'})['value']
        except Exception as e:
            print(f"⚠️ 获取页面数据时出错: {e}，使用默认值")

        # 4. 构建多商品数据（按照表单格式）
        cart_codes = []
        product_codes = []
        counts = []

        for item in order['items']:
            cart_codes.append(item['cart_id'])
            product_codes.append(item['product_code'])
            counts.append(str(item['count']))

        # 构建表单数据（支持多个商品）
        form_data = []
        for i, item in enumerate(order['items']):
            form_data.extend([
                ('cartCodes', item['cart_id']),
                ('defectNo', ''),
                ('productcode', item['product_code']),
                ('counts', str(item['count']))
            ])

        # 添加基础数据到表单
        for key, value in settle_data.items():
            form_data.append((key, value))

        print(f"📋 订单数据: {dict(form_data)}")

        # 5. 提交订单
        resp = requests.post(url=config.URL_SETTLE_SAVE, headers=headers, data=form_data)

        print(f"📤 提交状态码: {resp.status_code}")

        if resp.status_code == 200:
            try:
                result = resp.json()
                print(f"📋 提交结果: {result}")

                if result.get('resultCode') == 0:
                    order_code = result.get('data', {}).get('code', 'Unknown')
                    total_amount = result.get('data', {}).get('paid', 0)

                    print(f"✅ 批量订单提交成功!")
                    print(f"📦 订单号: {order_code}")
                    print(f"💰 订单金额: ¥{total_amount}")

                    # 发送通知
                    try:
                        wxpush = PushPlus()
                        product_names = [item['name'] for item in order['items']]
                        msg = f'批量下单成功!\n订单号: {order_code}\n商品: {", ".join(product_names)}\n金额: ¥{total_amount}'
                        wxpush.sendMsg("批量下单", msg)
                    except Exception as e:
                        print(f"⚠️ 发送通知失败: {e}")

                    # 刷新订单列表
                    try:
                        refresh_orders()
                    except Exception as e:
                        print(f"⚠️ 刷新订单列表失败: {e}")

                    return True
                else:
                    error_msg = result.get('errorMsg', '未知错误')
                    print(f"❌ 订单提交失败: {error_msg}")
                    return False

            except json.JSONDecodeError:
                print(f"❌ 响应解析失败: {resp.text}")
                return False
        else:
            print(f"❌ 请求失败: {resp.status_code}")
            return False

    except Exception as e:
        print(f"❌ 提交批量订单时出错: {e}")
        return False

# 注意：所有URL和配置已移至 ProductCheckoutConfig 类

# 全局headers实例（动态更新cookie）
headers = config.HEADERS.copy()

def getOrder():
    resp = requests.get(url=config.URL_ORDERLIST, headers=headers)
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
    response = requests.post(url=config.URL_LOGIN, data=config.LOGIN_USER)
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

    query_params = config.PARAM_QUERY_PRODUCT.copy()
    query_params['keyword'] = keyword
    headers['cookie'] = load_cookie()
    resp = requests.post(url=config.URL_QUERY_PRODUCT, headers=headers, params=query_params)
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
    resp = requests.get(url=f'{config.URL_SELECT_BUY_PRODUCT}?skc={sku}', headers=headers)
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

    resp = requests.post(url=config.URL_SAVE_CART, headers=headers, params=param_save_cart)
    print(f'status_code: {resp.status_code}')
    print('content:', resp.content.decode('utf-8'))
    if resp.status_code == 200:
        print('加入购物车成功')

        # 获取购物车ID（需要查询购物车获取最新的cart_id）
        try:
            cart_resp = requests.get(config.URL_CART, headers=headers)
            if cart_resp.status_code == 200:
                cart_soup = BeautifulSoup(cart_resp.content, "html.parser", from_encoding="utf-8")
                rows = cart_soup.select('tbody tr')

                # 查找刚添加的商品
                for row in rows:
                    row_product_code = row.find_all('td')[2].get_text(strip=True)
                    if row_product_code == product_code:
                        cart_id = row.find('input', {'type': 'checkbox'})['value']
                        return {
                            'cart_id': cart_id,
                            'product_code': product_code,
                            'productCode': product_code,  # 兼容旧的键名
                            'count': count,
                            'price': price
                        }
        except Exception as e:
            print(f"获取购物车ID失败: {e}")

        # 如果获取cart_id失败，返回基本信息
        return {
            'cart_id': None,
            'product_code': product_code,
            'productCode': product_code,  # 兼容旧的键名
            'count': count,
            'price': price
        }
    return None

# 查看购物车
def check_cart(product_code_value, count, payType='2'):
    """
    检查购物车并下单
    :param product_code_value: 商品代码
    :param count: 数量
    :param payType: 支付类型 ('1'=支付宝, '2'=微信支付)
    """
    resp = requests.get(config.URL_CART, headers=headers)
    soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")
    rows = soup.select('tbody tr')

    for row in rows:
        # rank_code = row.find('input', {'class': 'rankCode'})['value']  # 暂时不需要使用
        product_code = row.find_all('td')[2].get_text(strip=True)
        if product_code == product_code_value:
            checkId = row.find('input', {'type': 'checkbox'})['value']
            return checkout(checkId, count, payType)
    return False

# 结算
def checkout(checkId, count, payType='2'):
    """
    结算下单
    :param checkId: 购物车ID
    :param count: 数量
    :param payType: 支付类型 ('1'=支付宝, '2'=微信支付)
    """
    print(f'结算商品: {checkId}, 支付类型: {payType}')
    resp = requests.get(url=f'{config.URL_SETTLE}?checked={checkId}', headers=headers)
    soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")

    rows = soup.select('tbody tr')
    row_0 = rows[0]
    row_0_td = row_0.find_all('td')
    name = row_0_td[4].get_text(strip=True)
    print('name', name)

    settleData = {
        'rankCode': 0, 'tagCode': 0, 'shippingMethod': 1, 'thirdcode': '',
        'payType': payType,  # 添加支付类型参数
        'receiver': '李小峰', 'recvphone': '18529551929', 'provincecode': 19, 'citycode': 202, 'countycode': 1754,
        'recvaddr': '化龙镇山门大道700号', 'zip': '', 'idno': '', 'exchangeRate': 1,
        'cartCodes': checkId, 'defectNo': '', 'productcode': '0', 'counts': count, 'description': ''
    }
    # 获取结算数据
    try:
        settleData.update({
            'rankCode': soup.find('input', {'name': 'rankCode'})['value'],
            'tagCode': soup.find('input', {'name': 'tagCode'})['value'],
            'shippingMethod': soup.find('input', {'name': 'shippingMethod'})['value'],
            'thirdcode': soup.find('input', {'name': 'thirdcode'}).get('value', ''),
            'exchangeRate': soup.find('input', {'name': 'exchangeRate'})['value'],
            'productcode': soup.find('input', {'name': 'productcode'})['value'],
        })

        # 保持原有的cartCodes和counts
        settleData['cartCodes'] = checkId
        settleData['counts'] = count

    except Exception as e:
        print(f"获取页面数据时出错: {e}，使用默认值")
        # 使用默认值
        settleData.update({
            'rankCode': '68',
            'tagCode': '30',
            'shippingMethod': '1',
            'thirdcode': '',
            'exchangeRate': '1',
            'productcode': '',
        })

    # table = soup.find('table', {'class': 'table table-striped'})
    # table_html = str(table)
    # print('table_html', table_html)

    # {'rankCode': '68', 'tagCode': '30', 'shippingMethod': '1', 'thirdcode': None, 'receiver': '李不帅', 'recvphone': '18529551929', 'provincecode': 19, 'citycode': 202, 'countycode': 1754, 'recvaddr': '化龙镇山门大道700号', 'exchangeRate': '1', 'paid': '4821.0', 'rmbAmount': '4821.00', 'cartCodes': '70708', 'itemPrice': '1607.0', 'itemRmbAmount': '1607.00', 'defectNo': '', 'productcode': '101877501', 'counts': 3}
    print('settleData', settleData)

    wxpush = PushPlus()

    # 提交订单（使用data而不是params，与批量下单保持一致）
    resp = requests.post(url=config.URL_SETTLE_SAVE, headers=headers, data=settleData)
    print(f'📤 提交状态码: {resp.status_code}')

    if resp.status_code == 200:
        try:
            result = resp.json()
            print(f"📋 提交结果: {result}")

            if result.get('resultCode') == 0:
                order_code = result.get('data', {}).get('code', 'Unknown')
                total_amount = result.get('data', {}).get('paid', 0)

                print(f"✅ 单独下单成功!")
                print(f"📦 订单号: {order_code}")
                print(f"💰 订单金额: ¥{total_amount}")
                print(f"💳 支付类型: {'支付宝' if payType == '1' else '微信支付'}")

                # 发送通知
                try:
                    wxpush.sendMsg(name, f'下单成功!\n订单号: {order_code}\n商品: {name}\n数量: {count}\n金额: ¥{total_amount}\n支付: {"支付宝" if payType == "1" else "微信支付"}')
                except Exception as e:
                    print(f"⚠️ 发送通知失败: {e}")

                # 刷新订单列表
                try:
                    refresh_orders()
                except Exception as e:
                    print(f"⚠️ 刷新订单列表失败: {e}")

                return True
            else:
                error_msg = result.get('errorMsg', '未知错误')
                print(f"❌ 订单提交失败: {error_msg}")
                wxpush.sendMsg(name, f'下单失败! {error_msg}')
                return False

        except json.JSONDecodeError:
            print(f"❌ 响应解析失败: {resp.text}")
            wxpush.sendMsg(name, f'下单失败! 响应解析失败')
            return False
    else:
        print(f"❌ 请求失败: {resp.status_code}")
        wxpush.sendMsg(name, f'下单失败! HTTP {resp.status_code}')
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

def process_keyword(keyword):
    # 先检查是否需要查询商品
    if not should_query_products(keyword):
        return False

    # 获取自动下单状态
    from common.status import get_global_auto_order_status
    auto_order_enabled = get_global_auto_order_status()

    # 处理流程
    product = query_product(keyword)
    print('product', product)
    if product:
        param_save_cart = selectBuyDefect(product['sku'])

        if param_save_cart:
            # 获取商品代码（兼容不同的键名）
            product_code_value = param_save_cart.get('productCode') or param_save_cart.get('product_code')
            count = param_save_cart.get('count', 1)

            if not product_code_value:
                print(f"❌ 关键词 {keyword} 获取商品代码失败，param_save_cart: {param_save_cart}")
                return False

            print(f"📦 关键词 {keyword} 获取到商品代码: {product_code_value}, 数量: {count}")

            if auto_order_enabled:
                # 自动下单模式（默认使用微信支付）
                checkout_result = check_cart(product_code_value, count, config.PAY_TYPE_WECHAT)
                if checkout_result:
                    print(f"关键字 {keyword} 自动下单成功")
                    save_keyword_status(keyword)

                    # 立即推送订单到Web界面
                    try:
                        from service.web import push_order_to_clients
                        from common.orders import get_orders

                        # 获取最新订单并推送
                        latest_orders = get_orders()
                        if latest_orders:
                            for order_code in latest_orders[-1:]:  # 只推送最新的订单
                                push_order_to_clients(order_code)
                    except Exception as e:
                        print(f"推送订单失败: {e}")

                    return True
            else:
                # 通知模式
                wxpush = PushPlus()
                msg = f'库存更新 {product["name"]},\
                            <br />数量 {count}\
                            <br />金额 {product["distribution_price"]}\
                            <br /><img src="{product["image_url"]}" width="200px" height="200px" />'
                wxpush.sendMsg(keyword, msg)
                print('msg', msg)
                print(f"关键字 {keyword} 通知发送成功")
                save_keyword_status(keyword)
                return True

    return False


    
def refresh_orders():
    print('getOrder')
    resp = requests.get(url=config.URL_ORDERLIST, headers=headers)
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

# 添加查询商品总数的函数
def query_product_count():
    """查询商品总数"""
    print('query_product_count')
    
    try:
        headers['cookie'] = load_cookie()
        resp = requests.get(url=config.URL_QUERY_PRODUCT_COUNTS, headers=headers, timeout=10)
        print(f'status_code: {resp.status_code}')
        
        if 'login.do' in resp.url:
            do_login()
            return query_product_count()
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")
            message_div = soup.find('div', class_='message')
            # 查找包含总数的div
            if message_div:
                total_records = message_div.find('i', class_='blue').text
                print(f'商品总数: {total_records}')
                return int(total_records)
        
            print("⚠️ 未找到商品总数信息")
            return None
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 网络请求失败: {e}")
        return None
    except Exception as e:
        print(f"❌ 查询商品总数时出错: {e}")
        return None

def should_query_products(keyword):
    """判断是否需要查询具体商品"""
    current_count = query_product_count()

    if current_count is None:
        return True  # 查询失败，保险起见还是查询

    # 获取上次的总数
    last_count = state.last_product_count.get(keyword, 0)

    # 如果总数发生变化，需要查询
    if current_count != last_count:
        state.last_product_count[keyword] = current_count
        print(f'商品总数变化: {last_count} -> {current_count}，需要查询商品')
        return True

    print(f'商品总数未变化: {current_count}，跳过查询')
    return False

def save_count_cache(keyword, count):
    """保存总数缓存到文件"""
    cache_data = {
        'count': count,
        'timestamp': datetime.now().isoformat()
    }
    with open(f'cache_{keyword}_count.json', 'w') as f:
        json.dump(cache_data, f)

def load_count_cache(keyword):
    """加载总数缓存"""
    try:
        with open(f'cache_{keyword}_count.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def should_check_products():
    """检查是否需要查询商品（全局级别）"""
    current_count = query_product_count()
    current_time = datetime.now()

    if current_count is None:
        return True  # 查询失败，保险起见还是查询

    # 记录刷新次数（每次调用都算一次刷新）
    try:
        from common.status import increment_refresh_count
        increment_refresh_count()
    except Exception as e:
        print(f"⚠️ 记录刷新次数失败: {e}")

    # 如果总数发生变化，需要查询
    if state._last_total_count != current_count:
        print(f'📈 商品总数变化: {state._last_total_count} -> {current_count}，需要查询商品')
        state._last_total_count = current_count
        state._last_check_time = current_time
        return True

    print(f'📊 商品总数未变化: {current_count}，跳过查询')
    return False

def process_keyword_direct(keyword):
    """直接处理关键词，支持单独建单和统一建单模式"""

    # 获取建单模式
    batch_mode = get_global_batch_order_mode()

    if batch_mode:
        # 统一建单模式：支持多轮检测
        with state.batch_lock:
            # 检查是否应该继续检测这个关键词
            if keyword in state.processed_keywords_batch:
                keyword_info = state.processed_keywords_batch[keyword]
                # 如果已经检测了5轮，跳过
                if keyword_info['count'] >= config.MAX_DETECTION_ROUNDS:
                    print(f"批量模式下关键字 {keyword} 已检测{config.MAX_DETECTION_ROUNDS}轮，停止检测")
                    return False
            else:
                # 初始化关键词记录
                state.processed_keywords_batch[keyword] = {'count': 0, 'last_stock': 0}
    else:
        # 单独建单模式：支持多轮检测
        with state.batch_lock:
            # 检查是否应该继续检测这个关键词
            if keyword in state.processed_keywords_batch:
                keyword_info = state.processed_keywords_batch[keyword]
                # 如果已经检测了5轮，跳过
                if keyword_info['count'] >= config.MAX_DETECTION_ROUNDS:
                    print(f"单独建单模式下关键字 {keyword} 已检测{config.MAX_DETECTION_ROUNDS}轮，停止检测")
                    return False
            else:
                # 初始化关键词记录
                state.processed_keywords_batch[keyword] = {'count': 0, 'last_stock': 0}
    
    # 获取自动下单状态
    from common.status import get_global_auto_order_status
    auto_order_enabled = get_global_auto_order_status()

    # 处理流程
    product = query_product(keyword)
    print('product', product)
    print('auto_order_enabled', auto_order_enabled)
    if product:
        # 检查是否需要处理（自动下单模式或测试模式）
        test_mode = get_global_test_mode()
        print(f"🔍 [PROCESS] 模式检查: auto_order_enabled={auto_order_enabled}, test_mode={test_mode}, batch_mode={batch_mode}")

        if auto_order_enabled or test_mode:
            # 只有在自动下单或测试模式下才调用 selectBuyDefect
            param_save_cart = selectBuyDefect(product['sku'])

            if param_save_cart:
                # 获取商品代码（兼容不同的键名）
                product_code_value = param_save_cart.get('productCode') or param_save_cart.get('product_code')
                count = param_save_cart.get('count', 1)

                if not product_code_value:
                    print(f"❌ 关键词 {keyword} 获取商品代码失败，param_save_cart: {param_save_cart}")
                    return False

                print(f"📦 关键词 {keyword} 获取到商品代码: {product_code_value}, 数量: {count}")
                # 自动下单模式或测试模式
                if batch_mode or test_mode:
                    # 统一建单模式或测试模式：加入购物车
                    print(f"🔄 [PROCESS] 关键词 {keyword} 进入购物车流程 (batch_mode={batch_mode}, test_mode={test_mode})")

                    cart_result = selectBuyDefect(product['sku'])
                    print(f"🔄 [PROCESS] selectBuyDefect 结果: {cart_result}")

                    if cart_result:
                        product_info = {
                            'keyword': keyword,
                            'product_code': product_code_value,
                            'price': product['distribution_price'],
                            'distribution_price': product['distribution_price'],  # 添加这个字段
                            'name': product['name'],
                            'image_url': product.get('image_url', ''),  # 添加图片字段
                            'market_price': product.get('market_price', ''),
                            'brand_category': product.get('brand_category', '')
                        }
                        print(f"🔄 [PROCESS] 准备调用 add_to_batch_cart")
                        add_to_batch_cart(product_info, cart_result)

                        if test_mode:
                            print(f"✅ [PROCESS] 关键字 {keyword} 商品已加入测试购物车")
                        else:
                            print(f"✅ [PROCESS] 关键字 {keyword} 商品已加入批量购物车")

                        # 显示商品详细信息
                        # print(f"📦 商品信息:")
                        # print(f"   名称: {product_info['name']}")
                        # print(f"   价格: {product_info.get('price', product_info.get('distribution_price', '未知'))}")
                        # print(f"   图片: {product_info.get('image_url', '无图片')}")
                        # print(f"   库存: {count}")
                        # print(f"   购物车ID: {cart_result['cart_id']}")

                        # 发送带图片的HTML日志到Web界面
                        image_url = product_info.get('image_url', '')
                        if image_url:
                            html_msg = f'''📦 商品详情: {product_info['name']}
                                            💰 价格: ¥{product_info.get('price', '未知')}
                                            📦 库存: {count}
                                            🛒 购物车ID: {cart_result['cart_id']}
                                            <br><img src="{image_url}" style="max-width:200px;max-height:200px;border-radius:8px;" />'''
                            print(html_msg)  # 这会通过日志SSE推送到Web界面
                    else:
                        print(f"❌ [PROCESS] 关键词 {keyword} selectBuyDefect 失败")

                        # 更新批量模式检测记录
                        if batch_mode or test_mode:
                            with state.batch_lock:
                                if keyword in state.processed_keywords_batch:
                                    state.processed_keywords_batch[keyword]['count'] += 1
                                    state.processed_keywords_batch[keyword]['last_stock'] = count

                        return True
                else:
                    # 单独建单模式：立即下单（默认使用微信支付）
                    checkout_result = check_cart(product_code_value, count, config.PAY_TYPE_WECHAT)
                    if checkout_result:
                        print(f"关键字 {keyword} 自动下单成功")

                        # 更新单独建单模式检测记录
                        batch_mode = get_global_batch_order_mode()
                        if not batch_mode:  # 单独建单模式
                            with state.batch_lock:
                                if keyword in state.processed_keywords_batch:
                                    state.processed_keywords_batch[keyword]['count'] += 1
                                    state.processed_keywords_batch[keyword]['last_stock'] = count

                        # 立即推送订单到Web界面
                        try:
                            from service.web import push_order_to_clients
                            from common.orders import get_orders

                            # 获取最新订单并推送
                            latest_orders = get_orders()
                            if latest_orders:
                                for order_code in latest_orders[-1:]:  # 只推送最新的订单
                                    push_order_to_clients(order_code)
                        except Exception as e:
                            print(f"推送订单失败: {e}")

                        return True
        else:
            # 通知模式：只发送通知，不加购物车，不下单
            print(f"📢 [PROCESS] 关键词 {keyword} 进入通知模式（只发送库存通知）")
            wxpush = PushPlus()
            msg = f'库存更新 {product["name"]},\
                        <br />金额 {product["distribution_price"]}\
                        <br /><img src="{product["image_url"]}" width="200px" height="200px" />'
            wxpush.sendMsg(keyword, msg)
            print('msg', msg)
            print(f"关键字 {keyword} 通知发送成功")
            save_keyword_status(keyword)
            return True

    # 如果没有找到有货商品，也要更新检测记录（批量模式和单独建单模式都需要）
    batch_mode = get_global_batch_order_mode()
    test_mode = get_global_test_mode()

    if batch_mode or (not batch_mode and not test_mode):  # 批量模式或单独建单模式
        with state.batch_lock:
            if keyword in state.processed_keywords_batch:
                state.processed_keywords_batch[keyword]['count'] += 1
                # 如果连续检测没有库存变化，标记为无需继续检测
                if state.processed_keywords_batch[keyword]['last_stock'] == 0:
                    state.processed_keywords_batch[keyword]['count'] = config.MAX_DETECTION_ROUNDS  # 直接标记为完成

    return False
