import os
import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx

app = FastAPI()

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

if not DEEPSEEK_API_KEY:
    raise RuntimeError("DEEPSEEK_API_KEY не задан в переменных окружения")


@app.get("/")
@app.head("/")
async def health_check():
    return JSONResponse(content={"status": "ok"}, status_code=200)


@app.post("/")
async def main(request: Request):
    raw_body = await request.body()

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
                "text": "Не удалось прочитать запрос",
                "end_session": False
            }
        }

    user_text = body.get("request", {}).get("original_utterance", "").strip()

    # Ping
    if user_text.lower() == "ping":
        return {
            "version": body.get("version", "1.0"),
            "session": body.get("session"),
            "response": {
                "text": "ok",
                "end_session": False
            }
        }

    if not user_text:
        return {
            "version": body.get("version", "1.0"),
            "session": body.get("session"),
            "response": {
                "text": "Скажите что-нибудь — я с радостью помогу!",
                "end_session": False
            }
        }

    # Запрос к DeepSeek
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                DEEPSEEK_API_URL,
                headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": user_text}],
                },
            )
            resp.raise_for_status()
            answer_data = resp.json()

        choices = answer_data.get("choices", [])
        if not choices:
            raise ValueError("Пустой ответ от DeepSeek")

        answer = choices[0]["message"]["content"]

    except Exception as e:
        # Лучше логировать e, а пользователю — нейтральный текст
        answer = "Сейчас не удаётся получить ответ. Попробуйте позже."

    return {
        "version": body.get("version", "1.0"),
        "session": body.get("session"),
        "response": {
            "end_session": False,
            "text": answer
        }
    }
