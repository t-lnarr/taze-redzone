import os
import json
import sqlite3
import threading
from datetime import datetime
import google.generativeai as genai
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters
)
import logging

# Logging ayarları
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# API anahtarları
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

if not GEMINI_API_KEY or not TELEGRAM_TOKEN:
    raise ValueError("API anahtarları eksik! GEMINI_API_KEY ve TELEGRAM_TOKEN çevresel değişkenlerini ayarlayın.")

# Gemini yapılandırması
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(model_name="models/gemini-1.5-flash")

# Thread-safe hafıza
USER_MEMORY = {}
memory_lock = threading.Lock()
MAX_HISTORY = 5

BLACKLIST = [
    "din", "allah", "jeset", "syýasy", "porn", "ýarag", "intihar", "öldür", "adam öldür",
    "ýaradyjy", "Ýahudy", "Hristian", "Musulman", "Ilon Mask"
]

# İşletme Bilgisi (aynı kalıyor)
ISLETME_BILGI = """
<b>🤖 Redzone AI</b> — Pubg Mobile oýunyndaky UC (Unknown Cash) satyn almakda siziň iň gowy kömekçiňiz!

🔰 <b>UC näme we näme üçin gerek?</b>
UC — Pubg Mobile'daky ähli aýratynlyklaryň, skinleriň, Royal Passlaryň we beýleki premium hyzmatlaryň açarydyr. Oýun içinde tapawutlanmak, öz stiliňizi görkezmek we doly mümkinçiliklerden peýdalanmak üçin UC zerur!

🎯 <b>Näme üçin Redzone saýlamaly?</b>
✔️ <b>Tiz hyzmat:</b> Sargytlaryňyz gysga wagtyň içinde ýerine ýetirilýär.
✔️ <b>Ynamdar hyzmat:</b> Müşderilerimiziň ynamy we razylygy biziň üçin birinji ýerde durýar.
✔️ <b>Amatly bahalar:</b> Bäsdeşlerden has arzan we elýeterli nyrhlar.
✔️ <b>Müşderi goldawy:</b> Islendik soraga AI + hakyky işgärler bilen çalt we takyk jogap.
✔️ <b>Yzygiderli aksiýalar:</b> Wagtal-wagtal arzanladyşlar, bonuslar we aýratyn teklipler!
✔️ <b>Mobil programma:</b> Aragatnaşyk, sargyt we UC bahalary bir ýerde!

📲 <b>Mobil programmamyzy şu ýerden ýükläň:</b>
<a href="https://redzonegg.com/app-release.apk">⬇️ Redzone.apk — Ýükle!</a>

📞 <b>Satyn almak üçin jaň ediň:</b>
📱 +99362251883
📱 +99361365984

🌐 <b>Web saýdymyz:</b>
<a href="https://redzonegg.com">🔗 redzonegg.com</a>

📱 <b>Sosial mediada bizi tap:</b>
• Instagram: @redzone_official
• TikTok: @redzone_gg_official
• Telegram: @redZone_gg

💸 <b>Telefon bilen töleg arkaly UC bahalary:</b>
▫️ 60 UC = 25 TMT
▫️ 325 UC = 120 TMT
▫️ 660 UC = 240 TMT
▫️ 1800 UC = 600 TMT
▫️ 3850 UC = 1200 TMT
▫️ 8100 UC = 2300 TMT

💵 <b>Nagt töleg arkaly UC bahalary:</b>
▫️ 60 UC = 19 TMT
▫️ 325 UC = 98 TMT
▫️ 660 UC = 193 TMT
▫️ 1800 UC = 480 TMT
▫️ 3850 UC = 960 TMT
▫️ 8100 UC = 1920 TMT

💬 <b>Soraglaryňyz barmy?</b>
Meni soragyňyz bilen synap görüň!
Men — <b>Redzone AI</b> — sizi ýalňyz galdyrmajak söýgüli kömekçiňiz 😄

Men — Redzone komandasy tarapyndan, size iň oňat hyzmaty bermek we islendik soraglaryňyza çalt kömek etmek üçin döredilen dostuňyz.
"""

# İyileştirilmiş veritabanı kurulumu
def init_database():
    try:
        conn = sqlite3.connect('bot_analytics.db')
        cursor = conn.cursor()

        # Kullanıcılar tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                first_interaction TEXT,
                last_interaction TEXT,
                total_messages INTEGER DEFAULT 0
            )
        ''')

        # Mesajlar tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                message TEXT,
                response TEXT,
                timestamp TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')

        conn.commit()
        logger.info("Veritabanı başarıyla kuruldu")

    except sqlite3.Error as e:
        logger.error(f"Veritabanı kurulum hatası: {e}")
        raise
    finally:
        if conn:
            conn.close()

# İyileştirilmiş kullanıcı etkileşimi kaydetme
def save_user_interaction(user_id, username, first_name, last_name, message, response):
    conn = None
    try:
        conn = sqlite3.connect('bot_analytics.db')
        cursor = conn.cursor()

        current_time = datetime.now().isoformat()

        # Kullanıcı bilgilerini güncelle veya ekle
        cursor.execute('''
            INSERT OR REPLACE INTO users
            (user_id, username, first_name, last_name, first_interaction, last_interaction, total_messages)
            VALUES (?, ?, ?, ?,
                    COALESCE((SELECT first_interaction FROM users WHERE user_id = ?), ?),
                    ?,
                    COALESCE((SELECT total_messages FROM users WHERE user_id = ?), 0) + 1)
        ''', (user_id, username, first_name, last_name, user_id, current_time, current_time, user_id))

        # Mesajı kaydet
        cursor.execute('''
            INSERT INTO messages (user_id, username, message, response, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, message, response, current_time))

        conn.commit()

    except sqlite3.Error as e:
        logger.error(f"Veritabanı kayıt hatası: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

# Thread-safe hafıza yönetimi
def get_user_memory(user_id):
    with memory_lock:
        return USER_MEMORY.get(user_id, []).copy()

def update_user_memory(user_id, message):
    with memory_lock:
        if user_id not in USER_MEMORY:
            USER_MEMORY[user_id] = []
        USER_MEMORY[user_id].append(message)
        USER_MEMORY[user_id] = USER_MEMORY[user_id][-MAX_HISTORY:]

# İyileştirilmiş admin komutları
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_ids = [7172270461]  # Admin user ID'lerini buraya ekleyin

    if update.effective_user.id not in admin_ids:
        await update.message.reply_text("Bu komut için yetkiniz yok.")
        return

    conn = None
    try:
        conn = sqlite3.connect('bot_analytics.db')
        cursor = conn.cursor()

        # Genel istatistikler
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM messages')
        total_messages = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM users WHERE date(last_interaction) = date("now")')
        today_active = cursor.fetchone()[0]

        # En aktif kullanıcılar
        cursor.execute('''
            SELECT username, first_name, total_messages
            FROM users
            ORDER BY total_messages DESC
            LIMIT 5
        ''')
        top_users = cursor.fetchall()

        stats_text = f"""
📊 <b>Bot İstatistikleri</b>

👥 <b>Toplam Kullanıcı:</b> {total_users}
💬 <b>Toplam Mesaj:</b> {total_messages}
🔥 <b>Bugün Aktif:</b> {today_active}

🏆 <b>En Aktif Kullanıcılar:</b>
"""

        for i, (username, first_name, msg_count) in enumerate(top_users, 1):
            name = first_name or username or "Bilinmiyor"
            stats_text += f"{i}. {name}: {msg_count} mesaj\n"

        await update.message.reply_text(stats_text, parse_mode="HTML")

    except sqlite3.Error as e:
        logger.error(f"İstatistik alma hatası: {e}")
        await update.message.reply_text("İstatistik alınırken hata oluştu.")
    finally:
        if conn:
            conn.close()

async def admin_recent_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_ids = [7172270461]

    if update.effective_user.id not in admin_ids:
        await update.message.reply_text("Bu komut için yetkiniz yok.")
        return

    conn = None
    try:
        conn = sqlite3.connect('bot_analytics.db')
        cursor = conn.cursor()

        cursor.execute('''
            SELECT u.username, u.first_name, m.message, m.timestamp
            FROM messages m
            JOIN users u ON m.user_id = u.user_id
            ORDER BY m.timestamp DESC
            LIMIT 10
        ''')

        recent_messages = cursor.fetchall()
        messages_text = "📝 <b>Son 10 Mesaj:</b>\n\n"

        for username, first_name, message, timestamp in recent_messages:
            name = first_name or username or "Bilinmiyor"
            short_message = message[:50] + "..." if len(message) > 50 else message
            time_str = datetime.fromisoformat(timestamp).strftime("%d.%m %H:%M")
            messages_text += f"👤 <b>{name}</b> ({time_str}):\n{short_message}\n\n"

        await update.message.reply_text(messages_text, parse_mode="HTML")

    except sqlite3.Error as e:
        logger.error(f"Son mesajları alma hatası: {e}")
        await update.message.reply_text("Mesajlar alınırken hata oluştu.")
    finally:
        if conn:
            conn.close()

# /start komutu
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_message(update, context, override_message="sen kim ?")

# İyileştirilmiş mesaj işleme
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, override_message=None):
    try:
        # Grup kontrolü
        if update.message.chat.type in ['group', 'supergroup']:
            if not context.bot.username.lower() in update.message.text.lower():
                return

        user_id = update.effective_user.id
        username = update.effective_user.username
        first_name = update.effective_user.first_name
        last_name = update.effective_user.last_name

        user_message = override_message or update.message.text
        user_message = user_message.replace(f"@{context.bot.username}", "").strip()

        # Uygulama indirme istekleri
        if any(keyword in user_message.lower() for keyword in ["programmany nädip alyp bolar", "apk", "ýükle"]):
            download_link = "https://redzonegg.com/app-release.apk"
            reply_text = (
                "📲 <b>Redzone programmasyny şu ýerden ýükläp bilersiňiz:</b>\n"
                f'<a href="{download_link}">⬇️ Redzone.apk ýükle</a>'
            )
            await update.message.reply_text(reply_text, parse_mode="HTML")
            save_user_interaction(user_id, username, first_name, last_name, user_message, reply_text)
            return

        # Yasaklı kelime filtresi
        if any(term in user_message.lower() for term in BLACKLIST):
            response_text = "Bagyşlaň, bu tema boýunça kömek edip bilemok."
            await update.message.reply_text(response_text)
            save_user_interaction(user_id, username, first_name, last_name, user_message, response_text)
            return

        # Özel komut işleme
        if user_message.lower() in ["sen kim ?", "özüňi tanat", "who are you"]:
            user_message = "Redzone AI kim? Bize biraz özüň hakda gürrüň ber."

        # Thread-safe hafıza işlemi
        previous = get_user_memory(user_id)
        update_user_memory(user_id, f"Ulanyjy: {user_message}")
        history_text = "\n".join(get_user_memory(user_id))

        prompt = (
            f"{ISLETME_BILGI}\n\n"
            f"Dost bilen gepleşik:\n{history_text}\n\n"
            f"Täze sorag:\n{user_message}\n\n"
            f"⚠️ Edebe laýyk we umumy maglumatlara jogap ber, dini/syýasy/ahlakdan daş temalardan gaç. "
            f"Jogap bereniňde gerek bolsa 'Dost' diýip gürleş we gysga ýöne dogry jogap ber. "
            f"Bilmedik, düşünmedik soragyň berilende 'Bagyşlaň, soragyňyza düşünmedim. Başga bir soragyňyz barmy?' diý. Emojiler ulan."
        )

        try:
            response = model.generate_content(prompt)
            bot_reply = response.text if response.text else "Bagyşlaň, jogap ýazyp bilemok."
        except Exception as e:
            logger.error(f"AI model hatası: {e}")
            bot_reply = "Bagyşlaň, häzirki wagtda näsazlyk ýüze çykdy. Soňra synap görüň."

        # Hafızaya bot cevabını ekle
        update_user_memory(user_id, f"Redzone AI: {bot_reply}")

        # Etkileşimi kaydet
        save_user_interaction(user_id, username, first_name, last_name, user_message, bot_reply)

        await update.message.reply_text(bot_reply, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Mesaj işleme hatası: {e}")
        await update.message.reply_text("Bagyşlaň, bir hata ýüze çykdy.")

# Ana program
if __name__ == "__main__":
    try:
        print("Veritabanı başlatılıyor...")
        init_database()
        print("Bot işleýär... Synap görüň!")

        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

        # Handler'ları ekle
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("stats", admin_stats))
        app.add_handler(CommandHandler("recent", admin_recent_messages))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        app.run_polling()

    except Exception as e:
        logger.error(f"Bot başlatma hatası: {e}")
        print(f"Bot başlatılırken hata: {e}")
