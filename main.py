import os
import threading
import asyncio
from flask import Flask, render_template_string, request, jsonify
from telethon import TelegramClient, events
from telethon.sessions import StringSession

API_ID = int(os.environ.get("API_ID", 2040))
API_HASH = os.environ.get("API_HASH", "b18441a1ff607e10a989891a5462e627")
STRING_SESSION = os.environ.get("STRING_SESSION", "").strip()
# Твой личный Telegram ID (чтобы бот слушался только тебя)
OWNER_ID = int(os.environ.get("OWNER_ID", 0))

app = Flask(__name__)

# Изолированный event loop для Telethon
telethon_loop = asyncio.new_event_loop()
asyncio.set_event_loop(telethon_loop)

client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH, loop=telethon_loop)

# Состояние реле
relay_state = {
    "enabled": True,       # Включена ли отправка вообще (килл-свич)
    "target": ""           # Чат по умолчанию
}

# HTML-интерфейс панели отправки
HTML_PAGE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Web Telegram Sender</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; display: flex; justify-content: center; }
        .card { background: #1e293b; padding: 25px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); width: 100%; max-width: 400px; }
        h2 { text-align: center; margin-bottom: 20px; color: #38bdf8; }
        label { font-size: 14px; color: #94a3b8; display: block; margin-top: 12px; }
        input, textarea { width: 100%; padding: 12px; margin-top: 6px; background: #0f172a; border: 1px solid #334155; border-radius: 8px; color: #fff; box-sizing: border-box; font-size: 16px; font-family: inherit; }
        textarea { resize: vertical; height: 100px; }
        button { width: 100%; padding: 12px; margin-top: 15px; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; transition: 0.2s; }
        .btn-send { background: #22c55e; color: white; }
        .btn-send:hover { background: #16a34a; }
        .status-box { margin-top: 20px; padding: 12px; background: #0f172a; border-radius: 8px; text-align: center; font-size: 14px; border: 1px solid #334155; }
        .active { color: #22c55e; font-weight: bold; }
        .inactive { color: #ef4444; font-weight: bold; }
    </style>
</head>
<body>
    <div class="card">
        <h2>🚀 Отправка с твинка</h2>
        
        <label>Чат (@username или -100...):</label>
        <input type="text" id="targetInput" placeholder="@group_name" value="{{ target }}">

        <label>Текст сообщения:</label>
        <textarea id="textInput" placeholder="Введите текст сообщения..."></textarea>

        <button class="btn-send" onclick="sendMessage()">📨 Отправить сообщение</button>

        <div class="status-box">
            Статус реле: <span id="statusText" class="{{ 'active' if enabled else 'inactive' }}">{{ 'Активно (Разрешено)' if enabled else 'ЗАБЛОКИРОВАНО (Стоп)' }}</span>
        </div>
    </div>

    <script>
        async function sendMessage() {
            let target = document.getElementById('targetInput').value;
            let text = document.getElementById('textInput').value;
            
            let response = await fetch('/send', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target: target, text: text })
            });
            let result = await response.json();
            alert(result.message);
            if(response.ok) {
                document.getElementById('textInput').value = '';
            }
            location.reload();
        }
    </script>
</body>
</html>
"""

def run_telegram_background():
    async def background_main():
        await client.connect()
        me = await client.get_me()
        print(f"Telegram client connected as {me.first_name} (ID: {me.id})")
        if OWNER_ID == 0:
            print("WARNING: OWNER_ID is not set in environment variables! Anyone in PM can trigger stop/start.")

        # Слушаем ЛС для экстренных команд "стоп" / "старт"
        @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def kill_switch_listener(event):
            # Проверяем, что написал именно ты (если OWNER_ID задан) или любой в ЛС (если не задан)
            if OWNER_ID == 0 or event.sender_id == OWNER_ID:
                text = event.raw_text.strip().lower()
                if text == "стоп":
                    relay_state["enabled"] = False
                    await event.respond("🛑 **ВНИМАНИЕ:** Веб-отправка сообщений с твинка экстренно ОТКЛЮЧЕНА!")
                    print("Kill-switch activated: Sending disabled via PM.")
                elif text == "старт":
                    relay_state["enabled"] = True
                    await event.respond("🟢 Веб-отправка сообщений снова ВКЛЮЧЕНА!")
                    print("Kill-switch deactivated: Sending enabled via PM.")

        await client.run_until_disconnected()

    telethon_loop.run_until_complete(background_main())

@app.route('/')
def home():
    return render_template_string(HTML_PAGE, 
                                  target=relay_state["target"], 
                                  enabled=relay_state["enabled"])

@app.route('/send', methods=['POST'])
def api_send():
    if not relay_state["enabled"]:
        return jsonify({"message": "❌ Ошибка: Отправка заблокирована владельцем! (Отправьте 'старт' в ЛС твинку для разблокировки)"}), 400
    
    data = request.json
    target = data.get('target', '').strip()
    text = data.get('text', '').strip()
    
    if not target or not text:
        return jsonify({"message": "Укажите чат и текст сообщения!"}), 400
    
    relay_state["target"] = target

    async def send_msg_async():
        parsed_target = int(target) if (target.startswith("-100") or target.isdigit()) else target
        entity = await client.get_input_entity(parsed_target)
        await client.send_message(entity, text)

    try:
        future = asyncio.run_coroutine_threadsafe(send_msg_async(), telethon_loop)
        future.result(timeout=10)
        return jsonify({"message": "✅ Сообщение успешно отправлено от вашего имени!"})
    except Exception as e:
        return jsonify({"message": f"❌ Ошибка отправки: {str(e)}"}), 500

if __name__ == '__main__':
    threading.Thread(target=run_telegram_background, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
