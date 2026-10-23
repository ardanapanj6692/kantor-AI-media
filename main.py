import os
import time
import random
from google import genai
import requests
import feedparser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

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
    # Daftar Niche Pilihan: Keuangan & Teknologi
    target_niches = [
        {"niche": "Keuangan & Bisnis", "url": "https://www.antaranews.com/rss/ekonomi.xml"},
        {"niche": "Teknologi & Sains", "url": "https://www.antaranews.com/rss/tekno.xml"}
    ]
    
    # Pilih salah satu niche secara acak setiap script berjalan
    pilihan = random.choice(target_niches)
    niche_aktif = pilihan["niche"]
    rss_url = pilihan["url"]
    
    print(f"🎯 Niche Terpilih Sesi Ini: {niche_aktif}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    rss_content = fetch_rss_with_retry(rss_url, headers)
    feed = feedparser.parse(rss_content)
    
    if not feed.entries:
        raise Exception("RSS Feed terbaca kosong atau strukturnya berubah.")
        
    artikel_terbaru = feed.entries[0]
    judul = artikel_terbaru.title
    deskripsi = artikel_terbaru.summary if 'summary' in artikel_terbaru else ""
    
    berita_mentah = f"Niche: {niche_aktif}\nJudul: {judul}\nIsi Ringkas: {deskripsi}"
    print(f"📰 Berita Berhasil Ditarik: {judul}")

    print("⏳ Menghubungkan ke Gemini API...")
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt_kantor_ai = f"""
    Anda adalah sistem Multi-Agent Kantor Virtual Media yang berfokus pada analisis mendalam untuk niche {niche_aktif}. Olah berita mentah berikut:
    "{berita_mentah}"

    Jalankan tugas berurutan berikut secara profesional dan tajam:
    [AGENT 1: TREND & DATA ANALYST]
    Ekstrak 3 poin inti, implikasi pasar/industri, serta data angka/fakta kunci dari berita di atas.
    [AGENT 2: VIRAL SCRIPTWRITER]
    Buatkan skrip konten video pendek (TikTok/Reels/Shorts) durasi 30-45 detik dengan struktur Hook yang kuat, Isi yang padat informasi, dan Call to Action yang relevan.
    [AGENT 3: SOCIAL MEDIA MANAGER]
    Buatkan caption profesional, 5 hashtag tertarget, dan 3 prompt visual B-roll yang mendukung.
    """

    print("🤖 Pekerja AI sedang meracik konten...")
    response = client.models.generate_content(
        model='gemini-3.8-flash',
        contents=prompt_kantor_ai
    )
    hasil_akhir = response.text

    print("📤 Mengirim hasil ke Telegram...")
    url_telegram = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": f"🚀 KANTOR AI MEDIA [{niche_aktif.upper()}] 🚀\n\n📌 Judul: {judul}\n\n{hasil_akhir}"
    }

    kirim = requests.post(url_telegram, data=payload, timeout=15)

    if kirim.status_code == 200:
        print("✅ BERHASIL! Pesan terkirim.")
    else:
        print(f"❌ Gagal ke Telegram: {kirim.text}")

except Exception as e:
    print(f"❌ TERJADI KESALAHAN: {e}")
