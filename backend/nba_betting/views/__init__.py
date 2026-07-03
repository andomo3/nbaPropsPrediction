"""Views package — modules grouped by URL prefix.

Re-exports every public view class so `from . import views` /
`views.SomeView` references in urls.py keep working unchanged.
"""

from .predictions import (
    ManualPredictionView,
    MetadataView,
    PlayerListView,
)
from .picks import LitePicksView
from .backtests import (
    BacktestView,
    LeaderboardComparisonView,
    LeaderboardView,
    ModelComparisonView,
    SeasonSummaryView,
)
from .intelligence import (
    EdgeCalibrationView,
    FloorCeilingView,
    OpponentAnalysisView,
    PlayerFingerprintView,
    ShapAnalysisView,
    SimulatorView,
    StatisticalValidationView,
    TierHistoryView,
    VarianceDecompView,
)

__all__ = [
    "ManualPredictionView",
    "MetadataView",
    "PlayerListView",
    "LitePicksView",
    "BacktestView",
    "LeaderboardComparisonView",
    "LeaderboardView",
    "ModelComparisonView",
    "SeasonSummaryView",
    "EdgeCalibrationView",
    "FloorCeilingView",
    "OpponentAnalysisView",
    "PlayerFingerprintView",
    "ShapAnalysisView",
    "SimulatorView",
    "StatisticalValidationView",
    "TierHistoryView",
    "VarianceDecompView",
]
