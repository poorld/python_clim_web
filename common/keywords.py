#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
from common.logger import get_logger

logger = get_logger()
CONFIG_FILE = 'config.json'

def _load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def save_keyword(keyword):
    config = _load_config()
    keywords = config.get('KEYWORDS', [])
    if keyword not in keywords:
        keywords.append(keyword)
        config['KEYWORDS'] = keywords
        _save_config(config)
        logger.info(f"Added keyword: {keyword}")

def remove_keyword(keyword):
    config = _load_config()
    keywords = config.get('KEYWORDS', [])
    if keyword in keywords:
        keywords.remove(keyword)
        config['KEYWORDS'] = keywords
        _save_config(config)
        logger.info(f"Removed keyword: {keyword}")

def load_keywords():
    return _load_config().get('KEYWORDS', [])

def get_global_keywords():
    return load_keywords()
