"""Eligibility Engine: profile matching, confidence scoring. Entry: evaluate_eligibility(tender)."""
from .engine import run_eligibility_check, save_eligibility_result, NoActiveProfileError
from .matcher import evaluate_eligibility
from .profile import get_active_profile, get_past_projects

__all__ = [
    "run_eligibility_check",
    "save_eligibility_result",
    "NoActiveProfileError",
    "evaluate_eligibility",
    "get_active_profile",
    "get_past_projects",
]
