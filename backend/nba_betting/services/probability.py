import math

from scipy.stats import norm, poisson


LOW_COUNT_STATS = {"stl", "blk", "ast"}
HIGH_COUNT_STATS = {"pts", "reb", "pra"}


def calculate_probability(stat: str, projection: float, line: float, rmse: float = 6.0) -> float:
    """Return probability of going over the given line.

    Low-count stats use Poisson; high-count stats use Normal.
    """
    stat_key = (stat or "").lower().strip()
    if stat_key in LOW_COUNT_STATS:
        mu = max(float(projection), 0.0)
        target = math.floor(float(line))
        return float(1.0 - poisson.cdf(target, mu))

    if stat_key in HIGH_COUNT_STATS:
        denom = rmse if rmse and rmse > 0 else 1.0
        z_score = (float(projection) - float(line)) / denom
        return float(norm.cdf(z_score))

    denom = rmse if rmse and rmse > 0 else 1.0
    z_score = (float(projection) - float(line)) / denom
    return float(norm.cdf(z_score))
