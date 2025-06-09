from flask import Flask, render_template_string, jsonify
import sqlite3
from datetime import datetime, timedelta
import json

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('bot_analytics.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/stats')
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

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Redzone AI Bot - Analiz Paneli</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
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
            max-width: 1200px;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }

        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            text-align: center;
            transition: transform 0.3s ease;
        }

        .stat-card:hover {
            transform: translateY(-5px);
        }

        .stat-number {
            font-size: 2.5rem;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 10px;
        }

        .stat-label {
            color: #666;
            font-size: 1.1rem;
        }

        .content-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 30px;
        }

        .panel {
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }

        .panel h3 {
            color: #333;
            margin-bottom: 20px;
            font-size: 1.5rem;
        }

        .chart-container {
            position: relative;
            height: 300px;
        }

        .user-list {
            max-height: 300px;
            overflow-y: auto;
        }

        .user-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }

        .user-name {
            font-weight: 500;
            color: #333;
        }

        .message-count {
            background: #667eea;
            color: white;
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 0.9rem;
        }

        .messages-panel {
            grid-column: 1 / -1;
        }

        .message-item {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 15px;
            border-left: 4px solid #667eea;
        }

        .message-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }

        .message-user {
            font-weight: 600;
            color: #333;
        }

        .message-time {
            color: #666;
            font-size: 0.9rem;
        }

        .message-text {
            background: white;
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 10px;
            border: 1px solid #e9ecef;
        }

        .message-response {
            background: #e3f2fd;
            padding: 10px;
            border-radius: 8px;
            border: 1px solid #bbdefb;
        }

        .refresh-btn {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: #667eea;
            color: white;
            padding: 15px 20px;
            border: none;
            border-radius: 50px;
            cursor: pointer;
            font-size: 1rem;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            transition: all 0.3s ease;
        }

        .refresh-btn:hover {
            background: #5a6fd8;
            transform: scale(1.05);
        }

        .loading {
            text-align: center;
            color: #666;
            font-style: italic;
        }

        @media (max-width: 768px) {
            .content-grid {
                grid-template-columns: 1fr;
            }

            .stats-grid {
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Redzone AI Bot</h1>
            <p>Analiz Paneli</p>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number" id="totalUsers">-</div>
                <div class="stat-label">Toplam Kullanıcı</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="totalMessages">-</div>
                <div class="stat-label">Toplam Mesaj</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="todayActive">-</div>
                <div class="stat-label">Bugün Aktif</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="weekActive">-</div>
                <div class="stat-label">Haftalık Aktif</div>
            </div>
        </div>

        <div class="content-grid">
            <div class="panel">
                <h3>📊 Günlük Mesaj Grafiği</h3>
                <div class="chart-container">
                    <canvas id="messageChart"></canvas>
                </div>
            </div>

            <div class="panel">
                <h3>👥 En Aktif Kullanıcılar</h3>
                <div class="user-list" id="topUsers">
                    <div class="loading">Yükleniyor...</div>
                </div>
            </div>
        </div>

        <div class="panel messages-panel">
            <h3>💬 Son Mesajlar</h3>
            <div id="recentMessages">
                <div class="loading">Yükleniyor...</div>
            </div>
        </div>
    </div>

    <button class="refresh-btn" onclick="loadData()">🔄 Yenile</button>

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
                        borderColor: '#667eea',
                        backgroundColor: 'rgba(102, 126, 234, 0.1)',
                        borderWidth: 3,
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                stepSize: 1
                            }
                        }
                    }
                }
            });
        }

        function renderTopUsers(users) {
            const container = document.getElementById('topUsers');
            if (users.length === 0) {
                container.innerHTML = '<div class="loading">Henüz kullanıcı yok</div>';
                return;
            }

            container.innerHTML = users.map(user => `
                <div class="user-item">
                    <div class="user-name">${user.first_name || user.username || 'Bilinmiyor'}</div>
                    <div class="message-count">${user.total_messages}</div>
                </div>
            `).join('');
        }

        function renderRecentMessages(messages) {
            const container = document.getElementById('recentMessages');
            if (messages.length === 0) {
                container.innerHTML = '<div class="loading">Henüz mesaj yok</div>';
                return;
            }

            container.innerHTML = messages.map(msg => `
                <div class="message-item">
                    <div class="message-header">
                        <div class="message-user">${msg.first_name || msg.username || 'Bilinmiyor'}</div>
                        <div class="message-time">${formatDate(msg.timestamp)}</div>
                    </div>
                    <div class="message-text">
                        <strong>Soru:</strong> ${msg.message.length > 100 ? msg.message.substring(0, 100) + '...' : msg.message}
                    </div>
                    <div class="message-response">
                        <strong>Cevap:</strong> ${msg.response.length > 150 ? msg.response.substring(0, 150) + '...' : msg.response}
                    </div>
                </div>
            `).join('');
        }

        async function loadData() {
            try {
                const response = await fetch('/api/stats');
                const data = await response.json();

                // İstatistikleri güncelle
                document.getElementById('totalUsers').textContent = data.total_users;
                document.getElementById('totalMessages').textContent = data.total_messages;
                document.getElementById('todayActive').textContent = data.today_active;
                document.getElementById('weekActive').textContent = data.week_active;

                // Grafik oluştur
                createChart(data.daily_messages);

                // En aktif kullanıcıları göster
                renderTopUsers(data.top_users);

                // Son mesajları göster
                renderRecentMessages(data.recent_messages);

            } catch (error) {
                console.error('Veri yüklenirken hata:', error);
            }
        }

        // Sayfa yüklendiğinde veriyi al
        document.addEventListener('DOMContentLoaded', loadData);

        // Her 30 saniyede bir otomatik yenile
        setInterval(loadData, 30000);
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
