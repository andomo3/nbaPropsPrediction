from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXPORTS_DIR = ROOT / "exports"
MVP_PATH = EXPORTS_DIR / "nba_mvp_data.csv"
OUT_MVP_PATH = EXPORTS_DIR / "nba_training_mvp_v1.csv"


def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    print(f"Loading data from: {path}")
    return pd.read_csv(path)


def quality_checks(df: pd.DataFrame) -> pd.DataFrame:
    """Ensures numeric types and fills NaNs."""
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].fillna(0)

    for col in numeric_cols:
        if col.endswith("pct") or col == "min":
            df[col] = df[col].astype(float)
        else:
            df[col] = df[col].astype(int)

    return df


def clean_mvp_data(df: pd.DataFrame) -> pd.DataFrame:
    """Cleaning logic specific to the MVP (Full Game) dataset."""
    initial_rows = len(df)

    df = df[~df["game_id"].astype(str).str.startswith(("TEST", "999"))].copy()
    df = df.drop_duplicates(subset=["game_id", "player_name"])

    dropped = initial_rows - len(df)
    if dropped > 0:
        print(f"Dropped {dropped} rows (duplicates or test data).")

    return quality_checks(df)


def main() -> None:
    print("Starting MVP Cleaning Pipeline...")
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        df = load_data(MVP_PATH)
    except FileNotFoundError as exc:
        print(exc)
        return

    df = clean_mvp_data(df)
    df.to_csv(OUT_MVP_PATH, index=False)

    print(f"Saved MVP training data to {OUT_MVP_PATH}")
    print(f"Final shape: {df.shape} (rows, cols)")
    print(f"Columns: {list(df.columns)}")


if __name__ == "__main__":
    main()
