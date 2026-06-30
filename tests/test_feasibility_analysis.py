from src.common.schemas import ScopeOfWork, TenderData, TenderMetadata
from src.feasibility_analysis.gate import analyse_feasibility
from src.feasibility_analysis.thresholds import FeasibilityThresholds


def make_tender(value=1_000_000, timeline=60, category="IT Services"):
    return TenderData(
        metadata=TenderMetadata(bid_id="BID-1", title="Test", estimated_value_inr=value, category=category),
        scope_of_work=ScopeOfWork(timeline_days=timeline),
    )


def test_within_all_thresholds_is_feasible():
    tender = make_tender(value=1_000_000, timeline=60)
    thresholds = FeasibilityThresholds(max_project_value_inr=5_000_000, min_timeline_days=30)
    result = analyse_feasibility(tender, thresholds)
    assert result.is_feasible is True


def test_value_exceeds_threshold_is_infeasible():
    tender = make_tender(value=10_000_000)
    thresholds = FeasibilityThresholds(max_project_value_inr=5_000_000)
    result = analyse_feasibility(tender, thresholds)
    assert result.is_feasible is False


def test_timeline_too_short_is_infeasible():
    tender = make_tender(timeline=5)
    thresholds = FeasibilityThresholds(min_timeline_days=30)
    result = analyse_feasibility(tender, thresholds)
    assert result.is_feasible is False


def test_excluded_category_is_infeasible():
    tender = make_tender(category="Construction")
    thresholds = FeasibilityThresholds(excluded_categories=["Construction"])
    result = analyse_feasibility(tender, thresholds)
    assert result.is_feasible is False


def test_no_thresholds_configured_is_feasible():
    tender = make_tender()
    thresholds = FeasibilityThresholds()
    result = analyse_feasibility(tender, thresholds)
    assert result.is_feasible is True
