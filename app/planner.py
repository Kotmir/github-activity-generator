"""Pure scheduling logic: which day gets how many commits.

No git and no file system here, so the UI preview and the real run use
exactly the same code (and the same seed gives the same graph)."""
from __future__ import annotations

import random
from datetime import datetime, timedelta

COMMIT_HOUR = 20


def build_schedule(cfg, now=None, seed=None):
    """Return [(day, commits)] for every day of the period (zeros incl.).

    The period is [today - days_before, today + days_after). `day` is a
    datetime at 20:00; consecutive commits of a day go one minute apart.
    """
    now = now or datetime.now()
    rng = random.Random(cfg.seed if seed is None else seed)
    first = now.replace(hour=COMMIT_HOUR, minute=0, second=0,
                        microsecond=0) - timedelta(days=cfg.days_before)
    schedule = []
    for n in range(cfg.days_before + cfg.days_after):
        day = first + timedelta(days=n)
        count = 0
        weekend_off = cfg.no_weekends and day.weekday() >= 5
        if not weekend_off and rng.random() * 100 < cfg.frequency:
            count = rng.randint(1, cfg.max_commits)
        schedule.append((day, count))
    return schedule


def summarize(schedule):
    counts = [c for _, c in schedule]
    active = [c for c in counts if c > 0]
    return {
        'total': sum(counts),
        'active_days': len(active),
        'max_per_day': max(counts, default=0),
    }


def commit_message(moment):
    return moment.strftime('Contribution: %Y-%m-%d %H:%M')
