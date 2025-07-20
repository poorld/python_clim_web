#!/usr/bin/env python
# -*- coding: utf-8 -*-

orders_history = []
def save_orders_history(order):
    """保存成功处理的关键字到文件中"""
    global orders_history
    # 同时更新内存和文件，避免重复
    if order not in orders_history:
        orders_history.append(order)
        with open('orders.txt', 'a') as f:
            f.write(f"{order}\n")
        print(f"📝 订单 {order} 已保存到历史记录")
    else:
        print(f"⚠️ 订单 {order} 已存在于历史记录中，跳过保存")

def load_orders_history():
    global orders_history
    """加载已成功处理的关键字"""
    try:
        with open('orders.txt', 'r') as f:
            lines = f.readlines()
            # 去重处理
            unique_orders = []
            seen = set()
            for line in lines:
                order = line.strip()
                if order and order not in seen:
                    unique_orders.append(order)
                    seen.add(order)

            orders_history = unique_orders

            # 如果发现重复，重写文件
            original_count = len([line.strip() for line in lines if line.strip()])
            if len(unique_orders) < original_count:
                print(f"🧹 发现重复订单记录，清理中...")
                with open('orders.txt', 'w') as f:
                    for order in unique_orders:
                        f.write(f"{order}\n")
                print(f"✅ 订单记录已清理，从 {original_count} 条减少到 {len(unique_orders)} 条")

            return orders_history
    except FileNotFoundError:
        return []
    
def get_global_orders_history():
    return orders_history

orders = []
def set_orders(_orders):
    global orders
    # orders = _orders
    orders.append(_orders)

def get_orders():
    global orders
    return orders