# -*- coding:utf-8 -*-
#!/usr/bin/python

import requests
import re
from bs4 import BeautifulSoup
# from http import cookiejar


max_money = 20000

headers = {
    'accept' : 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-encoding': 'gzip, deflate, br, zstd',
    'content-type': 'application/x-www-form-urlencoded',
    'cookie': 'JSESSIONID=52E75FA6DCC05C4858625F412666175C; Hm_lvt_d0bc2426d87c21553db890f659e4af7b=1725774010; HMACCOUNT=1D22699C25816F54; Hm_lpvt_d0bc2426d87c21553db890f659e4af7b=1725779580',
    'host': 'fenxiao.clim.cn',
    'origin': 'https://fenxiao.clim.cn',
    'referer': 'https://fenxiao.clim.cn/shop/products.do',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'

}

url_query_product = 'https://fenxiao.clim.cn/shop/products.do'
param_query_product = {
    'minWarehouseCount': None,
    'maxWarehouseCount': None,
    'keyword': 'C2712QBMI5',
    'pageIndex': None,
    'pageSize': None,
    'recommendTypeCode': 1,
    'sort': 'desc',
    'sortFiled': 'online_time'
}

url_select_buy_pruduct = 'https://fenxiao.clim.cn/shop/selectBuyProduct.do?skc='

url_save_cart = 'https://fenxiao.clim.cn/shop/saveCart.do'
param_save_cart = {
    'typeCode': 0,
    'price': 0,
    'productCode': 0,
    'count': 0
}


url_cart = 'https://fenxiao.clim.cn/shop/cart.do?v=4.0'
url_settle = 'https://fenxiao.clim.cn/shop/settle.do?checked='
url_settle_save = 'https://fenxiao.clim.cn/shop/settlesave.do?statuscode=5'

settleData = {
    'rankCode': 0,
    'tagCode': 0,
    'shippingMethod': 1,
    'thirdcode': '',
    'receiver': '李不帅',
    'recvphone': '18529551929',
    'provincecode': 19,
    'citycode': 202,
    'countycode': 1754,
    'recvaddr': '化龙镇山门大道700号',
    'zip': '',
    'idno': '',
    'exchangeRate': 1,
    'paid': 0,
    'rmbAmount': 0,
    'cartCodes': '0',
    'itemPrice': 0,
    'itemRmbAmount': 0,
    'defectNo': '',
    'productcode': '0',
    'counts': 0,
    'description': ''
}



def query_product(keyword):
    param_query_product['keyword'] = keyword
    resp = requests.post(url=url_query_product, headers=headers, params=param_query_product)
    # print(resp.content)
    print(f'status_code: {resp.status_code}')
    sku = None
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")
        # print(soup)
        rows = soup.select('tbody tr')
        print('查看供应商商品', len(rows))

        if len(rows) > 0:
            row_0 = rows[0]
            row_0_td = row_0.find_all('td')
            brand_category = row_0_td[1].get_text(strip=True)
            image_url = row_0.find('img')['src']
            name = row_0.find('a').get_text(strip=True)
            weight = row_0_td[4].get_text(strip=True)
            distribution_price = row_0_td[5].get_text(strip=True)
            market_price = row_0_td[6].get_text(strip=True)
            listing_time = row_0_td[7].get_text(strip=True)
            # 提取库存信息从 row_0_td[8] 中的嵌套表格
            stock_table = row_0_td[8].find('table')
            if stock_table:
                stock_rows = stock_table.find_all('tr')
                if len(stock_rows) > 1:
                    stock = stock_rows[1].find_all('td')[1].get_text(strip=True)
                else:
                    stock = "无库存信息"
            else:
                stock = "无库存信息"

            # Print the extracted data
            print(f"品牌/分类: {brand_category}")
            print(f"图片: {image_url}")
            print(f"名称: {name}")
            print(f"重量: {weight}kg")
            print(f"分销价(CNY)	: {distribution_price} CNY")
            print(f"市场价: {market_price} CNY")
            print(f"上新时间: {listing_time}")
            print(f"库存: {stock}")
            print("-" * 50)

            
            # 提取 button 的 title -> 真实编号
            # buttons = stock_rows[13].find_all('button')
            buttons = row_0.find_all('button')
            button_titles = [button.get('title', None) for button in buttons]
            print('button_titles', button_titles)
            sku = button_titles[0]
            
        else:
            print('无库存')

    return sku

def selectBuyDefect(sku):
    resp = requests.get(url=f'{url_select_buy_pruduct}{sku}', headers=headers)
    print(f'status_code: {resp.status_code}')
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")
        # print(soup)
        return saveCart(soup)
    return None


def saveCart(soup: BeautifulSoup):
    type_code = soup.find('input', {'name': 'typeCode'})
    price = soup.find('input', {'name': 'price'})
    product_code = soup.find('input', {'name': 'productCode'})

    print(type_code)
    print(price)
    print(product_code)

    type_code_value = type_code['value']
    price_value = price['value']
    product_code_value = product_code['value']
    print(f"typeCode 的值: {type_code_value}")
    print(f"price 的值: {price_value}")
    print(f"productCode 的值: {product_code_value}")

    # 库存
    stock = soup.find('input', {'id': f'stock{product_code_value}'})
    stock_value = stock['value']
    print(f"stock_value 的值: {stock_value}")

    # 下单数 = 库存数
    count = stock_value

    # price_value = 30000

    # 总价
    total_price = float(price_value) * float(stock_value)
    print('总价', total_price)
    if total_price > max_money:
        count = max_money / price_value
        print(f'总价过大，下单数量:{count}')

    print(f'下单数量:{count}')
    param_save_cart['typeCode'] = type_code_value
    param_save_cart['price'] = price_value
    param_save_cart['productCode'] = product_code_value
    param_save_cart['count'] = count

    resp = requests.post(url=url_save_cart, headers=headers, params=param_save_cart)
    status_code = resp.status_code
    content = resp.content
    print('content', content)
    
    if status_code == 200:
        print('加入购物车成功')
        return product_code_value
    return None

def check_cart():
    resp = requests.get(url_cart, headers=headers)
    soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")
    # print(soup)
    rows = soup.select('tbody tr')
    print(len(rows))

    if len(rows) > 0:
        row_0 = rows[0]
        # 提取隐藏的输入字段
        hidden_inputs = row_0.find_all('input', type='hidden')
        hidden_data = {input_elem.get('name'): input_elem.get('value') for input_elem in hidden_inputs}

        # 提取数据
        checkbox_value = row_0.find('input', {'type': 'checkbox'}).get('value', '未找到')
        img_src = row_0.find('img')['src']
        product_code = row_0.find_all('td')[2].get_text(strip=True)
        description = row_0.find_all('td')[3].get_text(strip=True)
        item_name = row_0.find_all('td')[4].get_text(strip=True)
        product_link = row_0.find('a').get_text(strip=True)
        price = row_0.find_all('td')[6].get_text(strip=True)
        remarks = row_0.find_all('td')[7].get_text(strip=True)
        stock = row_0.find_all('td')[8].get_text(strip=True)
        # 打印提取的数据
        print(f"隐藏数据: {hidden_data}")
        print(f"复选框的值: {checkbox_value}")
        print(f"图片链接: {img_src}")
        print(f"产品代码: {product_code}")
        print(f"描述: {description}")
        print(f"项目名称: {item_name}")
        print(f"产品链接: {product_link}")
        print(f"价格: {price}")
        print(f"备注: {remarks}")
        print(f"库存: {stock}")
        print("-" * 50)
        

def check_cart1(product_code_value):
    resp = requests.get(url_cart, headers=headers)
    soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")
    # print(soup)
    rows = soup.select('tbody tr')
    print(len(rows))

    if len(rows) > 0:
        for row in rows:
            # 获取隐藏输入字段
            # hidden_inputs = row.find_all('input', type='hidden')
            # hidden_data = {input_elem.get('name'): input_elem.get('value') for input_elem in hidden_inputs}
            rank_code_input = row.find('input', {'class': 'rankCode'})
            rank_code = rank_code_input['value']

            # 提取数据
            checkbox_value = row.find('input', {'type': 'checkbox'}).get('value', '未找到')
            img_src = row.find('img')['src']
            product_code = row.find_all('td')[2].get_text(strip=True)
            description = row.find_all('td')[3].get_text(strip=True)
            item_name = row.find_all('td')[4].get_text(strip=True)
            product_link = row.find('a').get_text(strip=True)
            price = row.find_all('td')[6].get_text(strip=True)
            remarks = row.find_all('td')[7].get_text(strip=True)
            stock = row.find_all('td')[8].get_text(strip=True)
            
            # 打印提取的数据
            print(f"隐藏数据: {rank_code}")
            print(f"复选框的值: {checkbox_value}")
            print(f"图片链接: {img_src}")
            print(f"产品代码: {product_code}")
            print(f"描述: {description}")
            print(f"项目名称: {item_name}")
            print(f"产品链接: {product_link}")
            print(f"价格: {price}")
            print(f"备注: {remarks}")
            print(f"库存: {stock}")
            print("-" * 50)

            if product_code == product_code_value:
                checkout(checkbox_value)
                break

def checkout(checkId):
    pass
    print('结算 checkId=', checkId)
    resp = requests.get(url=f'{url_settle}{checkId}', headers=headers)
    soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")

    rankCode = soup.find('input', {'name': 'rankCode'})
    tagCode = soup.find('input', {'name': 'tagCode'})
    shippingMethod = soup.find('input', {'name': 'shippingMethod'})
    thirdcode = soup.find('input', {'name': 'thirdcode'})

    exchangeRate = soup.find('input', {'name': 'exchangeRate'})
    rmbAmount = soup.find('input', {'name': 'rmbAmount'})
    paid = soup.find('input', {'name': 'paid'})
    cartCodes = soup.find('input', {'name': 'cartCodes'})
    itemPrice = soup.find('input', {'name': 'itemPrice'})
    itemRmbAmount = soup.find('input', {'name': 'itemRmbAmount'})
    defectNo = soup.find('input', {'name': 'defectNo'})
    counts = soup.find('input', {'name': 'counts'})
    productcode = soup.find('input', {'name': 'productcode'})

    settleData['rankCode'] = rankCode['value']
    settleData['tagCode'] = tagCode['value']
    settleData['shippingMethod'] = shippingMethod['value']
    settleData['thirdcode'] = thirdcode.get('value', None) if thirdcode else None
    settleData['exchangeRate'] = exchangeRate['value']
    settleData['paid'] = paid['value']
    settleData['rmbAmount'] = rmbAmount['value']
    settleData['cartCodes'] = cartCodes['value']
    settleData['itemPrice'] = itemPrice['value']
    settleData['itemRmbAmount'] = itemRmbAmount['value']
    settleData['defectNo'] = defectNo['value']
    settleData['productcode'] = productcode['value']
    settleData['counts'] = counts['value']
    print(settleData)
    resp = requests.post(url=url_settle_save, headers=headers, params=settleData)
    status_code = resp.status_code
    content = resp.content
    print('status_code', status_code)
    print('content', content.decode('utf-8'))

if __name__ == "__main__":
    keys = ['C2712QBMI5', 'CH137SVM6A', ]
    for key in keys:
        sku = query_product(key)
        product_code_value = selectBuyDefect(sku)
        if product_code_value:
            check_cart1(product_code_value)