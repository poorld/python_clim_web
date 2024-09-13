#!/usr/bin/env python
# -*- coding: utf-8 -*-

refresh_status = False
intensify_refresh_status = False

file_name_status = 'status.txt'
file_name_intensify_status = 'intensify_status.txt'

def load_refresh_status():
    global refresh_status
    try:
        with open(file_name_status, 'r') as f:
            refresh_status = f.readline().strip() == 'True'
            return refresh_status
    except FileNotFoundError:
        return False

def set_refresh_status(status: bool):
    global refresh_status
    refresh_status = status
    """保存成功处理的关键字到文件中"""
    with open(file_name_status, 'w') as f:
        f.write(f"{status}\n")

def get_global_refresh_status(self):
    return refresh_status

# --------------------------------------------
def load_intensify_refresh_status():
    global intensify_refresh_status
    try:
        with open(file_name_intensify_status, 'r') as f:
            intensify_refresh_status = f.readline().strip() == 'True'
            return intensify_refresh_status
    except FileNotFoundError:
        return False

def set_intensify_refresh_status(status: bool):
    global intensify_refresh_status
    intensify_refresh_status = status
    """保存成功处理的关键字到文件中"""
    with open(file_name_intensify_status, 'w') as f:
        f.write(f"{status}\n")

def get_global_intensify_refresh_status(self):
    return intensify_refresh_status
