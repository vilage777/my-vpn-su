import requests
import base64
import json
import socket
import re
import time
from urllib.parse import urlparse, unquote
from concurrent.futures import ThreadPoolExecutor

# --- ТВОЯ ССЫЛКА ---
# Я преобразовал путь в прямую ссылку на Raw-файл
SOURCE_URL = "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/subscriptions/v2ray/all_sub.txt"

OUTPUT_FILE = "sub.txt"
TOP_PER_COUNTRY = 10
TIMEOUT = 2.0 # Таймаут проверки

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
            decoded = base64.b64decode(b64).decode('utf-8', errors='ignore')
            data = json.loads(decoded)
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
    # Оставляем только живые (пинг меньше 2000мс)
    if latency < 2000:
        return {"config": config, "latency": latency, "country": get_country_flag(name)}
    return None

def main():
    print(f"🚀 Downloading from: {SOURCE_URL}")
    lines = []
    
    try:
        resp = requests.get(SOURCE_URL, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            raise Exception(f"Status code: {resp.status_code}")
            
        content = resp.text.strip()
        
        # --- ВАЖНО: Декодирование ---
        # Файлы подписок обычно зашифрованы в Base64. Пробуем расшифровать.
        try:
            # Если это Base64 строка (без пробелов), декодируем
            if "vmess://" not in content and "vless://" not in content:
                decoded_content = base64.b64decode(content).decode('utf-8', errors='ignore')
                lines = decoded_content.split('\n')
                print("✅ Successfully decoded Base64 subscription.")
            else:
                # Если это просто текст
                lines = content.split('\n')
                print("✅ File is plain text.")
        except Exception as e:
            print(f"⚠️ Decode failed, trying as plain text. Error: {e}")
            lines = content.split('\n')

    except Exception as e:
        print(f"❌ Error downloading: {e}")
        # Если ошибка скачивания, создадим файл с ошибкой, чтобы Git не ругался
        with open(OUTPUT_FILE, "w") as f:
            f.write(base64.b64encode(b"vmess://ERROR_DOWNLOAD_CHECK_LOGS").decode())
        return

    # Чистим пустые строки
    lines = [x.strip() for x in lines if x.strip()]
    print(f"📥 Found {len(lines)} configs. Checking connectivity...")
    
    # Берем первые 2000 для проверки
    lines = lines[:2000]
    
    valid_configs = []
    with ThreadPoolExecutor(max_workers=50) as executor:
        results = executor.map(process_config, lines)
        for r in results:
            if r: valid_configs.append(r)
            
    print(f"✅ Working configs found: {len(valid_configs)}")

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
        print("⚠️ No working configs found in this file.")
        result_b64 = base64.b64encode(b"vmess://NO_WORKING_CONFIGS_FOUND").decode('utf-8')

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(result_b64)
    
    print("💾 File saved.")

if __name__ == "__main__":
    main()
