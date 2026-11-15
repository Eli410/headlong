from headlong_discord import naming
from headlong_discord.bridge import HourlyCap


def test_round_trip_reply_target():
    name = naming.from_name(111, 222)
    assert name == "discord-111-222"
    assert naming.parse_target(name) == naming.Target("channel", 222)


def test_proactive_targets():
    assert naming.parse_target("discord-channel-5") == naming.Target("channel", 5)
    assert naming.parse_target("discord-user-7") == naming.Target("user", 7)


def test_non_discord_names_are_ignored():
    for name in ("operator", "slack-U1-C2", "discord-", "discord-abc-1", "discord-1-2-3", "xdiscord-1-2"):
        assert naming.parse_target(name) is None


def test_header_server_and_dm():
    h = naming.header(display_name="Eli", username="eli410", user_id=1, is_bot=False,
                      guild="Lab", channel="general", channel_id=9, mentioned=True, reply_to="you")
    assert h == ('(Discord: Eli (@eli410, id 1) in #general (channel id 9) of the server "Lab"'
                 ", mentioning you, replying to you)")
    dm = naming.header(display_name="Eli", username="eli410", user_id=1, is_bot=True,
                       guild=None, channel=None, channel_id=9, mentioned=False)
    assert dm == "(Discord: Eli (@eli410, id 1), a bot in a direct message)"


def test_body():
    assert naming.body("  hi ", []) == "hi"
    assert naming.body("", ["https://x/a.png"]) == "[attachment] https://x/a.png"
    assert naming.body("", []) == "[no text]"


def test_split_respects_limit_and_keeps_text():
    text = "\n".join(f"line {i} " + "x" * 50 for i in range(200))
    parts = naming.split(text)
    assert all(0 < len(p) <= naming.DISCORD_MAX for p in parts)
    assert "".join(parts).replace("\n", "").replace(" ", "") == text.replace("\n", "").replace(" ", "")
    assert naming.split("   ") == []
    assert naming.split("a" * 4500, 2000) == ["a" * 2000, "a" * 2000, "a" * 500]


def test_hourly_cap():
    cap = HourlyCap(2)
    assert cap.allow(0) and cap.allow(1)
    assert not cap.allow(2)
    assert cap.allow(3601)          # the first one aged out
    assert HourlyCap(0).allow()     # 0 disables the cap
