import os
import time
import random
from google import genai
import requests
import feedparser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
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

    prompt_kantor_ai = f"""
    Anda adalah seorang content creator dan scriptwriter TikTok/Reels papan atas di niche {niche_aktif}. Tugas lu meracik berita mentah ini jadi materi konten yang renyah, tajam, dan gampang viral. 
    Bahan berita:
    "{berita_mentah}"

    Gunakan format struktur di bawah ini:

    [AGENT 1: TREND & DATA ANALYST]
    - Bongkar inti berita ini dengan bahasa analitis tapi ringkas. 
    - Apa dampak riilnya buat dompet atau teknologi keseharian orang? Kasih lihat datanya.

    [AGENT 2: VIRAL SCRIPTWRITER (TIKTOK/REELS STYLE)]
    - Tulis skrip video pendek (durasi 30-45 detik) dengan gaya bahasa lisan (spoken language) anak muda/gaul masa kini (pake sapaan santai, logis, to the point, gak kaku kayak skripsi).
    - **HOOK (0-3 detik pertama):** Harus pakai kalimat provokatif, bikin penasaran, atau langsung nyerang *pain point* penonton supaya mereka berhenti *scroll*.
    - **ISI:** Penjelasan inti yang cepat, padat, dan pakai analogi gampang dicerna. 
    - **CTA (Call to Action):** Kalimat penutup yang memancing orang komen atau nge-save video.

    [AGENT 3: SOCIAL MEDIA MANAGER]
    - Buat *caption* postingan yang santai tapi memancing diskusi di kolom komentar.
    - Sediakan 5-7 hashtag populer dan relevan.
    - Kasih ide visual B-roll (rekaman pendukung) yang pas buat diedit di CapCut.
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
    
    pesan_header = f"🚀 **KANTOR AI MEDIA [{niche_aktif.upper()}]** 🚀\n\n📌 **Judul:** {judul}\n🔗 **Sumber:** {link}\n\n"
    full_content = pesan_header + hasil_akhir
    
    chunks = [full_content[i:i+1900] for i in range(0, len(full_content), 1900)]
    
    success = True
    for chunk in chunks:
        payload = {"content": chunk}
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
        if response.status_code not in [200, 204]:
            print(f"❌ Gagal kirim ke Discord: {response.text}")
            success = False
            break

    if success:
        print("✅ BERHASIL! Laporan redaksi lengkap terkirim ke Discord.")
        save_seen_url(link)

except Exception as e:
    print(f"❌ TERJADI KESALAHAN: {e}")
