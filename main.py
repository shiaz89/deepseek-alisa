import os
import json
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx

app = FastAPI()

# 1. URL для бесплатного Qwen через OpenRouter 
QWEN_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# 2. Ключ от OpenRouter
QWEN_API_KEY = os.getenv("QWEN_API_KEY")

if not QWEN_API_KEY:
    raise RuntimeError("QWEN_API_KEY не задан в переменных окружения")

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

    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON: %s", e)
        return {
            "version": "1.0",
            "session": body.get("session") if 'body' in locals() else None,
            "response": {"text": "Не удалось прочитать запрос", "end_session": False}
        }

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

    logger.info(f"Calling Qwen with model: qwen/qwen3-next-80b-a3b-instruct:free, text length: {len(user_text)}")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                QWEN_API_URL,
                headers={
                    "Authorization": f"Bearer {QWEN_API_KEY}",
                    "HTTP-Referer": "https://your-site.com",  # Опционально, но рекомендуется OpenRouter
                    "X-Title": "Alice Skill",                   # Опционально
                },
                json={
                    # 3. Бесплатная модель Qwen 
                    "model": "qwen/qwen3-next-80b-a3b-instruct:free", 
                    "messages": [{"role": "user", "content": user_text}],
                },
            )
            resp.raise_for_status()
            answer_data = resp.json()

        choices = answer_data.get("choices", [])
        if not choices:
            raise ValueError("DeepSeek returned empty choices")

        answer = choices[0]["message"]["content"]
        logger.info("DeepSeek success")

    except httpx.TimeoutException:
        logger.error("DeepSeek timeout")
        answer = "Сервис временно не успевает получить ответ. Попробуйте позже."
    except httpx.HTTPStatusError as e:
        # Тут ты увидишь точный код: 401, 404, 503 и т.п.
        logger.error("DeepSeek HTTP error: status=%s, body=%s", e.response.status_code, e.response.text)
        if e.response.status_code == 401:
            answer = "Ошибка авторизации. Проверьте API‑ключ."
        elif e.response.status_code == 404:
            answer = "Модель не найдена. Проверьте название модели."
        else:
            answer = "Сейчас не удаётся получить ответ. Попробуйте позже."
    except Exception as e:
        logger.error("DeepSeek unexpected error: %s", e)
        answer = "Сейчас не удаётся получить ответ. Попробуйте позже."

    return {
        "version": body.get("version", "1.0"),
        "session": body.get("session"),
        "response": {
            "end_session": False,
            "text": answer
        }
    }
