#!/usr/bin/env python
# -*- coding: utf-8 -*-

keywords = []
intensify_keywords = []

file_name_keywords = 'keywords.txt'
file_name_intensify_keywords = 'intensify_keywords.txt'

def save_keyword(keyword, intensify = False):
    global keywords
    global intensify_keywords
    if intensify:
        keywords.append(keyword)
        """保存成功处理的关键字到文件中"""
        with open(file_name_intensify_keywords, 'a') as f:
            f.write(f"{keyword}\n")
    else:
        keywords.append(keyword)
        """保存成功处理的关键字到文件中"""
        with open(file_name_keywords, 'a') as f:
            f.write(f"{keyword}\n")

def remove_keyword(keyword, intensify = False):
    global keywords
    global intensify_keywords
    if intensify:
        # Remove keyword
        intensify_keywords.remove(keyword)
        print('intensify_keywords', intensify_keywords)
        with open(file_name_intensify_keywords, 'w') as f:
            for keyword in intensify_keywords:
                f.write(f"{keyword}\n")
        
    else:
        # Remove keyword
        keywords.remove(keyword)
        print('keywords', keywords)
        with open(file_name_keywords, 'w') as f:
            for keyword in keywords:
                f.write(f"{keyword}\n")

def load_keywords(intensify = False):
    global keywords
    global intensify_keywords

    if intensify:
        """加载已成功处理的关键字"""
        try:
            with open(file_name_intensify_keywords, 'r') as f:
                lines = f.readlines()
                intensify_keywords = [line.strip() for line in lines]
                return intensify_keywords
        except FileNotFoundError:
            return []
    else:
        """加载已成功处理的关键字"""
        try:
            with open(file_name_keywords, 'r') as f:
                lines = f.readlines()
                keywords = [line.strip() for line in lines]
                return keywords
        except FileNotFoundError:
            return []
        
        
def get_global_keywords(self):
    return keywords

def get_global_intensify_keywords(self):
    return intensify_keywords