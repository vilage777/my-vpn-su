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
SOURCE_URL = "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/mixed.txt"
OUTPUT_FILE = "sub.txt"
TOP_PER_COUNTRY = 10
MAX_PING = 2000 # Высокий порог, чтобы точно нашлось
TIMEOUT = 2.0

# Чтобы нас не блокировали
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def parse_config_info(config):
    try:
        ip, port, name = None, None, ""
        if config.startswith("vmess://"):
            b64 = config[8:]
            pad = len(b64) % 4
            if pad: b64 += '=' * (4 - pad)
            data = json.loads(base64.b64decode(b64).decode('utf-8', errors='ignore'))
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
    return flags[0] if flags else "🏳️ World"

def check_ping(ip, port):
    if not ip or not port: return 9999
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT)
        start = time.time()
        res = sock.connect_ex((ip, int(port)))
        sock.close()
        if res == 0:
            return int((time.time() - start) * 1000)
    except:
        pass
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
    print("🚀 Starting...")
    lines = []
    try:
        resp = requests.get(SOURCE_URL, headers=HEADERS, timeout=30)
        content = resp.text
        # Простая проверка на base64
        if "vmess://" not in content and "vless://" not in content:
            try:
                content = base64.b64decode(content).decode('utf-8', errors='ignore')
            except: pass
        
        lines = list(set(content.strip().split('\n')))
        print(f"📥 Downloaded {len(lines)} configs.")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Ограничим для теста
    lines = lines[:800]
    
    valid_configs = []
    if lines:
        print("🔎 Checking...")
        with ThreadPoolExecutor(max_workers=50) as executor:
            results = executor.map(process_config, lines)
            for r in results:
                if r: valid_configs.append(r)
    
    print(f"✅ Found {len(valid_configs)} working.")

    if valid_configs:
        countries = {}
        for item in valid_configs:
            c = item['country']
            if c not in countries: countries[c] = []
            countries[c].append(item)

        final_list = []
        for c, items in countries.items():
            items.sort(key=lambda x: x['latency'])
            top = items[:TOP_PER_COUNTRY]
            for i in top: final_list.append(i['config'])
            
        result_text = "\n".join(final_list)
        result_b64 = base64.b64encode(result_text.encode('utf-8')).decode('utf-8')
    else:
        print("⚠️ Empty list, creating placeholder.")
        result_b64 = base64.b64encode(b"vmess://empty").decode('utf-8')

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(result_b64)
    print("💾 Done.")

if __name__ == "__main__":
    main()
