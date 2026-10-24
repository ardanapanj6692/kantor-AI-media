import os
import time
import random
import re
from datetime import datetime
from google import genai
import requests
import feedparser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
# Ganti dengan username dan nama repo GitHub lu
GITHUB_USERNAME = os.environ.get("GITHUB_REPOSITORY_OWNER", "your-username")
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "").split("/")[-1] or "your-repo"

LOG_FILE = "seen_urls.txt"
POSTS_DIR = "_posts"

os.makedirs(POSTS_DIR, exist_ok=True)

def load_seen_urls():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_seen_url(url):
    with open(LOG_FILE, "a") as f:
        f.write(f"{url}\n")

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s-]+', '-', text).strip('-')
    return text[:50]

def fetch_rss_with_retry(url, headers, retries=3):
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=2,
        status_forcelist=[500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    for attempt in range(retries):
        try:
            print(f"⏳ Mengambil berita ({url}) - Percobaan {attempt+1}/{retries}...")
            response = session.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                return response.content
        except Exception as e:
            print(f"⚠️ Koneksi terputus: {e}, mencoba ulang dalam 3 detik...")
            time.sleep(3)
    raise Exception(f"Gagal total mengakses RSS: {url}")

try:
    seen_urls = load_seen_urls()

    target_niches = [
        {"niche": "Keuangan & Bisnis", "url": "https://www.antaranews.com/rss/ekonomi.xml"},
        {"niche": "Teknologi & Sains", "url": "https://www.antaranews.com/rss/tekno.xml"}
    ]
    
    random.shuffle(target_niches)
    
    artikel_terpilih = None
    niche_aktif = ""

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    for item in target_niches:
        rss_content = fetch_rss_with_retry(item["url"], headers)
        feed = feedparser.parse(rss_content)
        
        for entry in feed.entries[:10]:
            link = entry.link
            if link not in seen_urls:
                artikel_terpilih = entry
                niche_aktif = item["niche"]
                break
        
        if artikel_terpilih:
            break

    if not artikel_terpilih:
        print("ℹ️ Tidak ada berita baru yang belum pernah dikirim. Skip eksekusi kali ini.")
        exit(0)

    judul = artikel_terpilih.title
    link = artikel_terpilih.link
    deskripsi = artikel_terpilih.summary if 'summary' in artikel_terpilih else ""
    
    print(f"🎯 Niche Terpilih: {niche_aktif}")
    print(f"📰 Berita BARU Ditarik: {judul}")

    berita_mentah = f"Niche: {niche_aktif}\nJudul: {judul}\nIsi Ringkas: {deskripsi}"

    print("⏳ Menghubungkan ke Gemini API...")
    client = genai.Client(api_key=GEMINI_API_KEY)

    # Prompt Khusus Nulis Artikel Artikel Blog Panjang + Teaser Sosmed
    prompt_kantor_ai = f"""
    Anda adalah jurnalis dan analis senior untuk portal berita media {niche_aktif}.
    Berdasarkan bahan berita mentah berikut:
    "{berita_mentah}"

    Tuliskan 2 OUTPUT TERPISAH secara presisi sesuai format delimiter berikut:

    ---ARTIKEL_BLOG---
    Buatkan artikel berita blog yang mendalam, komprehensif (minimal 600-800 kata), terstruktur, dan ramah SEO.
    Gunakan format Markdown lengkap dengan:
    - Judul yang menarik dan tajam
    - Paragraf Pembuka/Pendahuluan
    - Beberapa Sub-heading (##) untuk membagi topik
    - Poin-poin analisis data, dampak pasar/industri, dan opini ahli
    - Kesimpulan / Outlook ke depan
    (Jangan gunakan kata-kata AI generik, buat tulisan mengalir seperti jurnalis profesional)

    ---TEASER_TELEGRAM---
    Buatkan pesan ringkas (maksimal 150 kata) untuk grup Telegram sebagai teaser artikel di atas:
    - Hook pembuka yang bikin penasaran
    - 3 Poin penting / highlight
    - Kalimat ajakan "Baca selengkapnya di portal web kami:"
    """

    hasil_akhir = None
    for attempt in range(3):
        try:
            print(f"🤖 Pekerja AI sedang meracik artikel & teaser (Percobaan {attempt+1}/3)...")
            response = client.models.generate_content(
                model='gemini-3.8-flash',
                contents=prompt_kantor_ai
            )
            hasil_akhir = response.text
            break
        except Exception as ai_err:
            print(f"⚠️ Gemini sibuk/error: {ai_err}, mencoba ulang dalam 5 detik...")
            time.sleep(5)
            if attempt == 2:
                raise Exception("Gemini API gagal merespons setelah 3 kali percobaan.")

    # Parsing output artikel dan teaser
    parts = hasil_akhir.split("---TEASER_TELEGRAM---")
    isi_artikel = parts[0].replace("---ARTIKEL_BLOG---", "").strip()
    isi_teaser = parts[1].strip() if len(parts) > 1 else "Klik link di bawah untuk membaca artikel lengkap."

    # 1. Simpan Artikel ke Folder _posts untuk GitHub Pages
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%Y-%m-%d %H:%M:%S +0700")
    slug_judul = slugify(judul)
    filename = f"{POSTS_DIR}/{date_str}-{slug_judul}.md"

    # Frontmatter untuk Jekyll Blog
    markdown_content = f"""---
layout: post
title: "{judul.replace('"', '')}"
date: {time_str}
categories: [{niche_aktif.split()[0].lower()}]
---

{isi_artikel}
"""

    with open(filename, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    print(f"📝 Artikel blog berhasil dibuat: {filename}")

    # Buat URL Artikel Web
    post_url = f"https://{GITHUB_USERNAME}.github.io/{GITHUB_REPO}/{now.strftime('%Y/%m/%d')}/{slug_judul}.html"

    # 2. Kirim Teaser + Link Artikel ke Telegram
    print("📤 Mengirim teaser & link ke Telegram...")
    url_telegram = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    pesan_telegram = f"🚀 **UPDATE [{niche_aktif.upper()}]** 🚀\n\n{isi_teaser}\n\n👉 **Baca Artikel Selengkapnya:**\n{post_url}"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": pesan_telegram,
        "parse_mode": "Markdown"
    }

    kirim = requests.post(url_telegram, data=payload, timeout=15)

    if kirim.status_code == 200:
        print("✅ BERHASIL! Teaser terkirim ke Telegram.")
        save_seen_url(link)
    else:
        # Fallback jika parse Markdown Telegram error
        payload.pop("parse_mode", None)
        requests.post(url_telegram, data=payload, timeout=15)
        print("✅ BERHASIL! (Fallback mode biasa).")
        save_seen_url(link)

except Exception as e:
    print(f"❌ TERJADI KESALAHAN: {e}")
