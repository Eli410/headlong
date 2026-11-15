"""Chat names and message text for the Discord bridge. Pure functions.

A Discord conversation is packed into the chat `from` name, and the reply
path hands the same name back as `to`, so the trajectory schema and the
agent need no changes (the same design as the Slack and Telegram bridges).

    discord-<user id>-<channel id>   a message from that user in that channel
                                     (a DM is a channel too); reply target
    discord-channel-<channel id>     post in a channel with no earlier message
    discord-user-<user id>           DM a person with no earlier message
"""

from __future__ import annotations

import re
from dataclasses import dataclass

DISCORD_MAX = 2000

_REPLY_RE = re.compile(r"^discord-(\d+)-(\d+)$")
_CHANNEL_RE = re.compile(r"^discord-channel-(\d+)$")
_USER_RE = re.compile(r"^discord-user-(\d+)$")


@dataclass(frozen=True)
class Target:
    kind: str          # "channel" or "user"
    id: int


def from_name(user_id: int, channel_id: int) -> str:
    return f"discord-{user_id}-{channel_id}"


def parse_target(to: str) -> Target | None:
    """Where a `to` name delivers, or None if it is not a Discord name."""
    if m := _REPLY_RE.match(to):
        return Target("channel", int(m.group(2)))
    if m := _CHANNEL_RE.match(to):
        return Target("channel", int(m.group(1)))
    if m := _USER_RE.match(to):
        return Target("user", int(m.group(1)))
    return None


def header(
    *,
    display_name: str,
    username: str,
    user_id: int,
    is_bot: bool,
    guild: str | None,
    channel: str | None,
    channel_id: int,
    mentioned: bool,
    reply_to: str | None = None,
) -> str:
    """One readable line saying who is talking and where."""
    who = f"{display_name} (@{username}, id {user_id})"
    if is_bot:
        who += ", a bot"
    if guild is None:
        where = "in a direct message"
    else:
        where = f"in #{channel} (channel id {channel_id}) of the server \"{guild}\""
    extra = ""
    if mentioned:
        extra += ", mentioning you"
    if reply_to:
        extra += f", replying to {reply_to}"
    return f"(Discord: {who} {where}{extra})"


def body(content: str, attachments: list[str]) -> str:
    text = content.strip()
    if attachments:
        text = (text + "\n" if text else "") + "\n".join(f"[attachment] {u}" for u in attachments)
    return text or "[no text]"


def split(text: str, limit: int = DISCORD_MAX) -> list[str]:
    """Split a message into pieces Discord accepts, preferring line breaks."""
    text = text.strip()
    if not text:
        return []
    parts: list[str] = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = text.rfind(" ", 0, limit)
        if cut < limit // 2:
            cut = limit
        parts.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    if text:
        parts.append(text)
    return parts
