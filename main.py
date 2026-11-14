import os
import threading
import asyncio
from flask import Flask, render_template_string, request, jsonify
from telethon import TelegramClient, functions
from telethon.sessions import StringSession

API_ID = int(os.environ.get("API_ID", 2040))
API_HASH = os.environ.get("API_HASH", "b18441a1ff607e10a989891a5462e627")
STRING_SESSION = os.environ.get("STRING_SESSION", "").strip()

app = Flask(__name__)

# Изолированный event loop для Telethon
telethon_loop = asyncio.new_event_loop()
asyncio.set_event_loop(telethon_loop)

client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH, loop=telethon_loop)

prank_state = {
    "is_typing": False,
    "target": "",
    "name": "некреветка",
    "status": "Остановлено"
}

# Фоновый воркер с кэшированием сущности чата (без лишних запросов к API)
def run_telegram_background():
    async def background_worker():
        await client.connect()
        print("Telegram client successfully connected in background loop!")
        
        cached_entity = None
        last_target = ""

        while True:
            if prank_state["is_typing"] and prank_state["target"]:
                target = prank_state["target"]
                
                # Если целевой чат сменился, сбрасываем кэш
                if target != last_target:
                    cached_entity = None
                    last_target = target

                try:
                    # Получаем сущность один раз и кэшируем
                    if cached_entity is None:
                        parsed_target = int(target) if (target.startswith("-100") or target.isdigit()) else target
                        cached_entity = await client.get_input_entity(parsed_target)
                    
                    async with client.action(cached_entity, 'typing'):
                        await asyncio.sleep(4)
                except Exception as e:
                    print(f"Typing error: {e}")
                    cached_entity = None  # Сбрасываем при ошибке для повторной попытки
                    await asyncio.sleep(5)
            else:
                cached_entity = None
                last_target = ""
                await asyncio.sleep(1)

    telethon_loop.run_until_complete(background_worker())

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
        <h2>❤️ Pranik</h2>
        
        <label>Ник твинка:</label>
        <input type="text" id="nameInput" value="{{ name }}">
        <button class="btn-name" onclick="setName()">Сменить имя</button>

        <label>Чат (@username или -100...):</label>
        <input type="text" id="targetInput" placeholder="@group_name" value="{{ target }}">

        <button class="btn-start" onclick="startPrank()">🟢 СТАРТ (Печатает)</button>
        <button class="btn-stop" onclick="stopPrank()">🔴 СТОП</button>

        <div class="status-box">
            Статус: <span id="statusText" class="{{ 'active' if is_typing else 'inactive' }}">{{ status }}</span>
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
                location.reload();
            } catch (err) {
                alert("Ошибка соединения с сервером!");
            }
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
    if not new_name:
        return jsonify({"message": "Имя не может быть пустым!"})
    
    prank_state["name"] = new_name
    
    async def update_profile():
        await client(functions.account.UpdateProfileRequest(first_name=new_name))

    try:
        future = asyncio.run_coroutine_threadsafe(update_profile(), telethon_loop)
        future.result(timeout=10)
        return jsonify({"message": f"Имя успешно сменено на: {new_name}"})
    except Exception as e:
        return jsonify({"message": f"Ошибка смены имени: {str(e)}"})

@app.route('/start', methods=['POST'])
def api_start():
    data = request.json
    target = data.get('target', '').strip()
    if not target:
        return jsonify({"message": "Укажите чат!"})
    
    prank_state["target"] = target
    prank_state["is_typing"] = True
    return jsonify({"message": f"Статус печати запущен для: {target}"})

@app.route('/stop', methods=['POST'])
def api_stop():
    prank_state["is_typing"] = False
    return jsonify({"message": "Пранк остановлен."})

if __name__ == '__main__':
    threading.Thread(target=run_telegram_background, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
