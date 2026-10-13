import os
import json
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx

app = FastAPI()

API_URL = os.getenv("API_URL")
API_KEY = os.getenv("API_KEY")

if not API_URL:
    raise RuntimeError("API_URL не задан в переменных окружения")
if not API_KEY:
    raise RuntimeError("API_KEY не задан в переменных окружения")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.get("/")
@app.head("/")
async def health_check():
    return JSONResponse(content={"status": "ok"}, status_code=200)

@app.post("/")
async def main(request: Request):
    logger.info("Received POST request")
    raw_body = await request.body()

    if not raw_body:
        logger.warning("Empty body received")
        return {
            "version": "1.0",
            "session": None,
            "response": {"text": "Сервис готов, но не получил запрос", "end_session": False}
        }

    body = None
    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON: %s", e)
        return {
            "version": "1.0",
            "session": None,
            "response": {"text": "Не удалось прочитать запрос", "end_session": False}
        }

    user_text = ""
    if body:
        user_text = body.get("request", {}).get("original_utterance", "").strip()

    # Ping
    if user_text.lower() == "ping":
        logger.info("Ping request handled")
        return {
            "version": body.get("version", "1.0"),
            "session": body.get("session"),
            "response": {"text": "ok", "end_session": False}
        }

    if not user_text:
        return {
            "version": body.get("version", "1.0"),
            "session": body.get("session"),
            "response": {"text": "Скажите что-нибудь — я помогу!", "end_session": False}
        }

    logger.info(f"Calling AI, text length: {len(user_text)}")
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:  # уменьшили таймаут
            resp = await client.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                },
                json={
                    # УКАЖИ ЗДЕСЬ РЕАЛЬНО БЕСПЛАТНУЮ МОДЕЛЬ ИЗ OPENROUTER
                    "model": "qwen/qwen-2.5-14b-instruct",
                    "messages": [{"role": "user", "content": user_text}],
                },
            )
            resp.raise_for_status()
            answer_data = resp.json()

        choices = answer_data.get("choices", [])
        if not choices:
            logger.warning("Empty choices from LLM")
            answer = "Сейчас не удалось получить ответ от модели. Попробуйте позже."
        else:
            answer = choices[0]["message"]["content"]
            logger.info("OpenRouter success")

    except httpx.TimeoutException:
        logger.error("OpenRouter timeout")
        answer = "Сервис временно не успевает получить ответ. Попробуйте позже."
    except httpx.HTTPStatusError as e:
        logger.error("OpenRouter HTTP error: status=%s, body=%s", e.response.status_code, e.response.text)
        if e.response.status_code == 401:
            answer = "Ошибка авторизации. Проверьте API‑ключ."
        elif e.response.status_code == 404:
            answer = "Модель не найдена. Проверьте название модели."
        elif e.response.status_code == 402:
            answer = "Требуется оплата. Модель недоступна в бесплатном режиме."
        else:
            answer = "Сейчас не удаётся получить ответ. Попробуйте позже."
    except Exception as e:
        logger.error("OpenRouter unexpected error: %s", e)
        answer = "Сейчас не удаётся получить ответ. Попробуйте позже."

    return {
        "version": body.get("version", "1.0"),
        "session": body.get("session"),
        "response": {
            "text": answer,
            "tts": answer,           # голос
            "end_session": False
        }
    }
