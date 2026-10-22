!pip install -q google-genai requests feedparser

from google import genai
import requests
import feedparser

# ==========================================
# DATA LU
# ==========================================
GEMINI_API_KEY = "AQ.Ab8RN6KpiFWcmkSqU_zxui18QB_4TMKuMtZtfWik-YqttLvNYA"
TELEGRAM_BOT_TOKEN = "8331636234:AAERUaFAN3oyL-uG_lIQDGPEpQwniks4s0g"
TELEGRAM_CHAT_ID = "8189935997"

try:
    print("⏳ Mengambil berita terbaru dari internet (RSS Feed)...")
    # Mengambil berita otomatis dari RSS Feed CNBC Indonesia (Kanal Market)
    rss_url = "https://www.cnbcindonesia.com/market/rss"
    feed = feedparser.parse(rss_url)
    
    if not feed.entries:
        raise Exception("Gagal mengambil berita dari RSS Feed.")
        
    # Ambil artikel teratas (paling baru)
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
        "text": f"🚀 **HASIL KERJA KANTOR AI MEDIA** 🚀\n\n📌 **Judul Berita Asli:** {judul}\n\n{hasil_akhir}",
        "parse_mode": "Markdown"
    }

    kirim = requests.post(url_telegram, data=payload)

    if kirim.status_code == 200:
        print("✅ BERHASIL! Cek Telegram lu sekarang.")
    else:
        print(f"❌ Gagal ngirim ke Telegram. Pesan dari server Telegram: {kirim.text}")

except Exception as e:
    print(f"❌ TERJADI KESALAHAN: {e}")
