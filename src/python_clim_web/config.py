# -*- coding:utf-8 -*-
#!/usr/bin/python

import os

class AppConfig:
    """应用全局配置"""
    # 从环境变量获取 PUSHPLUS_TOKEN，如果不存在则使用默认值（建议在生产环境中设置环境变量）
    PUSHPLUS_TOKEN = os.getenv('PUSHPLUS_TOKEN', '251cb35f680d46d994ef95a4470438c3')
    PUSHPLUS_TOPIC = '20240909'
    PUSHPLUS_URL = 'http://www.pushplus.plus/send'

class ProductCheckoutConfig:
    """产品下单配置管理类"""

    # 系统配置
    MAX_MONEY = 35000  # 最大金额限制

    # 登录配置 (建议从环境变量加载)
    LOGIN_USER = {
        'name': os.getenv('CLIM_USERNAME', '琴琴境内-境内'),
        'password': os.getenv('CLIM_PASSWORD', '888888')
    }

    # 收货人信息 (建议从环境变量加载)
    RECEIVER_INFO = {
        'receiver': os.getenv('RECEIVER_NAME', '李小峰'),
        'recvphone': os.getenv('RECEIVER_PHONE', '18529551929'),
        'provincecode': os.getenv('PROVINCE_CODE', '19'),
        'citycode': os.getenv('CITY_CODE', '202'),
        'countycode': os.getenv('COUNTY_CODE', '1754'),
        'recvaddr': os.getenv('RECEIVER_ADDR', '化龙镇山门大道700号'),
    }

    # 批量下单配置
    MAX_PRODUCTS_PER_ORDER = 8  # 每单最多商品种类
    MAX_QUANTITY_PER_ORDER = 40  # 每单最多数量
    MAX_AMOUNT_PER_ORDER = 40000  # 每单最大金额

    THREAD_TIMEOUT = 30  # 线程超时时间（秒）
    MAX_CONCURRENT_THREADS = 10  # 最大并发线程数

    # API URL配置
    BASE_URL = 'https://fenxiao.clim.cn'

    # 登录相关URL
    URL_LOGIN = f'{BASE_URL}/login/checkLogin.do'

    # 商品相关URL
    URL_QUERY_PRODUCT = f'{BASE_URL}/shop/products.do'
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

    # 查询商品参数配置
    PARAM_QUERY_PRODUCT = {
        'keyword': '',
        'recommendTypeCode': 1,
        'sort': 'desc',
        'sortFiled': 'online_time'
    }

    # 智能发现的排序字段候选列表
    SORT_FIELD_CANDIDATES = [
        # --- Top Priority (最优先) ---
        'update_time', 'modify_time', 'last_modified', 'updated_at', 'modified_at',
        'gmt_modified', 'gmt_updated', 'last_update', 'date_modified', 'date_updated',
        'timestamp', 'ts', 'tstamp',

        # --- Common Variations: snake_case (常见变种) ---
        'updated_time', 'modified_time', 'last_update_time', 'last_modify_time', 'last_change_time',
        'update_date', 'modify_date', 'last_update_date', 'change_date',
        'update_ts', 'modify_ts', 'last_update_ts',
        'update_datetime', 'modify_datetime', 'last_update_datetime',

        # --- Common Variations: camelCase & PascalCase (驼峰命名) ---
        'updateTime', 'modifyTime', 'lastModified', 'updatedAt', 'modifiedAt',
        'lastUpdateTime', 'lastModifyTime', 'gmtModified', 'gmtUpdated',
        'updateDate', 'modifyDate', 'lastUpdateDate',
        'UpdateTime', 'ModifyTime', 'LastModified', 'UpdatedAt', 'ModifiedAt',
        'UpdateDate', 'ModifyDate', 'GmtModified', 'GmtUpdated',

        # --- Prefixed/Suffixed (带前后缀) ---
        '_updated_at', '_modified_at', 'time_updated', 'time_modified', 'date_updated',
        'dt_updated', 'dt_modified',

        # --- Synonyms for "update" (更新的同义词) ---
        'change_time', 'changed_at', 'last_change', 'edit_time', 'last_edit',
        'revision_time', 'revision_date', 'last_revision',
        'sync_time', 'last_sync', 'refresh_time', 'last_refresh',

        # --- System/Framework Specific (系统/框架特定) ---
        'sys_mod_time', 'sys_update_time', 'row_version', 'rowversion', 'version',
        'rec_mod_time', '_ts',

        # --- Business Logic Specific (业务逻辑相关) ---
        'stock_update_time', 'stock_updated_at', 'inventory_update_time', 'inventory_updated_at',
        'price_update_time', 'price_updated_at',
        'available_time', 'available_date', 'availability_date',
        'publish_time', 'published_at', 'publish_date', 'published_date',
        'release_date', 'release_time',

        # --- Creation Time & Generic (创建时间及通用) ---
        'create_time', 'created_at', 'creation_time', 'created_time', 'creation_date',
        'insert_time', 'inserted_at', 'add_time', 'date_added', 'entry_date', 'post_date', 'post_modified',
        'last_accessed', 'access_time', 'event_date', 'log_date', 'record_date', 'data_update_time',
        'mod_time', 'upd_time', 'mod_date', 'upd_date',

        # --- Original Default (原始默认值) ---
        'online_time'
    ]

    HEADERS = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-encoding': 'gzip, deflate, br, zstd',
        'content-type': 'application/x-www-form-urlencoded',
        'cookie': 'JSESSIONID=52E75FA6DCC05C4858625F412666175C',
        'host': 'fenxiao.clim.cn',
        'origin': f'{BASE_URL}',
        'referer': f'{BASE_URL}/shop/products.do',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
    }

# 全局实例
config = ProductCheckoutConfig()