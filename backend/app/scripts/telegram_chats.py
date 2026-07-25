"""Discover Telegram chat ids for @QuataAlertsBot recipients.

Finding a chat id is the fiddliest step of setting the bot up: the official
route is to hand-read a raw ``getUpdates`` JSON blob. This does it for you.

    cd /home/Quata-Digital/backend
    source .venv/bin/activate
    python -m app.scripts.telegram_chats

Then paste the id into **Admin → Alert centre → Recipients**.

    --add-all       register every discovered chat as an active recipient
    --send-hello    send a confirmation message to each discovered chat

Note: ``getUpdates`` only returns messages from roughly the last 24 hours,
and returns *nothing* while a webhook is set. If the list comes back empty,
message the bot (or post in the group) and run this again.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

from app.core.logging_config import configure_logging


def _fetch_updates(token: str, api_base: str) -> list[dict]:
    url = f"{api_base.rstrip('/')}/bot{token}/getUpdates"
    with urllib.request.urlopen(url, timeout=15) as response:
        body = json.loads(response.read().decode("utf-8"))
    if not body.get("ok"):
        raise RuntimeError(body.get("description") or "Telegram rejected getUpdates")
    return body.get("result") or []


def _chats_from_updates(updates: list[dict]) -> dict[str, dict]:
    """Collapse the update stream into one entry per distinct chat."""
    chats: dict[str, dict] = {}
    for update in updates:
        message = (
            update.get("message")
            or update.get("edited_message")
            or update.get("channel_post")
            or {}
        )
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            continue
        name = (
            chat.get("title")
            or " ".join(filter(None, [chat.get("first_name"), chat.get("last_name")]))
            or chat.get("username")
            or f"Chat {chat_id}"
        )
        chats[str(chat_id)] = {
            "chat_id": str(chat_id),
            "label": name,
            "type": chat.get("type", "private"),
            "username": chat.get("username"),
        }
    return chats


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover @QuataAlertsBot chat ids")
    parser.add_argument("--add-all", action="store_true",
                        help="register every discovered chat as an active recipient")
    parser.add_argument("--send-hello", action="store_true",
                        help="send a confirmation message to each discovered chat")
    args = parser.parse_args()

    configure_logging()

    from app.core.config import settings
    from app.services.notifications import telegram

    token = telegram.get_bot_token()
    if not token:
        print(
            "No bot token configured. Set it in Admin → Site settings → "
            "Integrations, or TELEGRAM_BOT_TOKEN in backend/.env.",
            file=sys.stderr,
        )
        return 1

    identity = telegram.get_me()
    if not identity.get("ok"):
        print(f"Telegram rejected the token: {identity.get('error')}", file=sys.stderr)
        return 2
    print(f"Bot: @{identity.get('username')} (id {identity.get('bot_id')})\n")

    try:
        updates = _fetch_updates(token, settings.TELEGRAM_API_BASE)
    except Exception as exc:  # noqa: BLE001
        print(f"Couldn't fetch updates: {exc}", file=sys.stderr)
        return 3

    chats = _chats_from_updates(updates)
    if not chats:
        print(
            "No chats found.\n\n"
            "  • Message @" + str(identity.get("username")) + " from the admin's "
            "Telegram account, or add the bot to the ops group and post once.\n"
            "  • getUpdates only covers the last ~24 hours.\n"
            "  • It returns nothing while a webhook is set "
            "(clear it with deleteWebhook).\n"
            "Then run this again."
        )
        return 0

    print(f"Found {len(chats)} chat(s):\n")
    for chat in chats.values():
        kind = "group" if chat["chat_id"].startswith("-") else chat["type"]
        handle = f" @{chat['username']}" if chat.get("username") else ""
        print(f"  {chat['chat_id']:<20} {chat['label']}{handle}  [{kind}]")

    if args.send_hello:
        print("\nSending confirmation messages…")
        for chat in chats.values():
            result = telegram.send_message(
                chat["chat_id"],
                "<b>🔔 QUATA ALERT</b>\n\nThis chat can receive QUATA notifications.\n"
                "Add it under Admin → Alert centre → Recipients to start receiving them.",
            )
            print(f"  {chat['chat_id']}: {'ok' if result.ok else result.error}")

    if args.add_all:
        from app.db.session import SessionLocal
        from app.models import NotificationRecipient

        added = 0
        with SessionLocal() as db:
            for chat in chats.values():
                exists = (
                    db.query(NotificationRecipient)
                    .filter(NotificationRecipient.chat_id == chat["chat_id"])
                    .first()
                )
                if exists:
                    continue
                db.add(
                    NotificationRecipient(
                        chat_id=chat["chat_id"],
                        label=chat["label"][:120],
                        is_active=True,
                        is_group=chat["chat_id"].startswith("-"),
                        min_priority="info",
                        platforms=[],
                        categories=[],
                    )
                )
                added += 1
            db.commit()
        print(f"\nRegistered {added} new recipient(s). Existing ones were left untouched.")
    else:
        print("\nAdd these under Admin → Alert centre → Recipients, "
              "or re-run with --add-all.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
