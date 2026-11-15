# headlong-discord-bridge

Connects one Headlong identity to Discord through a bot account, in two parts:

1. **The bridge** carries conversation. Messages land in the identity's mind
   log as `message` steps, and its replies are posted back.
2. **`headlong-discord-py`** lets the identity run discord.py code as the bot,
   for everything that is not conversation: creating channels, roles and
   scheduled events, renaming things, reading history.

Unlike the Slack and Telegram bridges, the bot token is deliberately available
to the agent. Read "Security notes" before using this anywhere that matters.

## How it works

```
Discord <=(gateway websocket)=> headlong-discord-bridge
    inbound:  message -> from_name "discord-<user id>-<channel id>"
              -> POST <web>/api/identities/<id>/chat
              content starts with a header: who, which channel, which server
              reactions to the bot's messages and member joins arrive as notes
    outbound: tail trajectory.jsonl -> message steps where from=<identity>
              and to=discord-* -> channel.send (split at 2000 characters)

agent --(headlong-discord-py script.py)--> Discord REST API, as the bot
```

`to` names: `discord-<user>-<channel>` (reply where the message came from),
`discord-channel-<id>` (post in a channel), `discord-user-<id>` (DM).

## Setup

1. In the [Discord developer portal](https://discord.com/developers/applications)
   create an application, add a bot, and copy its token.
2. On the bot page enable the **Message Content** and **Server Members**
   privileged intents.
3. Invite the bot to a server with the `bot` scope and the permissions you
   want it to have.
4. Put the token in `~/.headlong/.env`:

   ```bash
   DISCORD_BOT_TOKEN='...'
   DISCORD_HEAR='all'        # or 'mentions' (the default)
   ```

5. Install the skill for the identity (`skills install <checkout>/skills/discord`
   in its shell) and start the bridge:

   ```bash
   tools/headlong-discord-bridge [ROOT]
   ```

The identity needs a running dispatcher, and headlong-web must be serving the
same root (`HEADLONG_WEB_URL`, default `http://127.0.0.1:8080`).

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `DISCORD_BOT_TOKEN` | required | the bot's token |
| `DISCORD_HEAR` | `mentions` | `mentions`: DMs and @mentions only. `all`: every message in every channel the bot can see. |
| `DISCORD_HEAR_BOTS` | off | forward messages from other bots |
| `DISCORD_HOURLY_CAP` | 120 | most inbound messages forwarded per hour (0 = no cap); each one wakes the mind and costs model calls |
| `HEADLONG_DISCORD_IDENTITY` | the `default` identity | which identity to connect |
| `HEADLONG_DISCORD_STATE_DIR` | `<identity>/run/discord-bridge` | cursor state |
| `HTTPS_PROXY` | unset | passed to discord.py, which ignores proxy env vars on its own |

## Tests

```bash
uv run --project discord pytest discord/tests
```

## Security notes

- **The agent holds the token.** It can do anything the bot's permissions
  allow, including destructive things, by mistake or because a message talked
  it into it. Give the bot only the permissions you would give a new member
  you do not fully trust, and start in a server you can afford to lose.
- **Prompt injection.** Every message the bridge forwards flows into the
  agent's context. With `DISCORD_HEAR=all` that is everyone in every channel.
- **One shared mind.** All conversations interleave in a single mind log.
  Anything said to the identity may surface in replies to others.
- **Cost.** In `all` mode a busy channel wakes the mind on every message.
  `DISCORD_HOURLY_CAP` bounds that.
- **Bot accounts only.** discord.py does not support automating a normal user
  account, and doing so breaks Discord's terms.
