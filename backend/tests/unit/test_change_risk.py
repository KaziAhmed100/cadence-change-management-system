"""Unit tests for the risk scoring algorithm.

The algorithm is deterministic, so these tests pin down the exact behavior
we promised: same inputs always produce the same score and band.
"""

import pytest

from app.core.change_enums import ImpactLevel, RiskBand
from app.core.change_risk import RiskInputs, assess_risk


def _inputs(**overrides) -> RiskInputs:
    """Build a baseline RiskInputs with sensible defaults, overridable per test."""
    defaults = {
        "impact": ImpactLevel.INDIVIDUAL,
        "downtime_minutes": 0,
        "affected_ci_count": 1,
        "has_rollback_plan": True,
        "is_security_related": False,
    }
    defaults.update(overrides)
    return RiskInputs(**defaults)


class TestRiskAssessment:
    def test_minimum_case_is_low(self) -> None:
        result = assess_risk(_inputs())
        assert result.band == RiskBand.LOW
        assert 1 <= result.score <= 3

    def test_maximum_case_is_critical(self) -> None:
        result = assess_risk(
            _inputs(
                impact=ImpactLevel.EXTERNAL,
                downtime_minutes=480,  # 8 hours
                affected_ci_count=50,
                has_rollback_plan=False,
                is_security_related=True,
            )
        )
        assert result.band == RiskBand.CRITICAL
        assert result.score == 10  # clamped to max

    def test_no_rollback_plan_adds_risk(self) -> None:
        with_plan = assess_risk(_inputs(has_rollback_plan=True))
        without_plan = assess_risk(_inputs(has_rollback_plan=False))
        assert without_plan.score > with_plan.score
        assert "no_rollback_plan" in without_plan.breakdown

    def test_security_related_adds_risk(self) -> None:
        not_security = assess_risk(_inputs(is_security_related=False))
        security = assess_risk(_inputs(is_security_related=True))
        assert security.score >= not_security.score

    def test_higher_impact_increases_score(self) -> None:
        import itertools

        scores = []
        for impact in (
            ImpactLevel.INDIVIDUAL,
            ImpactLevel.TEAM,
            ImpactLevel.DEPARTMENT,
            ImpactLevel.UNIVERSITY,
            ImpactLevel.EXTERNAL,
        ):
            scores.append(assess_risk(_inputs(impact=impact)).score)
        # Strictly non-decreasing along the impact ladder
        assert all(a <= b for a, b in itertools.pairwise(scores))

    def test_downtime_buckets(self) -> None:
        # Quick zero-downtime change should be lower than a long downtime one
        short = assess_risk(_inputs(downtime_minutes=0))
        medium = assess_risk(_inputs(downtime_minutes=60))
        long = assess_risk(_inputs(downtime_minutes=480))
        assert short.score < medium.score < long.score

    def test_breakdown_only_includes_nonzero_contributions(self) -> None:
        # Minimum case has many zero contributions - those shouldn't clutter the UI
        result = assess_risk(_inputs())
        for key, value in result.breakdown.items():
            assert value > 0, f"breakdown should not include zero: {key}"

    @pytest.mark.parametrize(
        ("score", "expected_band"),
        [
            (1, RiskBand.LOW),
            (3, RiskBand.LOW),
            (4, RiskBand.MEDIUM),
            (5, RiskBand.MEDIUM),
            (6, RiskBand.HIGH),
            (7, RiskBand.HIGH),
            (8, RiskBand.CRITICAL),
            (10, RiskBand.CRITICAL),
        ],
    )
    def test_band_thresholds(self, score: int, expected_band: RiskBand) -> None:
        """Document the score-to-band cutoffs explicitly."""
        # Constructing an exact score is awkward, so we test the band function
        # by reaching it through a real assessment that lands at that score.
        # The threshold mapping itself is straightforward to verify here:
        from app.core.change_risk import _band_for_score

        assert _band_for_score(score) == expected_band
