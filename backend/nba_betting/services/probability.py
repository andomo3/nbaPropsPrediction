"""Probability of clearing a prop line.

Single source of truth for prob_over: ManualPredictionView and
generate_daily_picks both route through calculate_probability().

Low-count stats (ast, stl, blk) are modeled as Poisson — a discrete
distribution whose variance is tied to the mean, so no dispersion estimate
is needed and no continuity correction is missed. High-count stats
(pts, reb, pra) are modeled as Normal centered on the model projection with
the player's rolling std as dispersion. Outputs are clamped to PROB_CLAMP:
with 10-game dispersion windows and no injury/lineup information, the model
cannot support near-certain claims.
"""

import math

from scipy.stats import norm, poisson

from nba_betting.constants import PROB_CLAMP, STD_DEFAULTS, STD_FLOOR

LOW_COUNT_STATS = {"stl", "blk", "ast"}


def calculate_probability(
    stat: str,
    projection: float,
    line: float,
    std_dev: float | None = None,
) -> float:
    """Return clamped P(actual > line).

    std_dev is the player's rolling std (ignored for Poisson stats);
    None/NaN falls back to STD_DEFAULTS.
    """
    stat_key = (stat or "").lower().strip()

    if stat_key in LOW_COUNT_STATS:
        mu = max(float(projection), 0.0)
        prob = float(1.0 - poisson.cdf(math.floor(float(line)), mu))
    else:
        try:
            std = float(std_dev)
        except (TypeError, ValueError):
            std = float("nan")
        if math.isnan(std):
            std = STD_DEFAULTS.get(stat_key, 4.0)
        std = max(std, STD_FLOOR)
        prob = float(1.0 - norm.cdf((float(line) - float(projection)) / std))

    lo, hi = PROB_CLAMP
    return float(min(hi, max(lo, prob)))
