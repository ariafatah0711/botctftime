import os
from dataclasses import dataclass
from typing import Optional


def env_int(name: str) -> Optional[int]:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None

@dataclass(frozen=True)
class Settings:
    team_name: str
    team_url: str
    team_description: str
    team_contact: str
    team_discord_invite: str

    ctf_role_id: Optional[int]
    findteam_mention_mode: str

    ctftime_notify_channel_id: Optional[int]
    ctftime_poll_minutes: int
    ctftime_lookahead_days: int
    ctftime_max_events_per_poll: int

# =================================================================
# Keep non-secret, non-ID operational defaults here.
# =================================================================
DEFAULT_TEAM_NAME = "NFCC"
DEFAULT_TEAM_URL = "https://ctftime.org/team/390784"
DEFAULT_TEAM_DESCRIPTION = "Komunitas CTF dan Cyber Security untuk belajar, sparring, dan main bareng."
DEFAULT_TEAM_CONTACT = "Hubungi admin server"
DEFAULT_TEAM_DISCORD_INVITE = ""

DEFAULT_FINDTEAM_MENTION_MODE = "everyone"  # everyone | role | none

DEFAULT_CTFTIME_POLL_MINUTES = 60
DEFAULT_CTFTIME_LOOKAHEAD_DAYS = 7
DEFAULT_CTFTIME_MAX_EVENTS_PER_POLL = 3

# =================================================================
# Load settings from environment variables, with defaults as fallback.
# =================================================================
def load_settings() -> Settings:
    return Settings(
        team_name=DEFAULT_TEAM_NAME,
        team_url=DEFAULT_TEAM_URL,
        team_description=DEFAULT_TEAM_DESCRIPTION,
        team_contact=DEFAULT_TEAM_CONTACT,
        team_discord_invite=DEFAULT_TEAM_DISCORD_INVITE,
        ctf_role_id=env_int("CTF_ROLE_ID"),
        findteam_mention_mode=os.getenv("FINDTEAM_MENTION_MODE", DEFAULT_FINDTEAM_MENTION_MODE).strip().lower(),
        ctftime_notify_channel_id=env_int("CTFTIME_NOTIFY_CHANNEL_ID"),
        ctftime_poll_minutes=DEFAULT_CTFTIME_POLL_MINUTES,
        ctftime_lookahead_days=DEFAULT_CTFTIME_LOOKAHEAD_DAYS,
        ctftime_max_events_per_poll=DEFAULT_CTFTIME_MAX_EVENTS_PER_POLL,
    )

SETTINGS = load_settings()
