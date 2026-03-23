from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.filters.command import CommandObject
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultAudio,
    Message,
    ReplyKeyboardRemove,
    WebAppInfo,
)
import httpx

from backend_client import BackendClient
from config import get_settings


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

router = Router()
backend_client = BackendClient()


def _build_inline_performer(description: str | None) -> str | None:
    if not description:
        return None

    normalized = " ".join(description.split()).strip()
    if not normalized:
        return None

    return normalized[:64]


def _build_start_keyboard(settings) -> InlineKeyboardMarkup | None:
    webapp_url = settings.WEBAPP_URL.strip()
    if not webapp_url.lower().startswith("https://"):
        logger.warning(
            "WEBAPP_URL=%s is not HTTPS; skipping Telegram Web App button in /start",
            webapp_url,
        )
        return None

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Open Clips Admin",
                    web_app=WebAppInfo(url=webapp_url),
                )
            ]
        ],
    )


@router.message(CommandStart(deep_link=True))
async def handle_deep_link_start(message: Message, command: CommandObject) -> None:
    args = (command.args or "").strip()
    if args.startswith("invite_"):
        invite_token = args.removeprefix("invite_").strip()
        if not invite_token:
            await message.answer("This invite link is incomplete. Ask the admin for a fresh one.")
            return

        from_user = message.from_user
        if from_user is None:
            await message.answer("Telegram did not provide your account details. Please try again.")
            return

        try:
            result = await backend_client.consume_uploader_invite(
                invite_token=invite_token,
                telegram_id=from_user.id,
                telegram_username=from_user.username,
                first_name=from_user.first_name,
                last_name=from_user.last_name,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                await message.answer("This uploader invite has expired. Ask the admin for a fresh link.")
                return
            if exc.response.status_code == 404:
                await message.answer("This uploader invite was not found. Ask the admin to generate a new one.")
                return
            if exc.response.status_code == 409:
                await message.answer("This uploader invite has already been used or revoked.")
                return
            logger.exception("Uploader invite consumption failed with HTTP error")
            await message.answer("I couldn't activate uploader access right now. Please try again in a moment.")
            return
        except Exception:
            logger.exception("Uploader invite consumption failed")
            await message.answer("I couldn't activate uploader access right now. Please try again in a moment.")
            return

        settings = get_settings()
        keyboard = _build_start_keyboard(settings)
        approved_name = result.get("approved_display_name") or from_user.full_name
        invite_text = f"Uploader access is now active for {approved_name}."
        if keyboard is None:
            invite_text += "\n\nOpen the site in a browser or ask the admin to enable a valid HTTPS WEBAPP_URL."
            await message.answer(invite_text, reply_markup=ReplyKeyboardRemove())
            return

        invite_text += "\n\nYou can open the admin app with the button below."
        await message.answer(invite_text, reply_markup=ReplyKeyboardRemove())
        await message.answer("Open Clips Admin", reply_markup=keyboard)
        return

    if not args.startswith("login_"):
        await handle_start(message)
        return

    challenge_token = args.removeprefix("login_").strip()
    if not challenge_token:
        await message.answer("This login link is incomplete. Return to the site and start login again.")
        return

    from_user = message.from_user
    if from_user is None:
        await message.answer("Telegram did not provide your account details. Please try again.")
        return

    try:
        result = await backend_client.confirm_browser_login(
            challenge_token=challenge_token,
            telegram_id=from_user.id,
            telegram_username=from_user.username,
            first_name=from_user.first_name,
            last_name=from_user.last_name,
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            await message.answer("This browser login link has expired. Return to the site and request a fresh one.")
            return
        if exc.response.status_code == 404:
            await message.answer("This browser login link was not found. Start the login flow again from the site.")
            return
        if exc.response.status_code == 409:
            await message.answer("This browser login link has already been used. Return to the site and start a new login.")
            return
        logger.exception("Browser login confirmation failed with HTTP error")
        await message.answer("I couldn't confirm the browser login right now. Please try again in a moment.")
        return
    except Exception:
        logger.exception("Browser login confirmation failed")
        await message.answer("I couldn't confirm the browser login right now. Please try again in a moment.")
        return

    approved_name = result.get("approved_display_name") or from_user.full_name
    await message.answer(
        f"Browser login confirmed for {approved_name}. Return to the site to finish signing in.",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    settings = get_settings()
    keyboard = _build_start_keyboard(settings)
    text = "Use inline mode to search clips: @%s query" % settings.TELEGRAM_BOT_USERNAME

    await message.answer(
        "Refreshing bot controls…",
        reply_markup=ReplyKeyboardRemove(),
    )

    if keyboard is None:
        text += "\n\nAdmin Web App is disabled in Telegram until WEBAPP_URL uses HTTPS."
        await message.answer(text)
        return

    text += "\n\nOpen the admin Mini App with the button below."
    await message.answer(text, reply_markup=keyboard)


@router.inline_query()
async def handle_inline_query(inline_query: InlineQuery) -> None:
    clips = await backend_client.search_clips(inline_query.query, limit=10)
    results = [
        InlineQueryResultAudio(
            id=clip["id"],
            audio_url=clip["audio_url"],
            title=clip["title"],
            performer=_build_inline_performer(clip.get("description")),
            audio_duration=int((clip.get("duration_ms") or 0) / 1000),
        )
        for clip in clips
        if clip.get("audio_url")
    ]
    await inline_query.answer(results=results, cache_time=5, is_personal=False)


async def main() -> None:
    settings = get_settings()
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    logger.info("Bot started")
    try:
        await dispatcher.start_polling(bot)
    finally:
        await backend_client.aclose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
