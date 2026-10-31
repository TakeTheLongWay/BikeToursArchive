from .api_appsettings import appsettings_bp
from .api_collections import collections_bp
from .api_diary import diary_bp
from .api_goals import goals_bp
from .api_stats import stats_bp
from .api_tours import tours_bp
from .imports import imports_bp
from .api_planning import planning_bp
from .pages import pages_bp

__all__ = [
    "appsettings_bp",
    "collections_bp",
    "diary_bp",
    "goals_bp",
    "planning_bp",
    "stats_bp",
    "tours_bp",
    "imports_bp",
    "pages_bp",
]