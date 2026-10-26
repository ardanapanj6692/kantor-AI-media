import os
import time
import random
from google import genai
import requests
import feedparser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") # Masukin ini nanti di Secrets GitHub
LOG_FILE = "seen_urls.txt"

def load_seen_urls():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_seen_url(url):
    with open(LOG_FILE, "a") as f:
        f.write(f"{url}\n")

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

    # Prompt diperluas karena tidak ada batasan ketat 4000 karakter ala Telegram
    prompt_kantor_ai = f"""
    Anda adalah sistem Multi-Agent Kantor Virtual Media yang berfokus pada analisis mendalam untuk niche {niche_aktif}. Olah berita mentah berikut secara komprehensif, tajam, dan mendalam (tanpa perlu dibatasi jumlah kata):
    "{berita_mentah}"

    Jalankan tugas berurutan berikut dengan sangat detail:
    [AGENT 1: TREND & DATA ANALYST]
    - Ekstrak poin inti secara mendalam.
    - Bedah implikasi jangka panjang terhadap pasar, ekonomi, atau industri terkait.
    - Jabarkan data angka, statistik, atau fakta kunci yang ada.

    [AGENT 2: VIRAL SCRIPTWRITER]
    - Buatkan skrip konten video pendek (TikTok/Reels/Shorts) yang sangat matang.
    - Berikan pilihan Hook yang kuat (minimal 2 variasi).
    - Isi penjelasan yang padat dan bernilai tinggi.
    - Call to Action yang memancing interaksi.

    [AGENT 3: SOCIAL MEDIA MANAGER]
    - Buatkan draf caption profesional dan edukatif.
    - Sediakan 5-10 hashtag tertarget.
    - Berikan detail konsep visual atau prompt B-roll untuk editing video.
    """

    hasil_akhir = None
    for attempt in range(3):
        try:
            print(f"🤖 Pekerja AI sedang meracik konten lengkap (Percobaan {attempt+1}/3)...")
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

    print("📤 Mengirim hasil lengkap ke Discord...")
    
    # Discord mendukung batas hingga 2000 karakter per blok pesan, 
    # jadi kita pecah jika teksnya sangat panjang agar tidak error.
    pesan_header = f"🚀 **KANTOR AI MEDIA [{niche_aktif.upper()}]** 🚀\n\n📌 **Judul:** {judul}\n🔗 **Sumber:** {link}\n\n"
    
    # Gabungkan header dengan hasil AI
    full_content = pesan_header + hasil_akhir
    
    # Discord membatasi 2000 karakter per pesan, kirim secara aman
    chunks = [full_content[i:i+1900] for i in range(0, len(full_content), 1900)]
    
    success = True
    for chunk in chunks:
        payload = {"content": chunk}
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
        if response.status_code not in [200, 204]:
            print(f"❌ Gagal kirim ke Discord: {response.text}")
            success = false
            break

    if success:
        print("✅ BERHASIL! Laporan redaksi lengkap terkirim ke Discord.")
        save_seen_url(link)

except Exception as e:
    print(f"❌ TERJADI KESALAHAN: {e}")
