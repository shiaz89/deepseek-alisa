import os
import json
from fastapi import FastAPI, Request
import requests

app = FastAPI()

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")


@app.get("/")
@app.head("/")
async def health_check():
    return JSONResponse(content={"status": "ok"}, status_code=200)
    

@app.post("/")
async def main(request: Request):
    # Читаем тело как байты, чтобы избежать падения на пустом запросе
    raw_body = await request.body()

    # Если тело пустое или не JSON — отвечаем стандартным ответом для ping
    if not raw_body:
        return {
            "version": "1.0",
            "response": {
                "text": "ok",
                "end_session": False
            }
        }

    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        return {
            "version": "1.0",
            "response": {
                "text": "ok",
                "end_session": False
            }
        }

    # Извлекаем текст запроса пользователя
    user_text = body["request"]["original_utterance"]

    # Если пришёл ping — сразу отвечаем, не дёргая DeepSeek
    if user_text.lower() == "ping":
        return {
            "version": body.get("version", "1.0"),
            "response": {
                "text": "ok",
                "end_session": False
            }
        }

    # Запрос к DeepSeek
    try:
        response = requests.post(
            DEEPSEEK_API_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": user_text}],
            },
            timeout=30
        )
        answer = response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        answer = f"Ошибка при обращении к DeepSeek: {e}"

    return {
        "version": body.get("version", "1.0"),
        "session": body.get("session"),
        "response": {
            "end_session": False,
            "text": answer
        }
    }
