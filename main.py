import requests
import base64
import json
import socket
import re
import time
import os
from urllib.parse import urlparse, unquote
from concurrent.futures import ThreadPoolExecutor

# --- НАСТРОЙКИ ---
SOURCE_URL = "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/all_configs.txt"
OUTPUT_FILE = "sub.txt" # Имя файла подписки
TOP_PER_COUNTRY = 10
MAX_PING = 700

def parse_config_info(config):
    try:
        ip, port, name = None, None, ""
        if config.startswith("vmess://"):
            b64 = config[8:]
            missing_padding = len(b64) % 4
            if missing_padding: b64 += '=' * (4 - missing_padding)
            data = json.loads(base64.b64decode(b64).decode('utf-8'))
            ip = data.get("add")
            port = data.get("port")
            name = data.get("ps", "")
        elif config.startswith("vless://") or config.startswith("trojan://") or config.startswith("ss://"):
            parsed = urlparse(config)
            ip = parsed.hostname
            port = parsed.port
            name = unquote(parsed.fragment) if parsed.fragment else ""
        return ip, port, name
    except:
        return None, None, None

def get_country_flag(name):
    flags = re.findall(r'[\U0001F1E6-\U0001F1FF]{2}', name)
    return flags[0] if flags else "🏳️ Other"

def check_ping(ip, port):
    if not ip or not port: return 9999
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.0) # Быстрый таймаут (1 сек)
        start = time.time()
        res = sock.connect_ex((ip, int(port)))
        sock.close()
        if res == 0: return int((time.time() - start) * 1000)
    except: pass
    return 9999

def process_config(config):
    config = config.strip()
    if not config: return None
    ip, port, name = parse_config_info(config)
    if not ip: return None
    
    latency = check_ping(ip, port)
    if latency < MAX_PING:
        return {"config": config, "latency": latency, "country": get_country_flag(name)}
    return None

def main():
    print("Download configs...")
    try:
        resp = requests.get(SOURCE_URL)
        # Если пришло в base64
        if "vmess" not in resp.text and "vless" not in resp.text:
             content = base64.b64decode(resp.text).decode('utf-8')
        else:
             content = resp.text
        lines = list(set(content.strip().split('\n')))
    except:
        return

    # Ограничиваем кол-во для проверки, чтобы уложиться в лимиты GitHub Free
    # Берем последние 1000 (обычно они свежее)
    lines = lines[:1000]

    valid = []
    with ThreadPoolExecutor(max_workers=40) as executor:
        results = executor.map(process_config, lines)
        for r in results:
            if r: valid.append(r)

    # Группировка
    countries = {}
    for item in valid:
        c = item['country']
        if c not in countries: countries[c] = []
        countries[c].append(item)

    final_configs = []
    for c, items in countries.items():
        items.sort(key=lambda x: x['latency'])
        top = items[:TOP_PER_COUNTRY]
        for i in top: final_configs.append(i['config'])
    
    # Кодируем в Base64 для подписки
    result_text = "\n".join(final_configs)
    result_b64 = base64.b64encode(result_text.encode('utf-8')).decode('utf-8')
    
    with open(OUTPUT_FILE, "w") as f:
        f.write(result_b64)
    print(f"Done. Saved {len(final_configs)} configs.")

if __name__ == "__main__":
    main()
