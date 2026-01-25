from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXPORTS_DIR = ROOT / "exports"
INPUT_PATH = EXPORTS_DIR / "nba_mvp_data.csv"
OUTPUT_PATH = EXPORTS_DIR / "nba_model_ready.csv"


def load_and_sort(path: Path) -> pd.DataFrame:
    print(f"Loading data from {path}...")
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["player_name", "date"]).reset_index(drop=True)
    return df


def add_context_features(df: pd.DataFrame) -> pd.DataFrame:
    print("Generating context features...")
    df["is_home"] = (df["player_team"] == df["home_team"]).astype(int)
    df["opponent"] = np.where(df["is_home"] == 1, df["away_team"], df["home_team"])
    df["days_rest"] = df.groupby("player_name")["date"].diff().dt.days
    df["days_rest"] = df["days_rest"].fillna(3)
    return df


def add_rolling_player_stats(df: pd.DataFrame) -> pd.DataFrame:
    print("Generating rolling/EMA features with garbage-time masking...")
    calc_df = df.copy()
    mask = calc_df["min"] < 10
    calc_df.loc[mask, ["pts", "reb", "ast", "min", "fg_pct"]] = np.nan

    stats = ["pts", "reb", "ast", "min", "fg_pct"]
    windows = [5, 10]

    for stat in stats:
        for window in windows:
            col_name = f"{stat}_L{window}"
            df[col_name] = calc_df.groupby("player_name")[stat].transform(
                lambda x: x.shift(1).rolling(window=window, min_periods=1).mean()
            )

    for stat in ["pts", "reb", "ast"]:
        col_name = f"{stat}_ema_L5"
        df[col_name] = calc_df.groupby("player_name")[stat].transform(
            lambda x: x.shift(1).ewm(span=5, adjust=False).mean()
        )

    df["pts_std_L10"] = calc_df.groupby("player_name")["pts"].transform(
        lambda x: x.shift(1).rolling(window=10, min_periods=5).std()
    )
    return df


def add_opponent_stats(df: pd.DataFrame) -> pd.DataFrame:
    print("Generating opponent defense features...")
    defense = (
        df.groupby(["game_id", "date", "opponent"])["pts"]
        .sum()
        .reset_index()
        .rename(columns={"pts": "total_pts_allowed"})
        .sort_values(["opponent", "date"])
    )

    defense["opp_pts_allowed_L10"] = defense.groupby("opponent")[
        "total_pts_allowed"
    ].transform(lambda x: x.shift(1).rolling(window=10, min_periods=1).mean())

    df = df.merge(
        defense[["game_id", "opponent", "opp_pts_allowed_L10"]],
        on=["game_id", "opponent"],
        how="left",
    )
    return df


def main() -> None:
    if not INPUT_PATH.exists():
        print(f"Error: {INPUT_PATH} not found.")
        return

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    df = load_and_sort(INPUT_PATH)
    df = add_context_features(df)
    df = add_rolling_player_stats(df)
    df = add_opponent_stats(df)

    before_dnp = len(df)
    # Remove DNPs (min == 0). Keep 0 < min < 10 rows as valid targets.
    df = df[df["min"] > 0]
    dnp_dropped = before_dnp - len(df)

    before = len(df)
    df = df.dropna()
    dropped = before - len(df)

    df.to_csv(OUTPUT_PATH, index=False)
    print(
        f"Saved {len(df)} rows to {OUTPUT_PATH} "
        f"(dropped {dnp_dropped} DNP, {dropped} missing features)."
    )


if __name__ == "__main__":
    main()
