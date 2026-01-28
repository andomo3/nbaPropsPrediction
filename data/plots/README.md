# Training Plots & Visualizations

Store model training visualizations here to diagnose model performance.

## Suggested Plots

### Data Exploration
- Feature distributions (histograms)
- Correlation heatmaps
- Target variable distribution

### Model Diagnostics
- **Learning curves** - Training vs validation loss over iterations (detect overfitting)
- **ROC curves** - Compare model discrimination across thresholds
- **Calibration curves** - Check if predicted probabilities match actual outcomes
- **Feature importance** - Which features drive predictions

### Overfitting/Underfitting Indicators

| Symptom | Train Score | Val Score | Diagnosis |
|---------|-------------|-----------|-----------|
| High train, low val | ~0.95 | ~0.60 | Overfitting |
| Both low | ~0.55 | ~0.53 | Underfitting |
| Both high, close | ~0.75 | ~0.72 | Good fit |

## File Naming Convention

```
{stat}_{model}_{plot_type}_{date}.png

Examples:
- pts_xgb_learning_curve_2024-01-15.png
- reb_catboost_roc_curve_2024-01-15.png
- feature_importance_comparison.png
```
