from .api_goals import goals_bp
from .api_stats import stats_bp
from .api_tours import tours_bp
from .imports import imports_bp
from .pages import pages_bp

__all__ = [
    "goals_bp",
    "stats_bp",
    "tours_bp",
    "imports_bp",
    "pages_bp",
]