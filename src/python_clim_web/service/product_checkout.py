# -*- coding:utf-8 -*-
#!/usr/bin/python

import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import urllib.parse
import threading
import concurrent.futures
import os
from ..pushplus import PushPlus
from ..config import config  # 引入新的配置文件
import re
from ..common.orders import set_orders
from ..common.status import get_global_batch_order_mode, get_global_test_mode
import json
from ..common.logger import get_logger

logger = get_logger()

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

            logger.info(f"🔄 [STATE] 批量状态已重置:")
            logger.info(f"   清空购物车: {old_cart_count} → 0")
            logger.info(f"   清空关键词记录: {old_keywords_count} → 0")
            logger.info(f"   重置轮次计数: → 0")

    def get_batch_cart_items(self):
        with self.batch_lock:
            items = self.batch_cart_items.copy()
            logger.info(f"🔍 [STATE] 获取购物车商品: {len(items)} 件")
            for i, item in enumerate(items):
                logger.info(f"   商品{i+1}: {item.get('name', 'Unknown')} (关键词: {item.get('keyword', 'Unknown')})")
            return items

    def add_batch_cart_item(self, item):
        with self.batch_lock:
            old_count = len(self.batch_cart_items)
            self.batch_cart_items.append(item)
            new_count = len(self.batch_cart_items)

            logger.info(f"📦 [STATE] 商品已添加到购物车:")
            logger.info(f"   商品名称: {item.get('name', 'Unknown')}")
            logger.info(f"   关键词: {item.get('keyword', 'Unknown')}")
            logger.info(f"   购物车ID: {item.get('cart_id', 'Unknown')}")
            logger.info(f"   购物车数量: {old_count} → {new_count}")

    def clear_batch_cart(self):
        with self.batch_lock:
            old_count = len(self.batch_cart_items)
            self.batch_cart_items.clear()
            logger.info(f"🧹 [STATE] 批量购物车已清空: {old_count} → 0")


state = ProductCheckoutState()

def add_to_batch_cart(product_info, cart_result):
    """添加商品到批量购物车"""
    logger.info(f"🔄 [FUNC] add_to_batch_cart 被调用:")
    logger.debug(f"   product_info: {product_info}")
    logger.debug(f"   cart_result: {cart_result}")

    item = {
        'keyword': product_info['keyword'],
        'product_code': product_info['product_code'],
        'cart_id': cart_result['cart_id'],
        'count': cart_result['count'],
        'price': product_info['price'],
        'name': product_info['name']
    }

    logger.info(f"📦 [FUNC] 准备添加商品到购物车: {item}")

    # 调用状态管理器添加商品
    state.add_batch_cart_item(item)

    # 验证添加结果
    current_items = state.get_batch_cart_items()
    logger.info(f"✅ [FUNC] 添加完成，当前购物车总数: {len(current_items)}")

    # 添加调试信息
    test_mode = get_global_test_mode()
    if test_mode:
        logger.info(f"📦 商品已加入测试购物车: {product_info['name']} (购物车ID: {cart_result['cart_id']})")
    else:
        logger.info(f"📦 商品已加入批量购物车: {product_info['name']} (购物车ID: {cart_result['cart_id']})")

def get_batch_cart_items():
    """获取批量购物车商品"""
    logger.info(f"🔍 [FUNC] get_batch_cart_items 被调用")
    items = state.get_batch_cart_items()
    logger.info(f"🔍 [FUNC] 返回 {len(items)} 件商品")
    return items

def clear_batch_cart():
    """清空批量购物车"""
    state.clear_batch_cart()
    logger.info("🧹 批量购物车已清空")

def reset_batch_round():
    """重置批量检测轮次"""
    state.reset_batch_state()
    logger.info("🔄 批量检测轮次已重置")



def execute_batch_checkout():
    """执行批量下单"""
    from ..config import config
    cart_items = get_batch_cart_items()
    if not cart_items:
        logger.info("📦 批量购物车为空，无需下单")
        return

    logger.info(f"🛒 开始批量下单，共 {len(cart_items)} 种商品。将根据限制进行拆单...")

    # --- 订单拆分逻辑 ---
    orders_to_submit = []
    current_order_items = []
    current_quantity = 0
    current_amount = 0

    # 复制一份可修改的商品列表
    splittable_items = [item.copy() for item in cart_items]

    for item in splittable_items:
        item['remaining_qty'] = int(item.get('count', 0))

    for item in splittable_items:
        item_price = float(item.get('price', 0))
        
        while item['remaining_qty'] > 0:
            # 如果当前订单为空，直接计算能放多少
            if not current_order_items:
                qty_to_add = min(item['remaining_qty'], config.MAX_QUANTITY_PER_ORDER)
                if item_price > 0:
                    qty_to_add = min(qty_to_add, int(config.MAX_AMOUNT_PER_ORDER / item_price))
            else:
                # 计算当前订单剩余容量
                space_by_qty = config.MAX_QUANTITY_PER_ORDER - current_quantity
                space_by_amt = (config.MAX_AMOUNT_PER_ORDER - current_amount)
                
                qty_to_add = min(item['remaining_qty'], space_by_qty)
                if item_price > 0:
                    qty_to_add = min(qty_to_add, int(space_by_amt / item_price))

            if qty_to_add <= 0:
                # 当前订单已满，提交并开启新订单
                if current_order_items:
                    orders_to_submit.append({'items': current_order_items, 'total_count': current_quantity, 'total_amount': current_amount, 'product_count': len(current_order_items)})
                current_order_items, current_quantity, current_amount = [], 0, 0
                continue # 重新循环，在新订单中添加

            # 将计算出的数量添加到当前订单
            order_item = item.copy()
            order_item['count'] = qty_to_add
            current_order_items.append(order_item)
            
            current_quantity += qty_to_add
            current_amount += qty_to_add * item_price
            item['remaining_qty'] -= qty_to_add

    # 添加最后一个未提交的订单
    if current_order_items:
        orders_to_submit.append({'items': current_order_items, 'total_count': current_quantity, 'total_amount': current_amount, 'product_count': len(current_order_items)})

    logger.info(f"📦 购物车商品已拆分为 {len(orders_to_submit)} 个子订单。")

    # --- 提交所有拆分好的订单 ---
    for i, order in enumerate(orders_to_submit, 1):
        try:
            logger.info(f"🚀 开始处理子订单 {i}/{len(orders_to_submit)}...")
            logger.info(f"   订单详情: {order['product_count']}种商品, {order['total_count']}件, ¥{order['total_amount']:.2f}")

            cart_ids = [item['cart_id'] for item in order['items']]
            checked_params = "&".join([f"checked={cart_id}" for cart_id in cart_ids])
            settle_url = f"{config.URL_SETTLE}?{checked_params}"

            logger.info(f"🔗 结算链接: {settle_url}")

            order_code = submit_batch_order(settle_url, order)

            if order_code:
                logger.info(f"✅ 子订单 {i} 下单成功，订单号: {order_code}")
                try:
                    from .web import push_order_to_clients
                    push_order_to_clients(order_code)
                    logger.info(f"🚀 订单号推送成功: {order_code}")
                except Exception as e:
                    logger.error(f"❌ 推送订单失败: {e}", exc_info=True)
            else:
                logger.error(f"❌ 子订单 {i} 下单失败")
        except Exception as e:
            logger.error(f"❌ 处理子订单 {i} 时出错: {e}", exc_info=True)

    # 清空批量购物车
    clear_batch_cart()
    logger.info("🎉 批量下单处理完成")

def submit_batch_order(settle_url, order):
    """提交批量订单"""
    try:
        logger.info(f"💳 正在提交批量订单: {settle_url}")

        # 1. 访问结算页面获取表单数据
        resp = requests.get(url=settle_url, headers=headers)
        if resp.status_code != 200:
            logger.error(f"❌ 访问结算页面失败: {resp.status_code}")
            return False

        soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")

        # 2. 构建批量订单数据
        settle_data = {
            'rankCode': '68',
            'tagCode': '30',
            'shippingMethod': '1',
            'thirdcode': '',
            'payType': config.PAY_TYPE_WECHAT,
            'idno': '',
            'exchangeRate': '1',
            'description': ''
        }

        # 3. 从页面获取基础数据（如果存在）
        try:
            if soup.find('input', {'name': 'rankCode'}):
                # 合并收货人信息
                settle_data['rankCode'] = soup.find('input', {'name': 'rankCode'})['value']
            if soup.find('input', {'name': 'tagCode'}):
                settle_data['tagCode'] = soup.find('input', {'name': 'tagCode'})['value']
            if soup.find('input', {'name': 'shippingMethod'}):
                settle_data['shippingMethod'] = soup.find('input', {'name': 'shippingMethod'})['value']
            if soup.find('input', {'name': 'exchangeRate'}):
                settle_data['exchangeRate'] = soup.find('input', {'name': 'exchangeRate'})['value']
            
            # 合并收货人信息
            settle_data.update(config.RECEIVER_INFO)
        except Exception as e:
            logger.warning(f"⚠️ 获取页面数据时出错: {e}，使用默认值")

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

        logger.debug(f"📋 订单数据: {dict(form_data)}")

        # 5. 提交订单
        resp = requests.post(url=config.URL_SETTLE_SAVE, headers=headers, data=form_data)

        logger.debug(f"📤 提交状态码: {resp.status_code}")

        if resp.status_code == 200:
            try:
                result = resp.json()
                logger.debug(f"📋 提交结果: {result}")

                if result.get('resultCode') == 0:
                    order_code = result.get('data', {}).get('code', 'Unknown')
                    total_amount = result.get('data', {}).get('paid', 0)

                    logger.info(f"✅ 批量订单提交成功!")
                    logger.info(f"📦 订单号: {order_code}")
                    logger.info(f"💰 订单金额: ¥{total_amount}")

                    # 发送通知
                    try:
                        wxpush = PushPlus()
                        product_names = [item['name'] for item in order['items']]
                        msg = f'批量下单成功!\n订单号: {order_code}\n商品: {", ".join(product_names)}\n金额: ¥{total_amount}'
                        wxpush.sendMsg("批量下单", msg)
                    except Exception as e:
                        logger.warning(f"⚠️ 发送通知失败: {e}")

                    # 刷新订单列表
                    try:
                        refresh_orders()
                    except Exception as e:
                        logger.warning(f"⚠️ 刷新订单列表失败: {e}")

                    return order_code  # 返回订单号而不是True
                else:
                    error_msg = result.get('errorMsg', '未知错误')
                    logger.error(f"❌ 订单提交失败: {error_msg}")
                    return False

            except json.JSONDecodeError:
                logger.error(f"❌ 响应解析失败: {resp.text}")
                return False
        else:
            logger.error(f"❌ 请求失败: {resp.status_code}")
            return False

    except Exception as e:
        logger.error(f"❌ 提交批量订单时出错: {e}", exc_info=True)
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
        if 'showOrder' in href:
            match = re.search(r"showOrder\('(\w+)'\)", href)
            if match:
                order_number = match.group(1)
                logger.info(f"提取的订单号: {order_number}")



# 登录
def do_login():
    logger.info('do_login')
    response = requests.post(url=config.URL_LOGIN, data=config.LOGIN_USER)
    logger.debug(response.status_code)
    data = response.json()
    logger.debug(data)
    if data['result'] is True:
        cookies = requests.utils.dict_from_cookiejar(response.cookies)
        cookiesValue = ''
        for key in cookies.keys():
            cookiesValue += key + '=' + cookies.get(key) + ';'
        logger.debug(cookiesValue)
        save_cookie(cookiesValue)
        logger.debug(f'loadcookie: {load_cookie()}')
        headers['cookie'] = cookiesValue
        logger.info('-' * 50)

# 查询商品信息
def query_product(keyword):
    logger.info(f'query_product: {keyword}')

    sku = None
    product = None

    query_params = config.PARAM_QUERY_PRODUCT.copy()
    query_params['keyword'] = keyword
    headers['cookie'] = load_cookie()
    resp = requests.post(url=config.URL_QUERY_PRODUCT, headers=headers, params=query_params)
    logger.debug(f'status_code: {resp.status_code}')
    logger.debug(f'url: {resp.url}')
    if 'login.do' in resp.url:
        do_login()
        return query_product(keyword)
    else:
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")

            # 从页面统计信息获取真正的商品总数
            message_div = soup.find('div', class_='message')
            total_count = 0
            if message_div:
                blue_element = message_div.find('i', class_='blue')
                if blue_element:
                    try:
                        total_count = int(blue_element.get_text(strip=True))
                    except ValueError:
                        total_count = 0

            rows = soup.select('tbody tr')
            logger.info(f'商品列表 [{keyword}]: 共{total_count}条记录')

            if rows:
                # 只显示有效商品，不显示无效行信息
                valid_products = []
                for row in rows:
                    try:
                        # 检查是否有SKU input（真正的商品行必须有这个）
                        sku_input = row.find('input', {'name': 'skc'})
                        name_element = row.find('a')

                        if sku_input and name_element:
                            # 这是有效的商品行
                            name = name_element.get_text(strip=True)
                            sku_value = sku_input['value']

                            # 获取图片URL
                            image_element = row.find('img')
                            image_url = image_element['src'] if image_element else ''

                            valid_products.append((name, sku_value, image_url))

                            # 显示商品信息和图片
                            if image_url:
                                logger.info(f"  商品{len(valid_products)}: {name} (SKU: {sku_value}) <br><img src='{image_url}' style='max-width:100px;max-height:100px;' />")
                            else:
                                logger.info(f"  商品{len(valid_products)}: {name} (SKU: {sku_value})")
                    except Exception:
                        # 静默处理错误，不显示
                        pass

                if len(valid_products) != len(rows):
                    logger.info(f"📦 找到 {len(valid_products)} 个有效商品")

                # 处理第一个商品
                row_0 = rows[0]
                row_0_td = row_0.find_all('td')

                # 从hidden input获取SKU（更准确）
                sku_input = row_0.find('input', {'name': 'skc'})
                sku = sku_input['value'] if sku_input else None

                if not sku:
                    # 备用方案：从按钮获取
                    buttons = row_0.find_all('button')
                    button_titles = [button.get('title') for button in buttons if button.get('title')]
                    sku = button_titles[0] if button_titles else None

                logger.info(f'提取的SKU: {sku}')

                brand_category = row_0_td[1].get_text(strip=True) if len(row_0_td) > 1 else ''
                image_element = row_0.find('img')
                image_url = image_element['src'] if image_element else ''
                name_element = row_0.find('a')
                name = name_element.get_text(strip=True) if name_element else '未知商品'
                distribution_price = row_0_td[5].get_text(strip=True) if len(row_0_td) > 5 else ''
                market_price = row_0_td[6].get_text(strip=True) if len(row_0_td) > 6 else ''
                listing_time = row_0_td[7].get_text(strip=True) if len(row_0_td) > 7 else ''

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
    logger.info('selectBuyDefect')
    sku = urllib.parse.quote(sku)
    logger.debug(f'sku: {sku}')
    resp = requests.get(url=f'{config.URL_SELECT_BUY_PRODUCT}?skc={sku}', headers=headers)
    logger.debug(f'status_code: {resp.status_code}')
    
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")
        return saveCart(soup)
    return None

# 保存到购物车
def saveCart(soup: BeautifulSoup):
    logger.debug('saveCart')
    type_code = soup.find('input', {'name': 'typeCode'})['value']
    price = soup.find('input', {'name': 'price'})['value']
    product_code = soup.find('input', {'name': 'productCode'})['value']
    
    stock = soup.find('input', {'id': f'stock{product_code}'})['value']
    count = int(stock)
    param_save_cart = {'typeCode': 0, 'price': 0, 'productCode': 0, 'count': 0}
    param_save_cart.update({
        'typeCode': type_code,
        'price': price,
        'productCode': product_code,
        'count': count
    })

    logger.debug(f'param_save_cart: {param_save_cart}')

    resp = requests.post(url=config.URL_SAVE_CART, headers=headers, params=param_save_cart)
    logger.debug(f'status_code: {resp.status_code}')
    logger.debug(f'content: {resp.content.decode("utf-8")}')
    if resp.status_code == 200:
        logger.info('加入购物车成功')

        try:
            cart_resp = requests.get(config.URL_CART, headers=headers)
            if cart_resp.status_code == 200:
                cart_soup = BeautifulSoup(cart_resp.content, "html.parser", from_encoding="utf-8")
                rows = cart_soup.select('tbody tr')

                for row in rows:
                    row_product_code = row.find_all('td')[2].get_text(strip=True)
                    if row_product_code == product_code:
                        cart_id = row.find('input', {'type': 'checkbox'})['value']
                        return {
                            'cart_id': cart_id,
                            'product_code': product_code,
                            'productCode': product_code,
                            'count': count,
                            'price': price
                        }
        except Exception as e:
            logger.error(f"获取购物车ID失败: {e}", exc_info=True)

        return {
            'cart_id': None,
            'product_code': product_code,
            'productCode': product_code,
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
    logger.info(f'结算商品: {checkId}, 支付类型: {payType}')
    resp = requests.get(url=f'{config.URL_SETTLE}?checked={checkId}', headers=headers)
    soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")

    rows = soup.select('tbody tr')
    row_0 = rows[0]
    row_0_td = row_0.find_all('td')
    name = row_0_td[4].get_text(strip=True)
    logger.info(f'name: {name}')

    settleData = {
        'rankCode': 0, 'tagCode': 0, 'shippingMethod': 1, 'thirdcode': '',
        'payType': payType, 'zip': '', 'idno': '', 'exchangeRate': 1,
        'cartCodes': checkId, 'defectNo': '', 'productcode': '0', 'counts': count, 'description': ''
    }
    settleData.update(config.RECEIVER_INFO)
    try:
        settleData.update({
            'rankCode': soup.find('input', {'name': 'rankCode'})['value'],
            'tagCode': soup.find('input', {'name': 'tagCode'})['value'],
            'shippingMethod': soup.find('input', {'name': 'shippingMethod'})['value'],
            'thirdcode': soup.find('input', {'name': 'thirdcode'}).get('value', ''),
            'exchangeRate': soup.find('input', {'name': 'exchangeRate'})['value'],
            'productcode': soup.find('input', {'name': 'productcode'})['value'],
        })

        settleData['cartCodes'] = checkId
        settleData['counts'] = count

    except Exception as e:
        logger.warning(f"获取页面数据时出错: {e}，使用默认值")
        settleData.update({
            'rankCode': '68',
            'tagCode': '30',
            'shippingMethod': '1',
            'thirdcode': '',
            'exchangeRate': '1',
            'productcode': '',
        })

    logger.debug(f'settleData: {settleData}')

    wxpush = PushPlus()

    resp = requests.post(url=config.URL_SETTLE_SAVE, headers=headers, data=settleData)
    logger.debug(f'📤 提交状态码: {resp.status_code}')

    if resp.status_code == 200:
        try:
            result = resp.json()
            logger.debug(f"📋 提交结果: {result}")

            if result.get('resultCode') == 0:
                order_code = result.get('data', {}).get('code', 'Unknown')
                total_amount = result.get('data', {}).get('paid', 0)

                logger.info(f"✅ 单独下单成功!")
                logger.info(f"📦 订单号: {order_code}")
                logger.info(f"💰 订单金额: ¥{total_amount}")
                logger.info(f"💳 支付类型: {'支付宝' if payType == '1' else '微信支付'}")

                try:
                    wxpush.sendMsg(name, f'下单成功!\n订单号: {order_code}\n商品: {name}\n数量: {count}\n金额: ¥{total_amount}\n支付: {"支付宝" if payType == "1" else "微信支付"}')
                except Exception as e:
                    logger.warning(f"⚠️ 发送通知失败: {e}")

                try:
                    from .web import push_order_to_clients
                    from ..common.orders import set_orders

                    set_orders(order_code)

                    logger.info(f"🚀 直接推送订单号: {order_code}")
                    push_order_to_clients(order_code)
                except Exception as e:
                    logger.error(f"❌ 直接推送订单失败: {e}", exc_info=True)

                return True
            else:
                error_msg = result.get('errorMsg', '未知错误')
                logger.error(f"❌ 订单提交失败: {error_msg}")
                wxpush.sendMsg(name, f'下单失败! {error_msg}')
                return False

        except json.JSONDecodeError:
            logger.error(f"❌ 响应解析失败: {resp.text}")
            wxpush.sendMsg(name, f'下单失败! 响应解析失败')
            return False
    else:
        logger.error(f"❌ 请求失败: {resp.status_code}")
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
    # 确保 data 目录存在
    os.makedirs('data', exist_ok=True)
    with open('data/processed_keywords.txt', 'a') as f:
        f.write(f"{keyword},{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

def load_processed_keywords():
    """加载已成功处理的关键字"""
    try:
        with open('data/processed_keywords.txt', 'r') as f:
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
    if not should_query_products(keyword):
        return False

    from ..common.status import get_global_auto_order_status
    auto_order_enabled = get_global_auto_order_status()

    product = query_product(keyword)
    logger.debug(f'product: {product}')
    if product:
        param_save_cart = selectBuyDefect(product['sku'])

        if param_save_cart:
            product_code_value = param_save_cart.get('productCode') or param_save_cart.get('product_code')
            count = param_save_cart.get('count', 1)

            if not product_code_value:
                logger.error(f"❌ 关键词 {keyword} 获取商品代码失败，param_save_cart: {param_save_cart}")
                return False

            logger.info(f"📦 关键词 {keyword} 获取到商品代码: {product_code_value}, 数量: {count}")

            if auto_order_enabled:
                checkout_result = check_cart(product_code_value, count, config.PAY_TYPE_WECHAT)
                if checkout_result:
                    logger.info(f"关键字 {keyword} 自动下单成功")
                    save_keyword_status(keyword)

                    return True
            else:
                wxpush = PushPlus()
                msg = f'库存更新 {product["name"]},\n            <br />数量 {count}\n            <br />金额 {product["distribution_price"]}\n            <br /><img src="{product["image_url"]}" width="200px" height="200px" />'
                wxpush.sendMsg(keyword, msg)
                logger.debug(f'msg: {msg}')
                logger.info(f"关键字 {keyword} 通知发送成功")
                save_keyword_status(keyword)
                return True

    return False


    
def refresh_orders():
    """刷新订单列表，只获取待付款的订单"""
    logger.info('getOrder')
    resp = requests.get(url=config.URL_ORDERLIST, headers=headers)
    soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")

    tbody = soup.find('tbody')
    if not tbody:
        logger.warning("未找到订单表格")
        return []

    orders = []
    rows = tbody.find_all('tr')

    for row in rows:
        try:
            tds = row.find_all('td')
            if len(tds) >= 6:
                order_link = tds[0].find('a')
                if order_link and 'showOrder' in order_link.get('href', ''):
                    match = re.search(r"showOrder\('(\w+)'\)", order_link['href'])
                    if match:
                        order_number = match.group(1)

                        order_status = tds[5].get_text(strip=True)

                        if order_status == '待付款':
                            logger.info(f"发现待付款订单: {order_number}")
                            orders.append(order_number)
                            set_orders(order_number)
                        else:
                            logger.debug(f"订单 {order_number} 状态为 '{order_status}'，跳过")
        except Exception as e:
            logger.error(f"解析订单行时出错: {e}", exc_info=True)
            continue

    logger.info(f"共找到 {len(orders)} 个待付款订单")
    return orders

def check_order_payment_status():
    """检查订单付款状态，移除已付款的订单"""
    from ..common.orders import get_orders
    from .web import remove_paid_orders

    current_orders = get_orders()
    if not current_orders:
        return

    logger.info(f"🔍 检查 {len(current_orders)} 个订单的付款状态...")

    try:
        resp = requests.get(url=config.URL_ORDERLIST, headers=headers)
        soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")

        tbody = soup.find('tbody')
        if not tbody:
            return

        try:
            message_div = soup.find('div', class_='message')
            if message_div:
                total_text = message_div.get_text()
                total_match = re.search(r'共.*?(\d+).*?条记录', total_text)
                if total_match:
                    total_count = int(total_match.group(1))
                    logger.info(f"📊 当前待付款订单总数: {total_count}")
        except Exception as e:
            logger.warning(f"⚠️ 提取订单总数失败: {e}")

        pending_orders = set()
        rows = tbody.find_all('tr')

        for row in rows:
            try:
                tds = row.find_all('td')
                if len(tds) >= 1:
                    order_link = tds[0].find('a')
                    if order_link and 'showOrder' in order_link.get('href', ''):
                        match = re.search(r"showOrder\('(\w+)'\)", order_link['href'])
                        if match:
                            order_number = match.group(1)
                            pending_orders.add(order_number)
                            logger.info(f"📋 发现待付款订单: {order_number}")
            except Exception as e:
                continue

        logger.info(f"📊 服务器端待付款订单: {list(pending_orders)}")
        logger.info(f"📊 本地订单列表: {current_orders}")

        paid_orders = []
        for order in current_orders:
            if order not in pending_orders:
                paid_orders.append(order)
                logger.info(f"✅ 订单 {order} 已付款（不在待付款列表中）")
            else:
                logger.info(f"📋 订单 {order} 仍为待付款状态")

        if paid_orders:
            remove_paid_orders(paid_orders)
            logger.info(f"🗑️ 已移除 {len(paid_orders)} 个已付款订单")
        else:
            logger.info("📋 所有订单仍为待付款状态")

    except Exception as e:
        logger.error(f"❌ 检查订单状态失败: {e}", exc_info=True)

def query_product_count():
    """查询商品总数"""
    logger.info('query_product_count')
    
    try:
        headers['cookie'] = load_cookie()
        resp = requests.get(url=config.URL_QUERY_PRODUCT_COUNTS, headers=headers, timeout=10)
        logger.debug(f'status_code: {resp.status_code}')
        
        if 'login.do' in resp.url:
            do_login()
            return query_product_count()
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")
            message_div = soup.find('div', class_='message')
            if message_div:
                total_records = message_div.find('i', class_='blue').text
                logger.info(f'商品总数: {total_records}')
                return int(total_records)
        
            logger.warning("⚠️ 未找到商品总数信息")
            return None
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ 网络请求失败: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ 查询商品总数时出错: {e}", exc_info=True)
        return None

def should_query_products(keyword):
    """判断是否需要查询具体商品"""
    current_count = query_product_count()

    if current_count is None:
        return True

    last_count = state.last_product_count.get(keyword, 0)

    if current_count != last_count:
        state.last_product_count[keyword] = current_count
        logger.info(f'商品总数变化: {last_count} -> {current_count}，需要查询商品')
        return True

    logger.info(f'商品总数未变化: {current_count}，跳过查询')
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
    from ..common.status import load_monitor_status, get_global_test_mode
    monitor_enabled = load_monitor_status()
    test_mode = get_global_test_mode()

    # 只有在监控开启或测试模式下才执行检查
    if not monitor_enabled and not test_mode:
        logger.debug("监控关闭且非测试模式，跳过商品总数变化检查。")
        return False

    current_count = query_product_count()
    current_time = datetime.now()

    if current_count is None:
        return True

    try:
        from ..common.status import increment_refresh_count
        increment_refresh_count()
    except Exception as e:
        logger.warning(f"⚠️ 记录刷新次数失败: {e}")

    if state._last_total_count != current_count:
        logger.info(f'📈 商品总数变化: {state._last_total_count} -> {current_count}，需要查询商品')
        state._last_total_count = current_count
        state._last_check_time = current_time
        return True

    logger.info(f'📊 商品总数未变化: {current_count}，跳过查询')
    return False

def process_keyword_direct(keyword):
    """直接处理关键词，支持单独建单和统一建单模式"""
    from ..common.status import load_monitor_status, get_global_test_mode
    monitor_enabled = load_monitor_status()
    test_mode = get_global_test_mode()

    # 只有在监控开启或测试模式下才执行查询
    if not monitor_enabled and not test_mode:
        logger.debug(f"监控关闭且非测试模式，跳过关键词 '{keyword}' 查询。")
        return False

    # 查询商品
    product = query_product(keyword)
    logger.debug(f'product: {product}')

    if not product:
        logger.debug(f"📡 关键词 {keyword} 暂无库存")
        return False

    # 获取系统状态
    from ..common.status import get_global_auto_order_status, get_global_batch_order_mode
    auto_order_enabled = get_global_auto_order_status()
    batch_mode = get_global_batch_order_mode()

    logger.info(f"🔍 [PROCESS] 模式检查: auto_order_enabled={auto_order_enabled}, test_mode={test_mode}, batch_mode={batch_mode}")

    if auto_order_enabled or test_mode:
        return _handle_order_mode(keyword, product, test_mode, batch_mode)
    else:
        return _handle_notification_mode(keyword, product)




def _handle_order_mode(keyword, product, test_mode, batch_mode):
    """处理下单模式（自动下单或测试模式）"""
    param_save_cart = selectBuyDefect(product['sku'])

    if not param_save_cart:
        logger.error(f"❌ [PROCESS] 关键词 {keyword} selectBuyDefect 失败")
        return True

    product_code_value = param_save_cart.get('productCode') or param_save_cart.get('product_code')
    count = param_save_cart.get('count', 1)

    if not product_code_value:
        logger.error(f"❌ 关键词 {keyword} 获取商品代码失败，param_save_cart: {param_save_cart}")
        return False

    logger.info(f"📦 关键词 {keyword} 获取到商品代码: {product_code_value}, 数量: {count}")

    # 确定处理模式
    use_cart, mode_name = _determine_processing_mode(test_mode, batch_mode, keyword)

    if use_cart:
        return _handle_cart_mode(keyword, product, product_code_value, count, mode_name)
    else:
        return _handle_direct_order_mode(keyword, product, product_code_value, count, mode_name)


def _determine_processing_mode(test_mode, batch_mode, keyword):
    """确定处理模式和名称"""
    if test_mode:
        if batch_mode:
            logger.info(f"🧪 [TEST] 测试统一建单模式：关键词 {keyword} 加入购物车")
            return True, "测试统一建单"
        else:
            logger.info(f"🧪 [TEST] 测试单独建单模式：关键词 {keyword} 立即下单")
            return False, "测试单独建单"
    elif batch_mode:
        logger.info(f"🛒 [BATCH] 统一建单模式：关键词 {keyword} 加入购物车")
        return True, "统一建单"
    else:
        logger.info(f"⚡ [SINGLE] 单独建单模式：关键词 {keyword} 立即下单")
        return False, "单独建单"


def _handle_cart_mode(keyword, product, product_code_value, count, mode_name):
    """处理购物车模式"""
    cart_result = selectBuyDefect(product['sku'])
    logger.debug(f"🔄 [PROCESS] selectBuyDefect 结果: {cart_result}")

    if not cart_result:
        logger.error(f"❌ [PROCESS] 关键词 {keyword} selectBuyDefect 失败")
        return True

    # 构建商品信息
    product_info = _build_product_info(keyword, product_code_value, product)

    logger.info(f"🔄 [PROCESS] 准备调用 add_to_batch_cart")
    add_to_batch_cart(product_info, cart_result)

    logger.info(f"✅ [PROCESS] {mode_name}：关键字 {keyword} 商品已加入购物车")

    # 记录商品详情
    _log_product_details(product_info, count, cart_result)

    return True


def _handle_direct_order_mode(keyword, product, product_code_value, count, mode_name):
    """处理直接下单模式，并应用数量和金额限制"""
    from ..config import config
    try:
        price = float(product.get('distribution_price', 0))
    except (ValueError, TypeError):
        price = 0
    
    available_quantity = int(count)
    
    # 1. 应用数量上限
    order_quantity = min(available_quantity, config.MAX_QUANTITY_PER_ORDER)
    
    # 2. 应用金额上限
    if price > 0:
        max_qty_by_amount = int(config.MAX_AMOUNT_PER_ORDER / price)
        order_quantity = min(order_quantity, max_qty_by_amount)

    if order_quantity <= 0:
        logger.warning(f"⚠️ {mode_name}：商品 {product['name']} 单价过高或库存为0，无法下单。")
        return False

    if order_quantity < available_quantity:
        logger.info(f"⚡️ {mode_name}：商品 {product['name']} 库存({available_quantity})超限，调整下单数量为: {order_quantity}")

    checkout_result = check_cart(product_code_value, order_quantity, config.PAY_TYPE_WECHAT)

    if not checkout_result:
        return False

    logger.info(f"✅ [PROCESS] {mode_name}：关键字 {keyword} 自动下单成功")
    return True


def _handle_notification_mode(keyword, product):
    """处理通知模式（只发送库存通知）"""
    logger.info(f"📢 [PROCESS] 关键词 {keyword} 进入通知模式（只发送库存通知）")

    wxpush = PushPlus()
    msg = f'库存更新 {product["name"]},\n            <br />金额 {product["distribution_price"]}\n            <br /><img src="{product["image_url"]}" width="200px" height="200px" />'
    wxpush.sendMsg(keyword, msg)
    logger.debug(f'msg: {msg}')
    logger.info(f"关键字 {keyword} 通知发送成功")
    save_keyword_status(keyword)

    return True



def _build_product_info(keyword, product_code_value, product):
    """构建商品信息字典"""
    return {
        'keyword': keyword,
        'product_code': product_code_value,
        'price': product['distribution_price'],
        'distribution_price': product['distribution_price'],
        'name': product['name'],
        'image_url': product.get('image_url', ''),
        'market_price': product.get('market_price', ''),
        'brand_category': product.get('brand_category', '')
    }


def _log_product_details(product_info, count, cart_result):
    """记录商品详情日志"""
    image_url = product_info.get('image_url', '')
    if image_url:
        html_msg = f'''📦 商品详情: {product_info['name']}
                        💰 价格: ¥{product_info.get('price', '未知')}
                        📦 库存: {count}
                        🛒 购物车ID: {cart_result['cart_id']}
                        <br><img src="{image_url}" style="max-width:200px;max-height:200px;border-radius:8px;" />'''
        logger.info(html_msg)

def find_latest_updated_products(sort_field_override=None):
    """
    智能发现最新商品。
    - 如果提供了 sort_field_override，则只测试该字段。
    - 否则，将自动遍历候选列表，直到找到有效的排序字段。
    """
    all_successful_results = {}  # 用于存储所有成功字段的结果

    if sort_field_override:
        fields_to_try = [sort_field_override]
        logger.info(f"🚀 开始手动智能发现：测试指定字段 '{sort_field_override}'...")
    else:
        fields_to_try = config.SORT_FIELD_CANDIDATES
        logger.info(f"🚀 开始自动智能发现：将尝试 {len(fields_to_try)} 个可能的排序字段...")
    
    headers['cookie'] = load_cookie()
    if not headers['cookie']:
        logger.info("Cookie为空，尝试登录...")
        do_login()
        headers['cookie'] = load_cookie()

    for i, field in enumerate(fields_to_try):
        logger.info(f"  [尝试 {i+1}/{len(fields_to_try)}] 使用排序字段: '{field}'")
        
        query_params = config.PARAM_QUERY_PRODUCT.copy()
        query_params['keyword'] = ''  # 全局搜索
        query_params['sortFiled'] = field
        query_params['sort'] = 'desc'

        try:
            resp = requests.post(url=config.URL_QUERY_PRODUCT, headers=headers, params=query_params, timeout=15)

            if 'login.do' in resp.url:
                logger.warning("会话已过期，重新登录并重试本次请求...")
                do_login()
                headers['cookie'] = load_cookie()
                resp = requests.post(url=config.URL_QUERY_PRODUCT, headers=headers, params=query_params, timeout=15)

            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")
                rows = soup.select('tbody tr')

                if not rows:
                    logger.info(f"    -> 字段 '{field}' 未返回任何商品。")
                    continue

                logger.info(f"✅ 成功! 字段 '{field}' 返回了 {len(rows)} 条记录。这很可能就是我们要找的字段！")
                logger.info(f"以下是按 '{field}' 排序的TOP 5商品：")
                
                found_products = []
                for j, row in enumerate(rows[:5]):
                    try:
                        sku_input = row.find('input', {'name': 'skc'})
                        if not sku_input: continue

                        name_element = row.find('a')
                        name = name_element.get_text(strip=True) if name_element else '未知商品'
                        listing_time = row.find_all('td')[7].get_text(strip=True)
                        
                        product_info = {'name': name, 'sku': sku_input['value'], 'listing_time': listing_time, 'sort_field': field}
                        found_products.append(product_info)
                        logger.info(f"  TOP {j+1}: {name} (上架/更新时间: {listing_time})")
                    except Exception as e:
                        logger.warning(f"解析商品行失败: {e}")
                
                if found_products:
                    all_successful_results[field] = found_products
            else:
                logger.error(f"    -> 字段 '{field}' 请求失败，状态码: {resp.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"    -> 字段 '{field}' 网络错误: {e}")
            continue

    if not all_successful_results:
        logger.warning("⚠️ 自动智能发现完成，未能从候选列表中找到有效的排序字段。")
    else:
        logger.info(f"🎉 自动智能发现完成，共找到 {len(all_successful_results)} 个有效的排序字段。")

    return all_successful_results