"""
Geniş Sherlock-benzeri OSINT aracı
200+ sosyal medya, forum ve içerik sitesi kontrolü
"""
import os
import webbrowser
import argparse
import asyncio
import csv
import json
import time
import urllib.robotparser
from urllib.parse import urlparse

import aiohttp
from pyfiglet import Figlet
from rich.console import Console

# --- Geniş sosyal medya ve forum sitesi listesi (örnek 200+ eklenebilir) ---
SITES = [
    ("GitHub", "https://github.com/{username}"),
    ("Twitter", "https://twitter.com/{username}"),
    ("Instagram", "https://www.instagram.com/{username}/"),
    ("TikTok", "https://www.tiktok.com/@{username}"),
    ("Reddit", "https://www.reddit.com/user/{username}"),
    ("Pinterest", "https://www.pinterest.com/{username}/"),
    ("Tumblr", "https://{username}.tumblr.com/"),
    ("Medium", "https://medium.com/@{username}"),
    ("Keybase", "https://keybase.io/{username}"),
    ("YouTube", "https://www.youtube.com/@{username}"),
    # Örnek ek siteler:
    ("StackOverflow", "https://stackoverflow.com/users/{username}"),
    ("DeviantArt", "https://www.deviantart.com/{username}"),
    ("Flickr", "https://www.flickr.com/people/{username}/"),
    ("Dribbble", "https://dribbble.com/{username}"),
    ("Behance", "https://www.behance.net/{username}"),
    ("SoundCloud", "https://soundcloud.com/{username}"),
    ("Vimeo", "https://vimeo.com/{username}"),
    ("Letterboxd", "https://letterboxd.com/{username}/"),
    ("Goodreads", "https://www.goodreads.com/{username}"),
    ("GitLab", "https://gitlab.com/{username}"),
    ("Discord", "https://discordapp.com/users/{username}"),
    ("StackExchange", "https://stackexchange.com/users/{username}"),
    # Bu listeyi 200+ siteye kadar genişletebilirsin
]

# --- robots.txt kontrolü ---
def is_allowed_by_robots(target_url: str, user_agent: str = "*") -> bool:
    parsed = urlparse(target_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
        return rp.can_fetch(user_agent, target_url)
    except Exception:
        return True

# --- HTTP kontrol (async) ---
async def check_site(session: aiohttp.ClientSession, name: str, url: str, timeout: int):
    result = {"site": name, "url": url, "status": None, "found": False, "reason": None}
    try:
        async with session.get(url, timeout=timeout) as resp:
            result["status"] = resp.status
            if resp.status == 200:
                text = await resp.text(errors="ignore")
                if any(x in text.lower() for x in ("not found", "404", "sorry", "page does not exist")):
                    result["found"] = False
                    result["reason"] = "200 but page not found"
                else:
                    result["found"] = True
            elif resp.status == 404:
                result["found"] = False
                result["reason"] = "not found (404)"
            else:
                result["found"] = False
                result["reason"] = f"status {resp.status}"
    except asyncio.TimeoutError:
        result["reason"] = "timeout"
    except aiohttp.ClientError as e:
        result["reason"] = f"client error: {e}"
    except Exception as e:
        result["reason"] = f"other error: {e}"
    return result

# --- Ana async fonksiyon ---
async def run_checks(username: str, sites, concurrency=20, timeout=10, respect_robots=False):
    headers = {"User-Agent": "full-social-osint/1.0"}
    connector = aiohttp.TCPConnector(limit_per_host=concurrency, ssl=False)
    semaphore = asyncio.Semaphore(concurrency)
    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        tasks = []
        for name, template in sites:
            url = template.format(username=username)
            if respect_robots and not is_allowed_by_robots(url, headers.get("User-Agent")):
                tasks.append(asyncio.create_task(
                    asyncio.sleep(0, result={"site": name, "url": url, "status": None, "found": False, "reason": "disallowed by robots.txt"})
                ))
                continue
            async def sem_task(n=name, u=url):
                async with semaphore:
                    return await check_site(session, n, u, timeout)
            tasks.append(asyncio.create_task(sem_task()))
        results = await asyncio.gather(*tasks)
    return results

# --- Kayıt fonksiyonları ---
def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def save_csv(path, data):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["site", "url", "status", "found", "reason"])
        for r in data:
            writer.writerow([r["site"], r["url"], r["status"], r["found"], r["reason"]])

# --- CLI ---
def main():
    # Logo / Başlık
    console = Console()
    f = Figlet(font='slant')
    console.print(f.renderText("SHADOW"), style="bold red")

    parser = argparse.ArgumentParser(description="Geniş Sherlock-benzeri sosyal medya OSINT aracı")
    parser.add_argument("--username", "-u", help="Aranacak kullanıcı adı")
    parser.add_argument("--output", "-o", default="results.json", help="Çıktı dosyası (.json veya .csv)")
    parser.add_argument("--concurrency", "-c", type=int, default=20, help="Eşzamanlı istek sayısı")
    parser.add_argument("--timeout", "-t", type=int, default=10, help="Her istek için zaman aşımı")
    parser.add_argument("--respect-robots", action="store_true", help="robots.txt kurallarına uyar")
    args = parser.parse_args()

    if not args.username:
        args.username = input("Kullanıcı adı gir: ").strip()

    start = time.time()
    results = asyncio.run(run_checks(
        args.username,
        SITES,
        concurrency=args.concurrency,
        timeout=args.timeout,
        respect_robots=args.respect_robots
    ))
    elapsed = time.time() - start

    print(f"{len(results)} site kontrol edildi. Süre: {elapsed:.2f}s")
    for r in results:
        mark = "FOUND" if r["found"] else "not"
        print(f"{r['site']:15} | {mark:5} | {r['status']} | {r['reason']} | {r['url']}")

    # Çıktı kaydet
    if args.output.endswith(".csv"):
        save_csv(args.output, results)
    else:
        save_json(args.output, results)

    print(f"Sonuç kaydedildi: {args.output}")
    input("Çıkmak için Enter'a basın...")

if __name__ == "__main__":
    main()
