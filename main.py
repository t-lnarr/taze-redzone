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
from flask import Flask, render_template_string, jsonify

# API anahtarları
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Flask app
flask_app = Flask(__name__)

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

def get_db_connection():
    conn = sqlite3.connect('bot_analytics.db')
    conn.row_factory = sqlite3.Row
    return conn

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

# Flask Routes
@flask_app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

@flask_app.route('/api/stats')
def api_stats():
    conn = get_db_connection()

    # Genel istatistikler
    total_users = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    total_messages = conn.execute('SELECT COUNT(*) FROM messages').fetchone()[0]

    # Bugün aktif olan kullanıcılar
    today_active = conn.execute('''
        SELECT COUNT(*) FROM users
        WHERE date(last_interaction) = date("now")
    ''').fetchone()[0]

    # Bu hafta aktif olan kullanıcılar
    week_active = conn.execute('''
        SELECT COUNT(*) FROM users
        WHERE date(last_interaction) >= date("now", "-7 days")
    ''').fetchone()[0]

    # Günlük mesaj sayıları (son 7 gün)
    daily_messages = conn.execute('''
        SELECT date(timestamp) as date, COUNT(*) as count
        FROM messages
        WHERE date(timestamp) >= date("now", "-7 days")
        GROUP BY date(timestamp)
        ORDER BY date
    ''').fetchall()

    # En aktif kullanıcılar
    top_users = conn.execute('''
        SELECT username, first_name, total_messages
        FROM users
        ORDER BY total_messages DESC
        LIMIT 10
    ''').fetchall()

    # Son mesajlar
    recent_messages = conn.execute('''
        SELECT u.username, u.first_name, m.message, m.response, m.timestamp
        FROM messages m
        JOIN users u ON m.user_id = u.user_id
        ORDER BY m.timestamp DESC
        LIMIT 20
    ''').fetchall()

    conn.close()

    return jsonify({
        'total_users': total_users,
        'total_messages': total_messages,
        'today_active': today_active,
        'week_active': week_active,
        'daily_messages': [dict(row) for row in daily_messages],
        'top_users': [dict(row) for row in top_users],
        'recent_messages': [dict(row) for row in recent_messages]
    })

# Admin komutları
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Sadece belirli admin kullanıcılar için
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

    # Railway URL'ini dinamik olarak alın
    railway_url = os.environ.get('RAILWAY_STATIC_URL', 'localhost:5000')
    if not railway_url.startswith('http'):
        railway_url = f'https://{railway_url}'

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

    stats_text += f"\n🌐 <b>Detaylı analiz paneli:</b>\n{railway_url}"

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

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Redzone AI Bot - Analiz Paneli</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
            padding: 20px;
            background: rgba(255,255,255,0.1);
            border-radius: 20px;
            backdrop-filter: blur(10px);
        }

        .header h1 {
            font-size: 3rem;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }

        .header p {
            font-size: 1.2rem;
            opacity: 0.9;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 25px;
            margin-bottom: 40px;
        }

        .stat-card {
            background: linear-gradient(145deg, #ffffff, #f0f0f0);
            padding: 30px;
            border-radius: 20px;
            box-shadow: 0 15px 35px rgba(0,0,0,0.1);
            text-align: center;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }

        .stat-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #667eea, #764ba2);
        }

        .stat-card:hover {
            transform: translateY(-10px) scale(1.02);
            box-shadow: 0 25px 50px rgba(0,0,0,0.15);
        }

        .stat-number {
            font-size: 3rem;
            font-weight: 800;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }

        .stat-label {
            color: #555;
            font-size: 1.2rem;
            font-weight: 500;
        }

        .content-grid {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 30px;
            margin-bottom: 40px;
        }

        .panel {
            background: linear-gradient(145deg, #ffffff, #f8f9fa);
            padding: 30px;
            border-radius: 20px;
            box-shadow: 0 15px 35px rgba(0,0,0,0.1);
            backdrop-filter: blur(10px);
        }

        .panel h3 {
            color: #333;
            margin-bottom: 25px;
            font-size: 1.8rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .chart-container {
            position: relative;
            height: 400px;
            margin-top: 20px;
        }

        .user-list {
            max-height: 400px;
            overflow-y: auto;
            padding: 10px;
        }

        .user-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #f8f9fa, #e9ecef);
            border-radius: 15px;
            transition: all 0.3s ease;
        }

        .user-item:hover {
            transform: translateX(5px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }

        .user-name {
            font-weight: 600;
            color: #333;
            font-size: 1.1rem;
        }

        .message-count {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 8px 15px;
            border-radius: 25px;
            font-size: 0.9rem;
            font-weight: 600;
            box-shadow: 0 3px 10px rgba(102, 126, 234, 0.3);
        }

        .messages-panel {
            grid-column: 1 / -1;
        }

        .message-item {
            background: linear-gradient(135deg, #f8f9fa, #ffffff);
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 20px;
            border-left: 5px solid #667eea;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
            transition: all 0.3s ease;
        }

        .message-item:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        }

        .message-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }

        .message-user {
            font-weight: 700;
            color: #333;
            font-size: 1.1rem;
        }

        .message-time {
            color: #666;
            font-size: 0.95rem;
            background: #e9ecef;
            padding: 5px 10px;
            border-radius: 10px;
        }

        .message-text {
            background: #ffffff;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 15px;
            border: 1px solid #e9ecef;
            box-shadow: inset 0 2px 5px rgba(0,0,0,0.05);
        }

        .message-response {
            background: linear-gradient(135deg, #e3f2fd, #f3e5f5);
            padding: 15px;
            border-radius: 10px;
            border: 1px solid #bbdefb;
        }

        .refresh-btn {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 18px 25px;
            border: none;
            border-radius: 60px;
            cursor: pointer;
            font-size: 1.1rem;
            font-weight: 600;
            box-shadow: 0 10px 25px rgba(102, 126, 234, 0.4);
            transition: all 0.3s ease;
            z-index: 1000;
        }

        .refresh-btn:hover {
            transform: scale(1.1) rotate(180deg);
            box-shadow: 0 15px 35px rgba(102, 126, 234, 0.6);
        }

        .loading {
            text-align: center;
            color: #666;
            font-style: italic;
            padding: 40px;
            font-size: 1.1rem;
        }

        .status-indicator {
            position: absolute;
            top: 15px;
            right: 15px;
            width: 12px;
            height: 12px;
            background: #4caf50;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.7); }
            70% { box-shadow: 0 0 0 10px rgba(76, 175, 80, 0); }
            100% { box-shadow: 0 0 0 0 rgba(76, 175, 80, 0); }
        }

        @media (max-width: 768px) {
            .content-grid {
                grid-template-columns: 1fr;
            }

            .stats-grid {
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            }

            .header h1 {
                font-size: 2rem;
            }

            .container {
                padding: 10px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="status-indicator"></div>
            <h1>🤖 Redzone AI Bot</h1>
            <p>Gelişmiş Analiz ve İzleme Paneli</p>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number" id="totalUsers">-</div>
                <div class="stat-label">👥 Toplam Kullanıcı</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="totalMessages">-</div>
                <div class="stat-label">💬 Toplam Mesaj</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="todayActive">-</div>
                <div class="stat-label">🔥 Bugün Aktif</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="weekActive">-</div>
                <div class="stat-label">📊 Haftalık Aktif</div>
            </div>
        </div>

        <div class="content-grid">
            <div class="panel">
                <h3>📈 Günlük Mesaj Grafiği</h3>
                <div class="chart-container">
                    <canvas id="messageChart"></canvas>
                </div>
            </div>

            <div class="panel">
                <h3>🏆 En Aktif Kullanıcılar</h3>
                <div class="user-list" id="topUsers">
                    <div class="loading">⏳ Yükleniyor...</div>
                </div>
            </div>
        </div>

        <div class="panel messages-panel">
            <h3>💭 Son Mesajlar</h3>
            <div id="recentMessages">
                <div class="loading">⏳ Yükleniyor...</div>
            </div>
        </div>
    </div>

    <button class="refresh-btn" onclick="loadData()" title="Verileri Yenile">🔄</button>

    <script>
        let messageChart;

        function formatDate(dateString) {
            const date = new Date(dateString);
            return date.toLocaleDateString('tr-TR', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        }

        function createChart(dailyMessages) {
            const ctx = document.getElementById('messageChart').getContext('2d');

            if (messageChart) {
                messageChart.destroy();
            }

            const labels = dailyMessages.map(item => {
                const date = new Date(item.date);
                return date.toLocaleDateString('tr-TR', { month: 'short', day: 'numeric' });
            });
            const data = dailyMessages.map(item => item.count);

            messageChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Günlük Mesajlar',
                        data: data,
                        borderColor: 'rgb(102, 126, 234)',
                        backgroundColor: 'rgba(102, 126, 234, 0.1)',
                        borderWidth: 3,
                        fill: true,
                        tension: 0.4,
                        pointBackgroundColor: 'rgb(102, 126, 234)',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2,
                        pointRadius: 6,
                        pointHoverRadius: 8
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            backgroundColor: 'rgba(0, 0, 0, 0.8)',
                            titleColor: 'white',
                            bodyColor: 'white',
                            borderColor: 'rgb(102, 126, 234)',
                            borderWidth: 1,
                            cornerRadius: 10,
                            displayColors: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)',
                                drawBorder: false
                            },
                            ticks: {
                                color: '#666',
                                font: {
                                    size: 12
                                }
                            }
                        },
                        x: {
                            grid: {
                                display: false
                            },
                            ticks: {
                                color: '#666',
                                font: {
                                    size: 12
                                }
                            }
                        }
                    }
                }
            });
        }

        function animateNumber(element, targetValue, duration = 1000) {
            const startValue = 0;
            const startTime = performance.now();

            function update(currentTime) {
                const elapsed = currentTime - startTime;
                const progress = Math.min(elapsed / duration, 1);

                const easeOutQuart = 1 - Math.pow(1 - progress, 4);
                const currentValue = Math.floor(startValue + (targetValue - startValue) * easeOutQuart);

                element.textContent = currentValue.toLocaleString('tr-TR');

                if (progress < 1) {
                    requestAnimationFrame(update);
                }
            }

            requestAnimationFrame(update);
        }

        function loadData() {
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    // İstatistikleri animasyonla güncelle
                    animateNumber(document.getElementById('totalUsers'), data.total_users);
                    animateNumber(document.getElementById('totalMessages'), data.total_messages);
                    animateNumber(document.getElementById('todayActive'), data.today_active);
                    animateNumber(document.getElementById('weekActive'), data.week_active);

                    // Grafik güncelle
                    createChart(data.daily_messages);

                    // En aktif kullanıcıları güncelle
                    const topUsersContainer = document.getElementById('topUsers');
                    if (data.top_users.length > 0) {
                        topUsersContainer.innerHTML = data.top_users.map(user => `
                            <div class="user-item">
                                <div class="user-name">
                                    ${user.first_name || user.username || 'Bilinmiyor'}
                                </div>
                                <div class="message-count">
                                    ${user.total_messages} mesaj
                                </div>
                            </div>
                        `).join('');
                    } else {
                        topUsersContainer.innerHTML = '<div class="loading">Henüz veri yok</div>';
                    }

                    // Son mesajları güncelle
                    const recentMessagesContainer = document.getElementById('recentMessages');
                    if (data.recent_messages.length > 0) {
                        recentMessagesContainer.innerHTML = data.recent_messages.map(msg => `
                            <div class="message-item">
                                <div class="message-header">
                                    <div class="message-user">
                                        ${msg.first_name || msg.username || 'Bilinmiyor'}
                                    </div>
                                    <div class="message-time">
                                        ${formatDate(msg.timestamp)}
                                    </div>
                                </div>
                                <div class="message-text">
                                    <strong>Kullanıcı:</strong> ${msg.message.length > 100 ? msg.message.substring(0, 100) + '...' : msg.message}
                                </div>
                                <div class="message-response">
                                    <strong>Bot:</strong> ${msg.response.length > 150 ? msg.response.substring(0, 150) + '...' : msg.response}
                                </div>
                            </div>
                        `).join('');
                    } else {
                        recentMessagesContainer.innerHTML = '<div class="loading">Henüz mesaj yok</div>';
                    }
                })
                .catch(error => {
                    console.error('Veri yükleme hatası:', error);
                    document.getElementById('totalUsers').textContent = 'Hata';
                    document.getElementById('totalMessages').textContent = 'Hata';
                    document.getElementById('todayActive').textContent = 'Hata';
                    document.getElementById('weekActive').textContent = 'Hata';
                });
        }

        // Sayfa yüklendiğinde verileri yükle
        document.addEventListener('DOMContentLoaded', loadData);

        // Her 30 saniyede bir otomatik güncelle
        setInterval(loadData, 30000);

        // Klavye kısayolları
        document.addEventListener('keydown', function(e) {
            if (e.key === 'F5' || (e.ctrlKey && e.key === 'r')) {
                e.preventDefault();
                loadData();
            }
        });
    </script>
</body>
</html>
'''

# Telegram bot kurulumu
def run_telegram_bot():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Komut handlers'ı ekle
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("recent", admin_recent_messages))

    # Mesaj handler'ı ekle
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Telegram bot başlatılıyor...")
    app.run_polling(drop_pending_updates=True)

# Flask uygulamasını çalıştırma
def run_flask_app():
    port = int(os.environ.get("PORT", 5000))
    print(f"🌐 Flask web paneli başlatılıyor... Port: {port}")
    flask_app.run(host="0.0.0.0", port=port, debug=False)

# Ana uygulama
if __name__ == "__main__":
    # Veritabanını başlat
    init_database()
    print("📊 Veritabanı hazırlandı.")

    # Bot ve Flask'i ayrı thread'lerde çalıştır
    telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    flask_thread = threading.Thread(target=run_flask_app, daemon=True)

    try:
        telegram_thread.start()
        flask_thread.start()

        print("✅ Redzone AI Bot tamamen aktif!")
        print("📱 Telegram bot çalışıyor")
        print("🌐 Web analiz paneli çalışıyor")
        print("🔄 Sistem hazır...")

        # Ana thread'i canlı tut
        telegram_thread.join()
        flask_thread.join()

    except KeyboardInterrupt:
        print("\n⚠️ Sistem kapatılıyor...")
    except Exception as e:
        print(f"❌ Hata: {e}")
