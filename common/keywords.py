#!/usr/bin/env python
# -*- coding: utf-8 -*-

keywords = []
file_name_keywords = 'keywords.txt'

def save_keyword(keyword):
    global keywords
    if keyword not in keywords:
        keywords.append(keyword)
        """保存关键字到文件中"""
        with open(file_name_keywords, 'a') as f:
            f.write(f"{keyword}\n")

def remove_keyword(keyword):
    global keywords
    if keyword in keywords:
        # Remove keyword
        keywords.remove(keyword)
        print('keywords', keywords)
        with open(file_name_keywords, 'w') as f:
            for kw in keywords:
                f.write(f"{kw}\n")

def load_keywords():
    global keywords
    """加载关键字"""
    try:
        with open(file_name_keywords, 'r') as f:
            lines = f.readlines()
            keywords = [line.strip() for line in lines if line.strip()]
            return keywords
    except FileNotFoundError:
        return []

def get_global_keywords():
    return keywords