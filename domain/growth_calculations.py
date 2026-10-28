"""Compatibility imports for the growth domain module."""
from tracker.domain.growth_calculations import (
    calculate_archive_history_changes,
    calculate_recent_history_changes,
)

__all__ = ["calculate_archive_history_changes", "calculate_recent_history_changes"]
