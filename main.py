import os
import json
import sqlite3
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

# API anahtarları
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Gemini yapılandırması
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(model_name="models/gemini-1.5-flash")

# Hafıza ve blacklist
USER_MEMORY = {}
MAX_HISTORY = 5

BLACKLIST = [
    "din", "allah", "jeset", "syýasy", "porn", "ýarag", "intihar", "öldür", "adam öldür",
    "ýaradyjy", "Ýahudy", "Hristian", "Musulman", "Ilon Mask"
]

# İşletme Bilgisi
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

# Veritabanı kurulumu
def init_database():
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
    conn.close()

# Kullanıcı ve mesaj kaydetme
def save_user_interaction(user_id, username, first_name, last_name, message, response):
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
    conn.close()

# Admin komutları
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Sadece belirli admin kullanıcılar için (isteğe bağlı)
    admin_ids = [7172270461]  # Admin user ID'lerini buraya ekleyin

    if update.effective_user.id not in admin_ids:
        await update.message.reply_text("Bu komut için yetkiniz yok.")
        return

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

    conn.close()

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

async def admin_recent_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Admin kontrolü
    admin_ids = [7172270461]  # Admin user ID'lerini buraya ekleyin

    if update.effective_user.id not in admin_ids:
        await update.message.reply_text("Bu komut için yetkiniz yok.")
        return

    conn = sqlite3.connect('bot_analytics.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT username, first_name, message, timestamp
        FROM messages m
        JOIN users u ON m.user_id = u.user_id
        ORDER BY timestamp DESC
        LIMIT 10
    ''')

    recent_messages = cursor.fetchall()
    conn.close()

    messages_text = "📝 <b>Son 10 Mesaj:</b>\n\n"

    for username, first_name, message, timestamp in recent_messages:
        name = first_name or username or "Bilinmiyor"
        # Mesajı kısalt
        short_message = message[:50] + "..." if len(message) > 50 else message
        time_str = datetime.fromisoformat(timestamp).strftime("%d.%m %H:%M")
        messages_text += f"👤 <b>{name}</b> ({time_str}):\n{short_message}\n\n"

    await update.message.reply_text(messages_text, parse_mode="HTML")

# /start komutu işlendiğinde kullanıcı sanki "kendini tanit" yazmış gibi davran
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Direkt özel bir mesajla yönlendir
    await handle_message(update, context, override_message="sen kim ?")

# Mesaj işleme fonksiyonu
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, override_message=None):
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
    if "Programmany nädip alyp bolar" in user_message.lower() or "apk" in user_message.lower():
        download_link = "https://redzonegg.com/app-release.apk"
        reply_text = (
            "📲 <b>Redzone programmasyny şu ýerden ýükläp bilersiňiz:</b>\n"
            f'<a href="{download_link}">⬇️ Redzone.apk ýükle</a>'
        )
        await update.message.reply_text(reply_text, parse_mode="HTML")
        # Etkileşimi kaydet
        save_user_interaction(user_id, username, first_name, last_name, user_message, reply_text)
        return

    # Yasaklı kelime filtresi
    if any(term in user_message.lower() for term in BLACKLIST):
        response_text = "Bagyşlaň, bu tema boýunça kömek edip bilemok."
        await update.message.reply_text(response_text)
        # Etkileşimi kaydet
        save_user_interaction(user_id, username, first_name, last_name, user_message, response_text)
        return

    # 'kendini tanit' gibi komutlara özel muamele
    if user_message.lower() in ["sen kim ?", "özüňi tanat", "who are you"]:
        user_message = "Redzone AI kim? Bize biraz özüň hakda gürrüň ber."

    # Kullanıcı geçmişi
    previous = USER_MEMORY.get(user_id, [])
    previous.append(f"Ulanyjy: {user_message}")
    USER_MEMORY[user_id] = previous[-MAX_HISTORY:]
    history_text = "\n".join(USER_MEMORY[user_id])

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
        bot_reply = response.text or response.candidates[0].content.parts[0].text
    except Exception as e:
        print("Model hatasy:", e)
        bot_reply = "Bagyşlaň, näsazlyk ýüze çykdy."

    USER_MEMORY[user_id].append(f"Redzone AI: {bot_reply}")
    USER_MEMORY[user_id] = USER_MEMORY[user_id][-MAX_HISTORY:]

    # Etkileşimi veritabanına kaydet
    save_user_interaction(user_id, username, first_name, last_name, user_message, bot_reply)

    await update.message.reply_text(bot_reply, parse_mode="HTML")

# Ana program
if __name__ == "__main__":
    print("Veritabanı başlatılıyor...")
    init_database()
    print("Bot işleýär... Synap görüň!")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Komut ve mesaj handler'lar
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("recent", admin_recent_messages))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()
