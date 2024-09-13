#!/usr/bin/env python
# -*- coding: utf-8 -*-

orders_history = []
def save_orders_history(order):
    """保存成功处理的关键字到文件中"""
    with open('orders.txt', 'a') as f:
        f.write(f"{order}\n")

def load_orders_history():
    global orders_history
    """加载已成功处理的关键字"""
    try:
        with open('orders.txt', 'r') as f:
            lines = f.readlines()
            orders_history = [line.strip() for line in lines]
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