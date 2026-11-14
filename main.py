import os
import threading
import asyncio
from flask import Flask, render_template_string, request, jsonify
from telethon import TelegramClient, events, functions
from telethon.sessions import StringSession

API_ID = int(os.environ.get("API_ID", 2040))
API_HASH = os.environ.get("API_HASH", "b18441a1ff607e10a989891a5462e627")
STRING_SESSION = os.environ.get("STRING_SESSION", "").strip()
OWNER_ID = int(os.environ.get("OWNER_ID", 0))

app = Flask(__name__)

# Изолированный event loop для Telethon
telethon_loop = asyncio.new_event_loop()
asyncio.set_event_loop(telethon_loop)

client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH, loop=telethon_loop)

# Состояние панели
panel_state = {
    "enabled": True,
    "my_name": "Загрузка...",
    "my_bio": "Загрузка..."
}

# Красивый многофункциональный интерфейс (Dashboard)
HTML_PAGE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Twink Control Hub</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 15px; display: flex; justify-content: center; }
        .container { width: 100%; max-width: 440px; }
        .card { background: #1e293b; padding: 20px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); margin-bottom: 15px; border: 1px solid #334155; }
        h2 { text-align: center; margin-bottom: 5px; color: #38bdf8; font-size: 22px; }
        .subtitle { text-align: center; font-size: 12px; color: #94a3b8; margin-bottom: 15px; }
        h3 { font-size: 15px; color: #cbd5e1; margin-top: 0; margin-bottom: 10px; border-bottom: 1px solid #334155; padding-bottom: 5px; }
        label { font-size: 13px; color: #94a3b8; display: block; margin-top: 8px; }
        input, textarea { width: 100%; padding: 10px; margin-top: 4px; background: #0f172a; border: 1px solid #334155; border-radius: 8px; color: #fff; box-sizing: border-box; font-size: 14px; font-family: inherit; }
        textarea { resize: vertical; height: 70px; }
        button { width: 100%; padding: 10px; margin-top: 12px; border: none; border-radius: 8px; font-size: 14px; font-weight: bold; cursor: pointer; transition: 0.2s; }
        .btn-send { background: #22c55e; color: white; }
        .btn-send:hover { background: #16a34a; }
        .btn-name { background: #3b82f6; color: white; }
        .btn-name:hover { background: #2563eb; }
        .btn-bio { background: #8b5cf6; color: white; }
        .btn-bio:hover { background: #7c3aed; }
        .status-box { padding: 10px; background: #0f172a; border-radius: 8px; text-align: center; font-size: 13px; border: 1px solid #334155; margin-top: 10px; }
        .active { color: #22c55e; font-weight: bold; }
        .inactive { color: #ef4444; font-weight: bold; }
        .info-text { font-size: 12px; color: #94a3b8; margin-top: 5px; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <h2>🎛️ Twink Control Hub</h2>
        <div class="subtitle">Многофункциональный пульт управления аккаунтом</div>

        <!-- Секция 1: Отправка сообщений -->
        <div class="card">
            <h3>📨 Отправить сообщение</h3>
            <label>Чат (@username или ID):</label>
            <input type="text" id="targetInput" placeholder="@group_name">

            <label>Текст сообщения:</label>
            <textarea id="textInput" placeholder="Что написать от твоего имени..."></textarea>

            <button class="btn-send" onclick="sendAction('/api/send', {target: document.getElementById('targetInput').value, text: document.getElementById('textInput').value})">🚀 Отправить в чат</button>
        </div>

        <!-- Секция 2: Смена имени -->
        <div class="card">
            <h3>✏️ Сменить имя профиля</h3>
            <label>Новое имя:</label>
            <input type="text" id="nameInput" value="{{ my_name }}">
            <button class="btn-name" onclick="sendAction('/api/set_name', {name: document.getElementById('nameInput').value})">🔄 Обновить имя</button>
        </div>

        <!-- Секция 3: Смена Bio -->
        <div class="card">
            <h3>🎭 Сменить Bio (О себе)</h3>
            <label>Новый статус (до 70 символов):</label>
            <input type="text" id="bioInput" maxlength="70" value="{{ my_bio }}">
            <button class="btn-bio" onclick="sendAction('/api/set_bio', {bio: document.getElementById('bioInput').value})">✨ Обновить Bio</button>
        </div>

        <!-- Статус панели -->
        <div class="card" style="padding: 15px;">
            <div class="status-box">
                Состояние панели: <span class="{{ 'active' if enabled else 'inactive' }}">{{ '⚡ Активна (Работает)' if enabled else '🛑 ЗАБЛОКИРОВАНА (Стоп)' }}</span>
            </div>
            <div class="info-text">Для экстренного отключения напиши <b>стоп</b> в ЛС твинку. Для включения — <b>старт</b>.</div>
        </div>
    </div>

    <script>
        async function sendAction(url, data) {
            try {
                let response = await fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                let result = await response.json();
                alert(result.message);
                if(response.ok) {
                    location.reload();
                }
            } catch (err) {
                alert("❌ Ошибка соединения с сервером!");
            }
        }
    </script>
</body>
</html>
"""

def run_telegram_background():
    async def background_main():
        await client.connect()
        me = await client.get_me()
        panel_state["my_name"] = me.first_name or ""
        panel_state["my_bio"] = me.about or ""
        print(f"Connected as {me.first_name} (ID: {me.id})")

        # Слушаем ЛС для килл-свича
        @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def kill_switch(event):
            if OWNER_ID == 0 or event.sender_id == OWNER_ID:
                text = event.raw_text.strip().lower()
                if text == "стоп":
                    panel_state["enabled"] = False
                    await event.respond("🛑 Пульт управления экстренно ЗАБЛОКИРОВАН!")
                elif text == "старт":
                    panel_state["enabled"] = True
                    await event.respond("🟢 Пульт управления РАЗБЛОКИРОВАН!")

        await client.run_until_disconnected()

    telethon_loop.run_until_complete(background_main())

@app.route('/')
def home():
    return render_template_string(HTML_PAGE, 
                                  my_name=panel_state["my_name"],
                                  my_bio=panel_state["my_bio"],
                                  enabled=panel_state["enabled"])

@app.route('/api/send', methods=['POST'])
def api_send():
    if not panel_state["enabled"]:
        return jsonify({"message": "❌ Панель заблокирована владельцем!"}), 400
    data = request.json
    target = data.get('target', '').strip()
    text = data.get('text', '').strip()
    if not target or not text:
        return jsonify({"message": "⚠️ Заполни чат и текст!"}), 400

    async def task():
        parsed = int(target) if (target.startswith("-100") or target.isdigit()) else target
        entity = await client.get_input_entity(parsed)
        await client.send_message(entity, text)

    try:
        future = asyncio.run_coroutine_threadsafe(task(), telethon_loop)
        future.result(timeout=10)
        return jsonify({"message": "✅ Сообщение успешно отправлено в чат!"})
    except Exception as e:
        return jsonify({"message": f"❌ Ошибка отправки: {str(e)}"}), 500

@app.route('/api/set_name', methods=['POST'])
def api_set_name():
    if not panel_state["enabled"]:
        return jsonify({"message": "❌ Панель заблокирована владельцем!"}), 400
    data = request.json
    new_name = data.get('name', '').strip()
    if not new_name:
        return jsonify({"message": "⚠️ Имя не может быть пустым!"}), 400

    async def task():
        await client(functions.account.UpdateProfileRequest(first_name=new_name))
        me = await client.get_me()
        panel_state["my_name"] = me.first_name

    try:
        future = asyncio.run_coroutine_threadsafe(task(), telethon_loop)
        future.result(timeout=10)
        return jsonify({"message": "✅ Имя аккаунта успешно изменено!"})
    except Exception as e:
        return jsonify({"message": f"❌ Ошибка смены имени: {str(e)}"}), 500

@app.route('/api/set_bio', methods=['POST'])
def api_set_bio():
    if not panel_state["enabled"]:
        return jsonify({"message": "❌ Панель заблокирована владельцем!"}), 400
    data = request.json
    new_bio = data.get('bio', '').strip()

    async def task():
        await client(functions.account.UpdateProfileRequest(about=new_bio))
        me = await client.get_me()
        panel_state["my_bio"] = me.about or ""

    try:
        future = asyncio.run_coroutine_threadsafe(task(), telethon_loop)
        future.result(timeout=10)
        return jsonify({"message": "✅ Bio (описание) успешно изменено!"})
    except Exception as e:
        return jsonify({"message": f"❌ Ошибка смены Bio: {str(e)}"}), 500

if __name__ == '__main__':
    threading.Thread(target=run_telegram_background, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
