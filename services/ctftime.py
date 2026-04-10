from datetime import datetime, timedelta, timezone
from typing import Dict, List
from urllib.parse import urlencode

import aiohttp


def format_discord_timestamp(dt: datetime) -> str:
    unix_ts = int(dt.timestamp())
    return f"<t:{unix_ts}:F> (<t:{unix_ts}:R>)"


def parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def fetch_upcoming_events(limit: int, lookahead_days: int) -> List[Dict]:
    now = datetime.now(timezone.utc)
    finish = now + timedelta(days=lookahead_days)
    params = {
        "limit": str(limit),
        "start": str(int(now.timestamp())),
        "finish": str(int(finish.timestamp())),
    }
    url = f"https://ctftime.org/api/v1/events/?{urlencode(params)}"

    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as response:
            response.raise_for_status()
            data = await response.json()

    if not isinstance(data, list):
        return []

    upcoming = []
    for event in data:
        try:
            start_dt = parse_iso_datetime(event["start"])
            if start_dt >= now:
                upcoming.append(event)
        except Exception:
            continue

    upcoming.sort(key=lambda x: x.get("start", ""))
    return upcoming
