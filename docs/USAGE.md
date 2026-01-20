# Scenario Mode Usage

Scenario Mode lets users input their own prop line (ex: "LeBron Over 25.5
Points") and receive model-backed over/under probabilities.

## Workflow
1. Select a player from the search input.
2. Choose a prop type (points, rebounds, assists, etc.).
3. Set the period (1-4) and enter a line value.
4. Submit to receive projected value and over/under probabilities.

## API Request
Endpoint: `POST /api/predict/manual/`

Payload:
```json
{
  "player": "LeBron James",
  "prop": "points",
  "line": 25.5,
  "period": 1
}
```

Response (scaffold):
```json
{
  "projected": 28.2,
  "prob_over": 0.65,
  "prob_under": 0.35
}
```

## Player Search
Endpoint: `GET /api/players/?q=lebron`

Response:
```json
[
  {
    "id": 1,
    "name": "LeBron James",
    "team": "LAL",
    "nba_id": 2544
  }
]
```

## Notes
- The ML logic in `backend/nba_betting/ml/predictor.py` is scaffold-only.
- Replace the placeholder with model loading and z-score probability logic.
