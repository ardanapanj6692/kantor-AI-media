import os
import time
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
            print(f"⏳ Mengambil berita (Percobaan {attempt+1}/{retries})...")
            response = session.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                return response.content
        except Exception as e:
            print(f"⚠️ Koneksi terputus: {e}, mencoba ulang dalam 3 detik...")
            time.sleep(3)
    raise Exception("Gagal total mengakses RSS setelah beberapa kali percobaan.")

try:
    rss_url = "https://www.antaranews.com/rss/terkini.xml"
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
    
    berita_mentah = f"Judul: {judul}\nIsi Ringkas: {deskripsi}"
    print(f"📰 Berita Berhasil Ditarik: {judul}")

    print("⏳ Menghubungkan ke Gemini API...")
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt_kantor_ai = f"""
    Anda adalah sistem Multi-Agent Kantor Virtual Media. Olah berita mentah berikut:
    "{berita_mentah}"

    Jalankan tugas berurutan berikut:
    [AGENT 1: TREND ANALYST]
    Ekstrak 3 poin inti & data angka/fakta kunci dari berita di atas.
    [AGENT 2: VIRAL SCRIPTWRITER]
    Buatkan skrip video pendek (TikTok/Shorts) durasi 30-45 detik dengan struktur Hook, Isi, dan Call to Action.
    [AGENT 3: SOCIAL MEDIA MANAGER]
    Buatkan caption singkat, 5 hashtag relevan, dan 3 prompt visual B-roll.
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
        "text": f"🚀 HASIL KERJA KANTOR AI MEDIA 🚀\n\n📌 Judul Berita Asli: {judul}\n\n{hasil_akhir}"
    }

    kirim = requests.post(url_telegram, data=payload, timeout=15)

    if kirim.status_code == 200:
        print("✅ BERHASIL! Pesan terkirim.")
    else:
        print(f"❌ Gagal ke Telegram: {kirim.text}")

except Exception as e:
    print(f"❌ TERJADI KESALAHAN: {e}")
