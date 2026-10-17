import asyncio
import logging
import re
import shutil
from contextlib import suppress
from typing import Optional

import aiohttp
from aiogram import Bot
from aiogram.types import MenuButtonWebApp, WebAppInfo

from .storage import Storage


LOGGER = logging.getLogger(__name__)
URL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


async def _read_tunnel_url(process: asyncio.subprocess.Process) -> Optional[str]:
    if process.stdout is None:
        return None
    while True:
        line = await process.stdout.readline()
        if not line:
            return None
        text = line.decode("utf-8", errors="replace")
        match = URL_PATTERN.search(text)
        if match:
            return match.group(0)


async def _drain_output(process: asyncio.subprocess.Process) -> None:
    if process.stdout is None:
        return
    while await process.stdout.readline():
        pass


async def _set_default_menu_button(bot: Bot, url: str) -> None:
    """Omit chat_id entirely; Telegram can ignore an explicit null default scope."""
    endpoint = "https://api.telegram.org/bot{}/setChatMenuButton".format(bot.token)
    payload = {
        "menu_button": {
            "type": "web_app",
            "text": "Открыть WIMAX",
            "web_app": {"url": url},
        }
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, json=payload) as response:
                data = await response.json()
    except Exception:
        # Do not let an exception expose the token-bearing Telegram URL in logs.
        raise RuntimeError("Telegram global menu button request failed") from None
    if not data.get("ok"):
        raise RuntimeError("Telegram rejected the global menu button update")


async def tunnel_supervisor(bot: Bot, storage: Storage, port: int) -> None:
    executable = shutil.which("cloudflared")
    if not executable:
        LOGGER.warning("cloudflared is unavailable; Mini App needs WEBAPP_URL")
        return
    while True:
        process: Optional[asyncio.subprocess.Process] = None
        try:
            process = await asyncio.create_subprocess_exec(
                executable,
                "tunnel",
                "--url",
                "http://127.0.0.1:{}".format(port),
                "--no-autoupdate",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            url = await asyncio.wait_for(_read_tunnel_url(process), timeout=45)
            if not url:
                raise RuntimeError("Cloudflare did not provide a URL")
            await storage.set_app_setting("webapp_url", url)
            await _set_default_menu_button(bot, url)
            owner_user_id = await storage.get_app_setting("owner_user_id")
            if owner_user_id:
                await bot.set_chat_menu_button(
                    chat_id=int(owner_user_id),
                    menu_button=MenuButtonWebApp(
                        text="Открыть WIMAX", web_app=WebAppInfo(url=url)
                    ),
                )
            LOGGER.info("Telegram Mini App URL updated: %s", url)
            drain_task = asyncio.create_task(_drain_output(process))
            await process.wait()
            await drain_task
            LOGGER.warning("Mini App tunnel stopped; restarting")
        except asyncio.CancelledError:
            if process and process.returncode is None:
                process.terminate()
                with suppress(ProcessLookupError):
                    await process.wait()
            raise
        except Exception:
            LOGGER.exception("Mini App tunnel failed; retrying")
            if process and process.returncode is None:
                process.terminate()
                with suppress(ProcessLookupError):
                    await process.wait()
        await asyncio.sleep(5)
