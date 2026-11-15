"""Bridge configuration, from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    serve_root: Path
    identity: str
    identity_dir: Path
    token: str
    web_url: str
    state_dir: Path
    hear: str            # "all" or "mentions"
    hear_bots: bool
    hourly_cap: int
    proxy: str | None

    @property
    def chat_url(self) -> str:
        # The web API names an identity by its root-relative path, / -> ~.
        rel = self.identity_dir.relative_to(self.serve_root)
        return f"{self.web_url}/api/identities/{str(rel).replace('/', '~')}/chat"


def _default_identity(serve_root: Path) -> str:
    for base in (".identities", "identities"):
        link = serve_root / base / "default"
        if link.exists():
            return link.resolve().name
    raise SystemExit(
        "headlong-discord-bridge: no identity given and no default set under "
        f"{serve_root}. Set HEADLONG_DISCORD_IDENTITY."
    )


def _find_identity_dir(serve_root: Path, name: str) -> Path:
    for base in (".identities", "identities"):
        candidate = serve_root / base / name
        if (candidate / "info.txt").is_file():
            return candidate
    raise SystemExit(f"headlong-discord-bridge: identity '{name}' not found under {serve_root}")


def proxy_from_env() -> str | None:
    """discord.py (aiohttp) ignores proxy env vars unless told; pass one on."""
    for name in ("HTTPS_PROXY", "https_proxy"):
        if os.environ.get(name):
            return os.environ[name]
    return None


def _int_env(name: str, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(os.environ.get(name, ""))))
    except ValueError:
        return default


def load(serve_root: Path) -> Config:
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    if not token:
        raise SystemExit("headlong-discord-bridge: DISCORD_BOT_TOKEN is required")
    identity = os.environ.get("HEADLONG_DISCORD_IDENTITY") or _default_identity(serve_root)
    identity_dir = _find_identity_dir(serve_root, identity)
    state_dir = Path(os.environ.get("HEADLONG_DISCORD_STATE_DIR") or identity_dir / "run" / "discord-bridge")
    state_dir.mkdir(parents=True, exist_ok=True)
    hear = os.environ.get("DISCORD_HEAR", "mentions").strip().lower()
    if hear not in ("all", "mentions"):
        raise SystemExit("headlong-discord-bridge: DISCORD_HEAR must be 'all' or 'mentions'")
    return Config(
        serve_root=serve_root,
        identity=identity,
        identity_dir=identity_dir,
        token=token,
        web_url=(os.environ.get("HEADLONG_WEB_URL") or "http://127.0.0.1:8080").rstrip("/"),
        state_dir=state_dir,
        hear=hear,
        hear_bots=os.environ.get("DISCORD_HEAR_BOTS", "") not in ("", "0"),
        hourly_cap=_int_env("DISCORD_HOURLY_CAP", 120, 0, 100000),
        proxy=proxy_from_env(),
    )
