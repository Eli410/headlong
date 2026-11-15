"""The bridge: Discord events in, the identity's replies out.

    inbound:  message / reaction / member join -> POST <web>/api/identities/<id>/chat
              with from_name "discord-<user>-<channel>"
    outbound: tail trajectory.jsonl -> message steps where from=<identity>
              and to=discord-* -> channel.send (or a DM)

The agent can also drive Discord directly with discord.py (see script.py
and the discord skill); the bridge only carries conversation.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque

import discord
import httpx

from . import mindlog, naming
from .config import Config

log = logging.getLogger("headlong-discord")


class HourlyCap:
    """Bound how many inbound messages may wake the mind per hour."""

    def __init__(self, cap: int):
        self.cap = cap
        self._times: deque[float] = deque()
        self.warned = False

    def allow(self, now: float | None = None) -> bool:
        if self.cap <= 0:
            return True
        now = time.time() if now is None else now
        while self._times and now - self._times[0] > 3600:
            self._times.popleft()
        if len(self._times) >= self.cap:
            return False
        self._times.append(now)
        self.warned = False
        return True


class Bridge(discord.Client):
    def __init__(self, cfg: Config):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents, proxy=cfg.proxy)
        self.cfg = cfg
        self.cap = HourlyCap(cfg.hourly_cap)
        self.http_client = httpx.AsyncClient(timeout=30)
        self._outbound: asyncio.Task | None = None

    # -- lifecycle -----------------------------------------------------------

    async def setup_hook(self) -> None:
        self._outbound = asyncio.create_task(self._run_outbound(), name="discord-outbound")

    async def on_ready(self) -> None:
        guilds = ", ".join(f"{g.name} ({g.id})" for g in self.guilds) or "none"
        log.info("connected as %s (id %s); servers: %s; hearing: %s",
                 self.user, self.user.id, guilds, self.cfg.hear)

    async def close(self) -> None:
        if self._outbound:
            self._outbound.cancel()
        await self.http_client.aclose()
        await super().close()

    # -- inbound -------------------------------------------------------------

    def _wanted(self, message: discord.Message) -> bool:
        if message.author.id == self.user.id:
            return False
        if message.author.bot and not self.cfg.hear_bots:
            return False
        if message.guild is None:
            return True                      # DMs always reach the mind
        if self.cfg.hear == "all":
            return True
        return self.user in message.mentions

    async def on_message(self, message: discord.Message) -> None:
        if not self._wanted(message):
            return
        reply_to = None
        ref = message.reference.resolved if message.reference else None
        if isinstance(ref, discord.Message):
            reply_to = "you" if ref.author.id == self.user.id else ref.author.display_name
        head = naming.header(
            display_name=message.author.display_name,
            username=message.author.name,
            user_id=message.author.id,
            is_bot=message.author.bot,
            guild=message.guild.name if message.guild else None,
            channel=getattr(message.channel, "name", None),
            channel_id=message.channel.id,
            mentioned=self.user in message.mentions,
            reply_to=reply_to,
        )
        text = naming.body(message.clean_content, [a.url for a in message.attachments])
        await self._forward(naming.from_name(message.author.id, message.channel.id), f"{head}\n{text}")

    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.abc.User) -> None:
        if user.id == self.user.id or reaction.message.author.id != self.user.id:
            return                           # only reactions to the agent's own messages
        if user.bot and not self.cfg.hear_bots:
            return
        emoji = reaction.emoji if isinstance(reaction.emoji, str) else f":{reaction.emoji.name}:"
        note = (f"(Discord: {user.display_name} (@{user.name}, id {user.id}) reacted {emoji} "
                f"to your message: {reaction.message.content[:120]!r})")
        await self._forward(naming.from_name(user.id, reaction.message.channel.id), note)

    async def on_member_join(self, member: discord.Member) -> None:
        if self.cfg.hear != "all" or not member.guild.system_channel:
            return
        note = (f"(Discord: {member.display_name} (@{member.name}, id {member.id}) "
                f"just joined the server \"{member.guild.name}\")")
        await self._forward(naming.from_name(member.id, member.guild.system_channel.id), note)

    async def _forward(self, from_name: str, content: str) -> None:
        if not self.cap.allow():
            if not self.cap.warned:
                log.warning("hourly cap of %d inbound messages reached; dropping until it clears",
                            self.cfg.hourly_cap)
                self.cap.warned = True
            return
        try:
            r = await self.http_client.post(
                self.cfg.chat_url, json={"content": content, "from_name": from_name})
            r.raise_for_status()
        except httpx.HTTPError as e:
            log.error("could not deliver inbound message to the mind: %s", e)

    # -- outbound ------------------------------------------------------------

    async def _run_outbound(self) -> None:
        await self.wait_until_ready()
        path = mindlog.find_trajectory(self.cfg.identity_dir)
        cursor = self.cfg.state_dir / "cursor"
        offset = mindlog._load_cursor(cursor, path)
        log.info("following %s", path)
        while not self.is_closed():
            try:
                steps, new_offset = mindlog.read_new(path, offset)
            except OSError as e:
                log.error("reading the mind log failed: %s", e)
                steps, new_offset = [], offset
            if new_offset != offset:
                offset = new_offset
                cursor.write_text(f"{offset} {path.resolve()}")
            for step in steps:
                if step.get("type") != "message" or step.get("from") != self.cfg.identity:
                    continue
                target = naming.parse_target(str(step.get("to", "")))
                if target is None:
                    continue
                await self._deliver(target, str(step.get("content", "")), str(step.get("to")))
            await asyncio.sleep(0.4)

    async def _deliver(self, target: naming.Target, content: str, to: str) -> None:
        try:
            if target.kind == "user":
                user = self.get_user(target.id) or await self.fetch_user(target.id)
                dest = user.dm_channel or await user.create_dm()
            else:
                dest = self.get_channel(target.id) or await self.fetch_channel(target.id)
            for part in naming.split(content):
                await dest.send(part)
            log.info("delivered to %s", to)
        except discord.DiscordException as e:
            log.error("delivery to %s failed: %s", to, e)
