"""Risk scoring algorithm.

Given a few structured inputs about a proposed change, compute:
1. A numeric risk score from 1-10
2. A human-readable RiskBand (Low/Medium/High/Critical)

The algorithm is deliberately simple and explainable - this is the kind of
thing where transparency beats sophistication. A change manager should be
able to look at the inputs and predict roughly where the score lands.

Inputs:
- impact: blast radius (ImpactLevel)
- downtime_minutes: expected downtime
- affected_ci_count: number of configuration items involved
- has_rollback_plan: whether the requester provided a rollback plan
- is_security_related: security changes get a small bump (they're sensitive
  even when other factors are low)

The output is bucketed because in practice we route by band, not score - but
keeping the numeric score around lets us tune thresholds without changing
the API.
"""

from dataclasses import dataclass

from app.core.change_enums import ImpactLevel, RiskBand

# Impact contributes the bulk of the score because blast radius is the single
# strongest predictor of how much pain a failed change will cause.
_IMPACT_POINTS = {
    ImpactLevel.INDIVIDUAL: 1,
    ImpactLevel.TEAM: 2,
    ImpactLevel.DEPARTMENT: 4,
    ImpactLevel.UNIVERSITY: 6,
    ImpactLevel.EXTERNAL: 7,
}


@dataclass(frozen=True)
class RiskInputs:
    """Structured inputs for the risk algorithm.

    Frozen so callers can't accidentally mutate them mid-calculation.
    """

    impact: ImpactLevel
    downtime_minutes: int
    affected_ci_count: int
    has_rollback_plan: bool
    is_security_related: bool


@dataclass(frozen=True)
class RiskAssessment:
    score: int  # 1-10
    band: RiskBand
    # The breakdown is exposed for UI transparency - the requester should be
    # able to see *why* their change scored high.
    breakdown: dict[str, int]


def _band_for_score(score: int) -> RiskBand:
    if score <= 3:
        return RiskBand.LOW
    if score <= 5:
        return RiskBand.MEDIUM
    if score <= 7:
        return RiskBand.HIGH
    return RiskBand.CRITICAL


def assess_risk(inputs: RiskInputs) -> RiskAssessment:
    """Compute the risk assessment for a change request.

    The algorithm sums up contributions from each input, then clamps the
    result to 1..10. Each contribution is logged in the breakdown so the
    UI can explain the score to users.
    """
    breakdown: dict[str, int] = {}

    # Impact is the strongest signal
    impact_pts = _IMPACT_POINTS[inputs.impact]
    breakdown["impact"] = impact_pts

    # Downtime in tiers. The boundaries are fuzzy on purpose - we'd rather
    # round up than down. Zero downtime is the only band that contributes
    # nothing.
    if inputs.downtime_minutes <= 0:
        downtime_pts = 0
    elif inputs.downtime_minutes <= 15:
        downtime_pts = 1
    elif inputs.downtime_minutes <= 60:
        downtime_pts = 2
    elif inputs.downtime_minutes <= 240:
        downtime_pts = 3
    else:
        downtime_pts = 4
    breakdown["downtime"] = downtime_pts

    # CI count - more systems involved means more places for things to go wrong
    if inputs.affected_ci_count <= 1:
        ci_pts = 0
    elif inputs.affected_ci_count <= 3:
        ci_pts = 1
    elif inputs.affected_ci_count <= 10:
        ci_pts = 2
    else:
        ci_pts = 3
    breakdown["affected_systems"] = ci_pts

    # No rollback plan is risky on its own - if something goes wrong you have
    # no documented way to recover. Always adds points.
    if not inputs.has_rollback_plan:
        breakdown["no_rollback_plan"] = 2
    else:
        breakdown["no_rollback_plan"] = 0

    # Security-related changes get a small bump even if all other factors
    # are low. The reasoning: a "trivial" security change still warrants
    # scrutiny.
    if inputs.is_security_related:
        breakdown["security_sensitive"] = 1
    else:
        breakdown["security_sensitive"] = 0

    raw_score = sum(breakdown.values())
    # Clamp to [1, 10] - a change always has some risk, and the scale tops out
    score = max(1, min(10, raw_score))

    return RiskAssessment(
        score=score,
        band=_band_for_score(score),
        breakdown={k: v for k, v in breakdown.items() if v > 0},
    )
