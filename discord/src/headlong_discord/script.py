"""Run discord.py code as the bot, for one-off actions.

The bridge carries conversation. Everything else discord.py can do (create
channels, roles and scheduled events, rename things, read history, manage
members) the agent does by writing a short script:

    from headlong_discord.script import run

    async def main(client):
        guild = await client.fetch_guild(123456789012345678)
        await guild.create_text_channel("book-club")

    run(main)

`run` logs in over REST only, with no gateway connection, so it does not
disturb the running bridge. That means caches are empty: use the fetch_*
methods (client.fetch_guild, guild.fetch_channels, client.fetch_channel,
client.fetch_user, guild.fetch_member) rather than the get_* ones.
"""

from __future__ import annotations

import asyncio
import os
from typing import Awaitable, Callable

import discord

from .config import proxy_from_env


def run(main: Callable[[discord.Client], Awaitable[object]]) -> object:
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    if not token:
        raise SystemExit("DISCORD_BOT_TOKEN is not set")

    async def _go() -> object:
        client = discord.Client(intents=discord.Intents.none(), proxy=proxy_from_env())
        await client.login(token)
        try:
            return await main(client)
        finally:
            await client.close()

    return asyncio.run(_go())
