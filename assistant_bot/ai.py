import json
from datetime import datetime
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI


ACTION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "reply": {"type": "string"},
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["reminder", "memory", "note", "cancel_reminder"],
                    },
                    "project": {"type": ["string", "null"]},
                    "project_description": {"type": ["string", "null"]},
                    "title": {"type": ["string", "null"]},
                    "due_at": {"type": ["string", "null"]},
                    "due_timezone": {"type": ["string", "null"]},
                    "recurrence": {
                        "type": ["string", "null"],
                        "enum": ["none", "daily", "weekly", "monthly", None],
                    },
                    "reminder_kind": {
                        "type": ["string", "null"],
                        "enum": ["notification", "project_report", None],
                    },
                    "fact_key": {"type": ["string", "null"]},
                    "fact_value": {"type": ["string", "null"]},
                    "confidence": {"type": ["number", "null"]},
                    "note": {"type": ["string", "null"]},
                    "reminder_id": {"type": ["integer", "null"]},
                },
                "required": [
                    "type", "project", "project_description", "title", "due_at", "due_timezone",
                    "recurrence", "reminder_kind", "fact_key", "fact_value",
                    "confidence", "note", "reminder_id",
                ],
            },
        },
    },
    "required": ["reply", "actions"],
}

MEMORY_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "memories": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "project": {"type": ["string", "null"]},
                    "fact_key": {"type": "string"},
                    "fact_value": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["project", "fact_key", "fact_value", "confidence"],
            },
        }
    },
    "required": ["memories"],
}


SYSTEM_PROMPT = """Ты — персональный Telegram-ассистент с долговременной памятью.
Понимай русский, казахский, английский и их смесь. Отвечай коротко на языке пользователя.
conversation_history — это реальные предыдущие реплики пользователя и ассистента. Используй
их для продолжения темы, понимания местоимений и ссылок вроде «он», «тот проект», «как я говорил».
Не утверждай, что не помнишь информацию, которая есть в conversation_history или memories.

Твоя главная обязанность — безошибочно извлекать напоминания:
- due_at всегда ISO 8601 и сохраняет именно названные пользователем локальные часы/минуты;
- due_timezone — IANA timezone только если пользователь явно назвал другой пояс,
  иначе используй переданный timezone пользователя;
- относительные даты считай от переданного текущего локального времени;
- если дата или время неоднозначны и их нельзя надежно вывести, НЕ создавай reminder,
  а задай один короткий уточняющий вопрос;
- recurrence: none, daily, weekly или monthly;
- просьба регулярно присылать отчет по проекту — reminder_kind=project_report;
- обычное напоминание — notification.

Организуй информацию по проектам. Если пользователь явно упоминает новый проект,
можно дать ему короткое естественное название и создать note. Не плодить проекты для
каждой бытовой мелочи. Сохраняй memory только для устойчивых и полезных фактов или
предпочтений, сказанных самим пользователем. Не сохраняй пароли, токены, медицинские,
финансовые и другие чувствительные данные. Пользователь видит и может удалить память.
Для отмены конкретного напоминания используй cancel_reminder только если известен id.
"""

MEMORY_PROMPT = """Извлеки из НОВОГО сообщения пользователя только долговременные факты,
которые сделают персонального помощника полезнее в будущих разговорах. Подходят: имя,
язык общения, устойчивые предпочтения, привычный распорядок, стиль работы, долгосрочные
цели, роли, люди и проекты с понятной связью с пользователем. Учитывай контекст, чтобы
нормализовать факт, но не извлекай факты из старой переписки повторно.

Не сохраняй разовые просьбы, текущие задания и предположения. Никогда не сохраняй пароли,
API-ключи, токены, платежные данные, точные адреса, медицинские, интимные и иные чувствительные
сведения. Если подходящего факта нет, верни пустой массив. fact_key делай коротким и стабильным,
чтобы новое значение того же факта обновляло старое. fact_value формулируй без домыслов.
"""


class AIService:
    def __init__(self, api_key: str, text_model: str, transcribe_model: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.text_model = text_model
        self.transcribe_model = transcribe_model

    async def transcribe(self, audio: bytes, filename: str = "voice.ogg") -> str:
        result = await self.client.audio.transcriptions.create(
            model=self.transcribe_model,
            file=(filename, audio, "audio/ogg"),
            prompt=(
                "Голосовая заметка персональному ассистенту. Возможна смесь русского, "
                "казахского и английского. Точно сохраняй имена, даты, время и названия проектов."
            ),
            response_format="json",
        )
        return result.text.strip()

    async def understand(
        self, text: str, timezone_name: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        now = datetime.now(ZoneInfo(timezone_name))
        payload = {
            "current_local_datetime": now.isoformat(),
            "timezone": timezone_name,
            "known_context": context,
            "user_message": text,
        }
        response = await self.client.responses.create(
            model=self.text_model,
            instructions=SYSTEM_PROMPT,
            input=json.dumps(payload, ensure_ascii=False, default=str),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "assistant_actions",
                    "strict": True,
                    "schema": ACTION_SCHEMA,
                }
            },
        )
        return json.loads(response.output_text)

    async def extract_memories(
        self, text: str, timezone_name: str, context: Dict[str, Any]
    ) -> list[Dict[str, Any]]:
        payload = {
            "timezone": timezone_name,
            "known_memories": context.get("memories", []),
            "recent_conversation": context.get("conversation_history", []),
            "new_user_message": text,
        }
        response = await self.client.responses.create(
            model=self.text_model,
            instructions=MEMORY_PROMPT,
            input=json.dumps(payload, ensure_ascii=False, default=str),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "personal_memories",
                    "strict": True,
                    "schema": MEMORY_SCHEMA,
                }
            },
        )
        return json.loads(response.output_text).get("memories", [])

    async def make_report(self, data: Dict[str, Any]) -> str:
        response = await self.client.responses.create(
            model=self.text_model,
            instructions=(
                "Составь короткий полезный отчет персонального помощника. Разделы: "
                "что известно, последние заметки, ближайшие дела, риски/следующий шаг. "
                "Не выдумывай факты. Для сроков используй due_at_local и явно указанный "
                "часовой пояс, не UTC. Если данных мало, честно скажи это. Ответ на русском."
            ),
            input=json.dumps(data, ensure_ascii=False, default=str),
        )
        return response.output_text.strip()
