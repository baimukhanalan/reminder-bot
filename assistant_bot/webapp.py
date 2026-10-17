import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from aiohttp import web

from .ai import AIService
from .config import Settings
from .service import AssistantService
from .storage import Storage
from .web_auth import WebAppAuthError, validate_init_data


LOGGER = logging.getLogger(__name__)
MAX_AUDIO_BYTES = 20 * 1024 * 1024


def json_response(data: Any, status: int = 200) -> web.Response:
    return web.json_response(data, status=status, dumps=lambda value: json.dumps(value, ensure_ascii=False))


def create_web_app(
    settings: Settings, storage: Storage, ai: AIService
) -> web.Application:
    app = web.Application(client_max_size=MAX_AUDIO_BYTES + 1024 * 1024)
    service = AssistantService(storage, ai, settings.default_timezone)
    static_root = Path(__file__).resolve().parent.parent / "webapp" / "dist"

    async def authenticate(request: web.Request) -> int:
        init_data = request.headers.get("X-Telegram-Init-Data", "")
        if init_data:
            identity = validate_init_data(init_data, settings.telegram_token)
            user_id = identity["user_id"]
        elif settings.dev_user_id and request.remote in {"127.0.0.1", "::1", None}:
            user_id = settings.dev_user_id
        else:
            raise web.HTTPUnauthorized(text="Open this app from Telegram")

        if settings.allowed_user_ids:
            allowed = user_id in settings.allowed_user_ids
        else:
            allowed = await storage.claim_or_check_owner(user_id)
        if not allowed:
            raise web.HTTPForbidden(text="This assistant is private")
        await storage.ensure_user(user_id, user_id, settings.default_timezone)
        return user_id

    @web.middleware
    async def error_middleware(request: web.Request, handler):
        try:
            return await handler(request)
        except web.HTTPException:
            raise
        except WebAppAuthError as exc:
            raise web.HTTPUnauthorized(text=str(exc))
        except Exception:
            LOGGER.exception("Mini App request failed: %s", request.path)
            return json_response({"error": "Не удалось выполнить запрос"}, 500)

    app.middlewares.append(error_middleware)

    async def dashboard(request: web.Request) -> web.Response:
        user_id = await authenticate(request)
        return json_response(await storage.dashboard(user_id))

    async def process_text(request: web.Request) -> web.Response:
        user_id = await authenticate(request)
        body = await request.json()
        text = str(body.get("text", "")).strip()
        if not text or len(text) > 4000:
            return json_response({"error": "Введите текст до 4000 символов"}, 400)
        reply = await service.process(user_id, user_id, text, "mini_app")
        return json_response({"reply": reply, "dashboard": await storage.dashboard(user_id)})

    async def transcribe(request: web.Request) -> web.Response:
        await authenticate(request)
        reader = await request.multipart()
        part = await reader.next()
        if part is None or part.name != "audio":
            return json_response({"error": "Аудиофайл не найден"}, 400)
        chunks = []
        size = 0
        while True:
            chunk = await part.read_chunk()
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_AUDIO_BYTES:
                return json_response({"error": "Аудио больше 20 МБ"}, 413)
            chunks.append(chunk)
        filename = part.filename or "voice.webm"
        transcript = await ai.transcribe(b"".join(chunks), filename)
        return json_response({"transcript": transcript})

    async def cancel_reminder(request: web.Request) -> web.Response:
        user_id = await authenticate(request)
        ok = await storage.cancel_reminder(user_id, int(request.match_info["item_id"]))
        return json_response({"ok": ok, "dashboard": await storage.dashboard(user_id)})

    async def delete_note(request: web.Request) -> web.Response:
        user_id = await authenticate(request)
        ok = await storage.delete_note(user_id, int(request.match_info["item_id"]))
        return json_response({"ok": ok, "dashboard": await storage.dashboard(user_id)})

    async def delete_memory(request: web.Request) -> web.Response:
        user_id = await authenticate(request)
        ok = await storage.delete_memory(user_id, int(request.match_info["item_id"]))
        return json_response({"ok": ok, "dashboard": await storage.dashboard(user_id)})

    async def delete_project(request: web.Request) -> web.Response:
        user_id = await authenticate(request)
        ok = await storage.delete_project(user_id, int(request.match_info["item_id"]))
        return json_response({"ok": ok, "dashboard": await storage.dashboard(user_id)})

    async def report(request: web.Request) -> web.Response:
        user_id = await authenticate(request)
        body = await request.json()
        project = body.get("project")
        text = await service.report(user_id, str(project) if project else None)
        return json_response({"report": text})

    async def create_project(request: web.Request) -> web.Response:
        user_id = await authenticate(request)
        body = await request.json()
        name = str(body.get("name", "")).strip()
        description = str(body.get("description", "")).strip()
        if not name or len(name) > 100 or len(description) > 500:
            return json_response({"error": "Проверьте название и описание проекта"}, 400)
        await storage.get_or_create_project(user_id, name, description)
        return json_response({"dashboard": await storage.dashboard(user_id)})

    async def health(_: web.Request) -> web.Response:
        return json_response({"status": "ok"})

    async def index(_: web.Request) -> web.StreamResponse:
        index_path = static_root / "index.html"
        if not index_path.exists():
            raise web.HTTPServiceUnavailable(text="Mini App frontend is not built")
        return web.FileResponse(index_path)

    app.router.add_get("/healthz", health)
    app.router.add_get("/api/dashboard", dashboard)
    app.router.add_post("/api/assistant/process", process_text)
    app.router.add_post("/api/voice/transcribe", transcribe)
    app.router.add_delete("/api/reminders/{item_id}", cancel_reminder)
    app.router.add_delete("/api/notes/{item_id}", delete_note)
    app.router.add_delete("/api/memories/{item_id}", delete_memory)
    app.router.add_delete("/api/projects/{item_id}", delete_project)
    app.router.add_post("/api/report", report)
    app.router.add_post("/api/projects", create_project)
    if static_root.exists():
        app.router.add_static("/assets", static_root / "assets", show_index=False)
    app.router.add_get("/{tail:.*}", index)
    return app


async def start_web_server(
    settings: Settings, storage: Storage, ai: AIService
) -> web.AppRunner:
    runner = web.AppRunner(create_web_app(settings, storage, ai))
    await runner.setup()
    site = web.TCPSite(runner, settings.webapp_host, settings.webapp_port)
    await site.start()
    LOGGER.info("Mini App server listening on %s:%s", settings.webapp_host, settings.webapp_port)
    return runner
