"""
services/simulator.py

Season Simulator: fits an AR(1) process to a player's 2025-26 game-by-game
residuals and runs Monte Carlo to produce a forward-looking fan chart.

Steps:
  1. Load player history, filter to the 2025-26 season window.
  2. Compute season average μ and per-game residuals r[t] = x[t] - μ.
  3. Fit AR(1): r[t] = φ * r[t-1] + ε,  ε ~ N(0, σ_ε).
  4. Run N simulations of n_future games, each starting from the last observed
     residual, generating values via: x_t = max(0, μ + φ*r_prev + σ_ε*z).
  5. Return per-quantile projection bands and a prop-probability table.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from nba_betting.constants import SEASON_DATES
from nba_betting.services.features import (
    _add_rolling_features,
    _find_player,
    _load_player_history,
)

N_SIMS    = 1000
N_FUTURE  = 20       # games to simulate forward
SEASON    = 2026     # hard-coded to 2025-26


def run_simulation(
    player_name: str,
    stat: str,
    n_future: int = N_FUTURE,
    n_sims: int = N_SIMS,
    seed: int | None = 42,
) -> dict[str, Any]:
    """
    Fit AR(1) to player's 2025-26 game log and run Monte Carlo forward.

    Returns:
        player_name, stat, season_avg, games_played, ar1_phi, ar1_sigma,
        actual: list of {game_num, date, value, opponent},
        projections: list of {game_num, p10, p25, p50, p75, p90},
        prop_table: list of {line, prob_over}
    """
    rng = np.random.default_rng(seed)

    player = _find_player(player_name)
    if not player:
        raise ValueError(f"Player not found: {player_name!r}")

    history_df = _load_player_history(player)
    if history_df.empty:
        raise ValueError(f"No historical stats for {player_name!r}")

    history_df = _add_rolling_features(history_df)
    history_df = history_df[history_df["min"] > 0].reset_index(drop=True)

    # ── Filter to 2025-26 season ──────────────────────────────────────────────
    date_from, date_to = SEASON_DATES[SEASON]
    history_df["date"] = pd.to_datetime(history_df["date"])
    mask = (
        (history_df["date"].dt.date >= date_from)
        & (history_df["date"].dt.date <= date_to)
    )
    season_df = history_df[mask].reset_index(drop=True)

    if season_df.empty:
        raise ValueError(f"No 2025-26 data for {player_name!r}")

    values = season_df[stat].astype(float).values
    dates  = season_df["date"].dt.strftime("%Y-%m-%d").tolist()
    opps   = season_df["opponent"].fillna("").tolist()

    # ── Season average and residuals ──────────────────────────────────────────
    mu  = float(np.mean(values))
    res = values - mu          # residuals: r[t] = x[t] - μ

    # ── Fit AR(1): φ = cov(r[t], r[t-1]) / var(r[t-1]) ──────────────────────
    phi, sigma_eps = _fit_ar1(res)

    # ── Build actual-games list ───────────────────────────────────────────────
    actual = [
        {
            "game_num": i + 1,
            "date":     dates[i],
            "value":    round(float(values[i]), 1),
            "opponent": opps[i],
        }
        for i in range(len(values))
    ]

    # ── Monte Carlo forward simulation ────────────────────────────────────────
    games_played  = len(values)
    last_residual = float(res[-1]) if len(res) > 0 else 0.0

    # Shape: (n_sims, n_future)
    sim_matrix = _simulate_paths(
        mu, phi, sigma_eps, last_residual, n_future, n_sims, rng
    )

    # Quantiles per future game slot
    quantiles = [10, 25, 50, 75, 90]
    projections = [
        {
            "game_num": games_played + g + 1,
            **{
                f"p{q}": round(float(np.percentile(sim_matrix[:, g], q)), 1)
                for q in quantiles
            },
        }
        for g in range(n_future)
    ]

    # ── Prop probability table ────────────────────────────────────────────────
    # Build lines around the median across all future sims
    all_future_flat = sim_matrix.flatten()
    prop_table = _build_prop_table(all_future_flat, mu)

    return {
        "player_name":   player_name,
        "stat":          stat,
        "season":        "2025-26",
        "season_avg":    round(mu, 2),
        "games_played":  games_played,
        "n_future":      n_future,
        "ar1_phi":       round(phi, 4),
        "ar1_sigma":     round(sigma_eps, 4),
        "actual":        actual,
        "projections":   projections,
        "prop_table":    prop_table,
    }


# ── AR(1) fitting ─────────────────────────────────────────────────────────────

def _fit_ar1(residuals: np.ndarray) -> tuple[float, float]:
    """
    OLS estimate of AR(1) coefficient φ and innovation std σ_ε.
    Returns (phi, sigma_eps), φ clamped to (-0.95, 0.95) for stationarity.
    """
    if len(residuals) < 4:
        return 0.0, float(np.std(residuals)) if len(residuals) > 0 else 1.0

    r_prev = residuals[:-1]
    r_curr = residuals[1:]

    var_prev = float(np.var(r_prev))
    if var_prev < 1e-8:
        return 0.0, float(np.std(residuals))

    phi = float(np.dot(r_curr, r_prev) / (len(r_prev) * var_prev))
    phi = float(np.clip(phi, -0.95, 0.95))

    innovations = r_curr - phi * r_prev
    sigma_eps   = float(np.std(innovations)) if len(innovations) > 1 else 1.0
    sigma_eps   = max(sigma_eps, 0.5)     # floor to avoid degenerate sims

    return phi, sigma_eps


# ── Monte Carlo ───────────────────────────────────────────────────────────────

def _simulate_paths(
    mu: float,
    phi: float,
    sigma_eps: float,
    last_residual: float,
    n_future: int,
    n_sims: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Return (n_sims, n_future) matrix of simulated stat values (clipped >= 0)."""
    # noise matrix: (n_sims, n_future)
    noise = rng.normal(0.0, sigma_eps, size=(n_sims, n_future))

    paths = np.empty((n_sims, n_future), dtype=float)
    r = np.full(n_sims, last_residual, dtype=float)

    for t in range(n_future):
        r = phi * r + noise[:, t]
        paths[:, t] = np.maximum(mu + r, 0.0)

    return paths


# ── Prop table ────────────────────────────────────────────────────────────────

def _build_prop_table(values: np.ndarray, mu: float) -> list[dict]:
    """
    Generate 8 lines spaced ~2.5 apart centred on mu,
    reporting the simulated P(over line) for each.
    """
    # Round mu to nearest 0.5, then build 4 lines below and 3 above
    centre = round(mu * 2) / 2.0   # nearest 0.5
    step   = 2.5

    lines = sorted({round(centre + step * i - 0.5, 1) for i in range(-3, 5)})
    lines = [l for l in lines if l >= 0][:8]

    table = []
    n = len(values)
    for line in lines:
        prob = float(np.sum(values > line) / n) if n > 0 else 0.5
        table.append({"line": line, "prob_over": round(prob, 4)})

    return table
