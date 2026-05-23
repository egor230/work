import re
import requests


SOURCES = [
    # GitHub raw списки
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",

    # сайты с MTProto (примерные)
    "https://mtpro.xyz/",
    "https://mtproto-proxy.com/",
]


def extract_mtproto(text):
    """Ищет MTProto ссылки и вытаскивает server/port/secret"""
    proxies = []

    pattern = r'(tg://proxy\?server=[^ \n]+|https://t\.me/proxy\?[^ \n]+)'
    matches = re.findall(pattern, text)

    for link in matches:
        clean = link.replace("&amp;", "&")

        server = re.search(r"server=([^&]+)", clean)
        port = re.search(r"port=([^&]+)", clean)
        secret = re.search(r"secret=([^&]+)", clean)

        if server and port and secret:
            proxies.append({
                "server": server.group(1),
                "port": int(port.group(1)),
                "secret": secret.group(1),
            })

    return proxies


def fetch_url(url):
    try:
        r = requests.get(url, timeout=10)
        return r.text
    except Exception as e:
        print(f"[ERROR] {url}: {e}")
        return ""


def main():
    all_proxies = []

    for url in SOURCES:
        print(f"[+] Проверяю {url}")
        content = fetch_url(url)

        proxies = extract_mtproto(content)
        all_proxies.extend(proxies)

    # удаление дублей
    unique = {}
    for p in all_proxies:
        key = (p["server"], p["port"], p["secret"])
        unique[key] = p

    proxies = list(unique.values())

    print(f"\nНайдено: {len(proxies)} MTProto прокси")

    with open("mtproto.txt", "w") as f:
        for p in proxies:
            f.write(f"{p['server']}:{p['port']}:{p['secret']}\n")

    print("Сохранено в mtproto.txt")


if __name__ == "__main__":
    main()