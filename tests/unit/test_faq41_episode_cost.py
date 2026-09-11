"""Unit tests for FAQ Round 2 §4.1 episode cost accounting rules and synthetic multi-episode fixture.

FAQ Round 2 §4.1 Specification Invariants:
1. Maximal runs of consecutive faulty weeks constitute continuous episodes.
2. Healthy weeks separate distinct independent episodes.
3. Within one episode, only the first selected visit is credited as the catch.
4. Missed cost (€600/wk) is charged for weeks up to and including the week the first visit lands.
5. Missed cost stops once the first visit lands; subsequent weeks in the same continuous episode incur €0 missed penalty.
6. Subsequent selections in the same episode receive no additional €600 benefit (wasted visits).
7. Unvisited episodes are charged in full (length * €600).
8. A new independent episode must be caught again; visits in a separate episode are credited independently.
"""
import datetime as dt
from typing import List
import pytest

from app.model.evaluate import (
    EpisodeCostAccountingResult,
    evaluate_episode_cost_faq41,
)


@pytest.fixture
def synthetic_two_episode_fixture() -> dict:
    """Synthetic fixture covering a 4-week continuous episode, a healthy separator week,

    and a 2-week independent second episode.

    Structure:
    - Gateway: GW_SYNTH_01
    - Episode 1 (4 weeks): 2025-11-03 (W1), 2025-11-10 (W2), 2025-11-17 (W3), 2025-11-24 (W4)
    - Separator Healthy Week (1 week): 2025-12-01 (W5)
    - Episode 2 (2 weeks): 2025-12-08 (W6), 2025-12-15 (W7)
    """
    ep1_weeks = [
        dt.date(2025, 11, 3),   # W1
        dt.date(2025, 11, 10),  # W2
        dt.date(2025, 11, 17),  # W3
        dt.date(2025, 11, 24),  # W4
    ]
    healthy_week = dt.date(2025, 12, 1)  # W5 - healthy separator
    ep2_weeks = [
        dt.date(2025, 12, 8),   # W6
        dt.date(2025, 12, 15),  # W7
    ]
    return {
        "gateway_id": "GW_SYNTH_01",
        "episodes": [ep1_weeks, ep2_weeks],
        "ep1_weeks": ep1_weeks,
        "healthy_week": healthy_week,
        "ep2_weeks": ep2_weeks,
    }


class TestFAQ41EpisodeCostAccounting:
    """Exhaustive tests asserting FAQ Round 2 §4.1 cost backtest accounting invariants."""

    def test_visit_in_week1_and_subsequent_w2_w3(self, synthetic_two_episode_fixture: dict):
        """Visit in Week 1: missed cost stops after W1 (charged 1 week = €600).

        Subsequent selections in W2 and W3 receive NO additional €600 benefit.
        """
        episodes = [synthetic_two_episode_fixture["ep1_weeks"]]
        # Model selects W1, W2, and W3
        selected = [dt.date(2025, 11, 3), dt.date(2025, 11, 10), dt.date(2025, 11, 17)]

        res = evaluate_episode_cost_faq41(episodes, selected)

        assert res.total_episodes == 1
        assert res.episodes_caught == 1
        assert res.episodes_missed == 0
        assert res.total_faulty_weeks == 4
        assert res.charged_missed_weeks == 1  # Only Week 1 charged
        assert res.saved_missed_weeks == 3    # Weeks 2, 3, 4 saved
        assert res.missed_penalty_eur == 600.0
        assert res.first_catch_selections == 1
        assert res.wasted_repick_selections == 2  # W2 and W3 are wasted repicks
        assert res.total_visit_selections == 3
        assert res.total_visit_cost_eur == 1140.0 # 3 * €380
        assert res.total_accounting_cost_eur == 1740.0 # €600 + €1140

    def test_visit_in_week2_and_subsequent_w3(self, synthetic_two_episode_fixture: dict):
        """Visit in Week 2: charged 2 weeks (€1200) per FAQ §4.1.

        Missed cost stops after W2. Subsequent selection in W3 receives NO additional €600 benefit.
        """
        episodes = [synthetic_two_episode_fixture["ep1_weeks"]]
        # Model selects W2 and W3
        selected = [dt.date(2025, 11, 10), dt.date(2025, 11, 17)]

        res = evaluate_episode_cost_faq41(episodes, selected)

        assert res.total_episodes == 1
        assert res.episodes_caught == 1
        assert res.episodes_missed == 0
        assert res.total_faulty_weeks == 4
        assert res.charged_missed_weeks == 2  # Weeks 1 and 2 charged
        assert res.saved_missed_weeks == 2    # Weeks 3 and 4 saved
        assert res.missed_penalty_eur == 1200.0 # FAQ §4.1 example: W1-W4 with visit in W2 costs €1,200
        assert res.first_catch_selections == 1
        assert res.wasted_repick_selections == 1  # W3 is a wasted repick
        assert res.total_visit_selections == 2
        assert res.total_visit_cost_eur == 760.0  # 2 * €380

    def test_visit_in_week3_only(self, synthetic_two_episode_fixture: dict):
        """Visit in Week 3: charged 3 weeks (€1800). Missed cost stops after W3."""
        episodes = [synthetic_two_episode_fixture["ep1_weeks"]]
        selected = [dt.date(2025, 11, 17)]

        res = evaluate_episode_cost_faq41(episodes, selected)

        assert res.total_episodes == 1
        assert res.episodes_caught == 1
        assert res.episodes_missed == 0
        assert res.total_faulty_weeks == 4
        assert res.charged_missed_weeks == 3  # Weeks 1, 2, 3 charged
        assert res.saved_missed_weeks == 1    # Week 4 saved
        assert res.missed_penalty_eur == 1800.0
        assert res.first_catch_selections == 1
        assert res.wasted_repick_selections == 0
        assert res.total_visit_selections == 1

    def test_no_visit_charged_in_full(self, synthetic_two_episode_fixture: dict):
        """No visit in episode: charged in full (4 weeks = €2400) per FAQ §4.1."""
        episodes = [synthetic_two_episode_fixture["ep1_weeks"]]
        selected = []

        res = evaluate_episode_cost_faq41(episodes, selected)

        assert res.total_episodes == 1
        assert res.episodes_caught == 0
        assert res.episodes_missed == 1
        assert res.total_faulty_weeks == 4
        assert res.charged_missed_weeks == 4  # All 4 weeks charged
        assert res.saved_missed_weeks == 0
        assert res.missed_penalty_eur == 2400.0
        assert res.first_catch_selections == 0
        assert res.wasted_repick_selections == 0
        assert res.total_visit_selections == 0

    def test_second_independent_episode_credited_separately(self, synthetic_two_episode_fixture: dict):
        """Healthy week 5 separates Episode 1 and Episode 2.

        Visits in Episode 2 are credited separately as a new episode per FAQ §4.1.
        """
        episodes = synthetic_two_episode_fixture["episodes"]

        # Case A: Visit W2 (Episode 1) and W6 (Episode 2, Week 1 of Ep 2)
        sel_a = [dt.date(2025, 11, 10), dt.date(2025, 12, 8)]
        res_a = evaluate_episode_cost_faq41(episodes, sel_a)

        assert res_a.total_episodes == 2
        assert res_a.episodes_caught == 2
        assert res_a.episodes_missed == 0
        assert res_a.total_faulty_weeks == 6
        # Ep 1 charged 2 wks (W1, W2); Ep 2 charged 1 wk (W6) -> total 3 wks
        assert res_a.charged_missed_weeks == 3
        assert res_a.saved_missed_weeks == 3   # Ep 1 W3, W4; Ep 2 W7
        assert res_a.missed_penalty_eur == 1800.0
        assert res_a.first_catch_selections == 2
        assert res_a.wasted_repick_selections == 0

        # Case B: Visit W2 (Episode 1) and NONE in Episode 2
        sel_b = [dt.date(2025, 11, 10)]
        res_b = evaluate_episode_cost_faq41(episodes, sel_b)

        assert res_b.total_episodes == 2
        assert res_b.episodes_caught == 1
        assert res_b.episodes_missed == 1
        # Ep 1 charged 2 wks; Ep 2 charged in full (2 wks) -> total 4 wks
        assert res_b.charged_missed_weeks == 4
        assert res_b.saved_missed_weeks == 2   # Ep 1 W3, W4
        assert res_b.missed_penalty_eur == 2400.0
