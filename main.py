import os
import asyncio
import threading
from flask import Flask, render_template_string, request, jsonify
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl import functions

API_ID = int(os.environ.get("API_ID", 2040))
API_HASH = os.environ.get("API_HASH", "b18441a1ff607e10a989891a5462e627")
STRING_SESSION = os.environ.get("STRING_SESSION", "").strip()

# Инициализация бота и Flask
client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
app = Flask(__name__)

# Состояние пранка
prank_state = {
    "is_typing": False,
    "target": "",
    "name": "некреветка",
    "status": "Остановлено"
}

# HTML-панель управления прямо внутри скрипта
HTML_PAGE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prank Control Panel</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; display: flex; justify-content: center; }
        .card { background: #1e293b; padding: 25px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); width: 100%; max-width: 400px; }
        h2 { text-align: center; margin-bottom: 20px; color: #38bdf8; }
        label { font-size: 14px; color: #94a3b8; display: block; margin-top: 12px; }
        input { width: 100%; padding: 12px; margin-top: 6px; background: #0f172a; border: 1px solid #334155; border-radius: 8px; color: #fff; box-sizing: border-box; font-size: 16px; }
        button { width: 100%; padding: 12px; margin-top: 15px; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; transition: 0.2s; }
        .btn-start { background: #22c55e; color: white; }
        .btn-start:hover { background: #16a34a; }
        .btn-stop { background: #ef4444; color: white; }
        .btn-stop:hover { background: #dc2626; }
        .btn-name { background: #3b82f6; color: white; }
        .btn-name:hover { background: #2563eb; }
        .status-box { margin-top: 20px; padding: 12px; background: #0f172a; border-radius: 8px; text-align: center; font-size: 14px; border: 1px solid #334155; }
        .active { color: #22c55e; font-weight: bold; }
        .inactive { color: #ef4444; font-weight: bold; }
    </style>
</head>
<body>
    <div class="card">
        <h2>🦐 Пранк Панель</h2>
        
        <label>Ник твинка (кого изображаем):</label>
        <input type="text" id="nameInput" value="{{ name }}">
        <button class="btn-name" onclick="setName()">Сменить имя</button>

        <label>Чат (юзернейм @chat или ID -100...):</label>
        <input type="text" id="targetInput" placeholder="@group_name или -100xxxx" value="{{ target }}">

        <button class="btn-start" onclick="startPrank()">🟢 СТАРТ (Печатает)</button>
        <button class="btn-stop" onclick="stopPrank()">🔴 СТОП</button>

        <div class="status-box">
            Статус: <span id="statusText" class="{{ 'active' if is_typing else 'inactive' }}">{{ status }}</span>
        </div>
    </div>

    <script>
        async function sendAction(url, data) {
            let response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            let result = await response.json();
            alert(result.message);
            location.reload();
        }

        function setName() {
            let name = document.getElementById('nameInput').value;
            sendAction('/set_name', { name: name });
        }

        function startPrank() {
            let target = document.getElementById('targetInput').value;
            sendAction('/start', { target: target });
        }

        function stopPrank() {
            sendAction('/stop', {});
        }
    </script>
</body>
</html>
"""

async def typing_loop():
    global prank_state
    while prank_state["is_typing"]:
        try:
            target = prank_state["target"]
            # Если ввели ID или юзернейм
            if target.startswith("-100"):
                target = int(target)
            
            async with client.action(target, 'typing'):
                await asyncio.sleep(4)
        except Exception as e:
            print(f"Ошибка статуса печати: {e}")
            await asyncio.sleep(5)

@app.route('/')
def home():
    return render_template_string(HTML_PAGE, 
                                  name=prank_state["name"], 
                                  target=prank_state["target"], 
                                  is_typing=prank_state["is_typing"],
                                  status="Печатает..." if prank_state["is_typing"] else "Остановлено")

@app.route('/set_name', methods=['POST'])
def api_set_name():
    data = request.json
    new_name = data.get('name', '').strip()
    if new_name:
        prank_state["name"] = new_name
        # Меняем имя через клиент Telegram асинхронно
        asyncio.run_coroutine_threadsafe(
            client(functions.account.UpdateProfileRequest(first_name=new_name, last_name="")), 
            client.loop
        )
        return jsonify({"message": f"Имя успешно сменено на: {new_name}"})
    return jsonify({"message": "Имя не может быть пустым!"})

@app.route('/start', methods=['POST'])
def api_start():
    data = request.json
    target = data.get('target', '').strip()
    if not target:
        return jsonify({"message": "Укажите чат (юзернейм или ID)!"})
    
    prank_state["target"] = target
    prank_state["is_typing"] = True
    
    # Запускаем бесконечный цикл печати в фоновом потоке бота
    asyncio.run_coroutine_threadsafe(typing_loop(), client.loop)
    return jsonify({"message": f"Запущен статус печати в чате: {target}"})

@app.route('/stop', methods=['POST'])
def api_stop():
    prank_state["is_typing"] = False
    return jsonify({"message": "Пранк остановлен."})

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    # Запускаем Flask в фоне
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Запуск Telegram клиента
    client.start()
    print("Web Control Panel Bot started!")
    client.run_until_disconnected()