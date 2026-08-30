"""Testy silnika podatkowego (`src/tax_engine.py`).

Skupione na przypadkach wskazanych w specyfikacji jako najbardziej podatne
na błędy: kolejność i wysycanie limitów w kaskadzie oraz mechanika PPK
i kompensacji strat.
"""

import pytest

from src.tax_engine import (
    AccountYTDState,
    LossCarryforward,
    allocate_monthly_surplus,
    annual_limit,
    apply_loss_relief,
    effective_multiplier,
    ppk_early_withdrawal_penalty,
    register_loss,
    retail_bond_rate,
)


class TestEffectiveMultiplier:
    def test_ikze_dominates_at_low_pit_bracket(self):
        ike = effective_multiplier("IKE", marginal_tax_rate=0.12)
        ikze = effective_multiplier("IKZE", marginal_tax_rate=0.12)
        assert ike == pytest.approx(0.88)
        assert ikze == pytest.approx(0.90)
        assert ikze > ike

    def test_ikze_dominates_at_high_pit_bracket(self):
        ike = effective_multiplier("IKE", marginal_tax_rate=0.32)
        ikze = effective_multiplier("IKZE", marginal_tax_rate=0.32)
        assert ike == pytest.approx(0.68)
        assert ikze == pytest.approx(0.90)
        # przewaga IKZE rośnie wraz ze stawką PIT: 22 p.p. przy 32%
        assert (ikze - ike) == pytest.approx(0.22)

    def test_unknown_account_type_raises(self):
        with pytest.raises(ValueError):
            effective_multiplier("OKI", marginal_tax_rate=0.12)  # type: ignore[arg-type]


class TestAnnualLimit:
    AVG_WAGE = 8000.0

    def test_ike_limit(self):
        assert annual_limit("IKE", self.AVG_WAGE) == pytest.approx(3 * self.AVG_WAGE)

    def test_ikze_limit_uop(self):
        assert annual_limit("IKZE", self.AVG_WAGE, employment_form="uop") == pytest.approx(
            1.2 * self.AVG_WAGE
        )

    def test_ikze_limit_b2b_is_higher(self):
        uop = annual_limit("IKZE", self.AVG_WAGE, employment_form="uop")
        b2b = annual_limit("IKZE", self.AVG_WAGE, employment_form="b2b")
        assert b2b == pytest.approx(1.8 * self.AVG_WAGE)
        assert b2b > uop

    def test_ikze_without_employment_form_raises(self):
        with pytest.raises(ValueError):
            annual_limit("IKZE", self.AVG_WAGE)

    def test_oki_threshold_fixed_before_2030(self):
        assert annual_limit(
            "OKI", self.AVG_WAGE, oki_kind="investment", year=2028
        ) == pytest.approx(100_000.0)

    def test_oki_threshold_indexed_from_2030(self):
        result = annual_limit(
            "OKI",
            self.AVG_WAGE,
            oki_kind="savings",
            year=2031,
            cumulative_inflation_since_2030=1.10,
        )
        assert result == pytest.approx(25_000.0 * 1.10)


class TestAllocateMonthlySurplus:
    def make_limits(self):
        return {"ppk": 2_000.0, "ikze": 12_000.0, "ike": 20_000.0, "oki": 100_000.0}

    def test_small_surplus_goes_entirely_to_ppk(self):
        state = AccountYTDState()
        allocation = allocate_monthly_surplus(1_000.0, state, self.make_limits())
        assert allocation["ppk"] == pytest.approx(1_000.0)
        assert allocation["ikze"] == pytest.approx(0.0)
        assert allocation["standard"] == pytest.approx(0.0)
        assert state.ppk_ytd == pytest.approx(1_000.0)

    def test_surplus_overflows_through_full_cascade_to_standard(self):
        state = AccountYTDState()
        limits = self.make_limits()
        total = sum(limits.values()) + 5_000.0
        allocation = allocate_monthly_surplus(total, state, limits)
        assert allocation["ppk"] == pytest.approx(limits["ppk"])
        assert allocation["ikze"] == pytest.approx(limits["ikze"])
        assert allocation["ike"] == pytest.approx(limits["ike"])
        assert allocation["oki"] == pytest.approx(limits["oki"])
        assert allocation["standard"] == pytest.approx(5_000.0)

    def test_ytd_state_accumulates_across_calls(self):
        state = AccountYTDState()
        limits = self.make_limits()
        allocate_monthly_surplus(1_500.0, state, limits)  # wysyca PPK (limit 2000)
        second = allocate_monthly_surplus(1_500.0, state, limits)
        # pierwsze 500 dopełnia limit PPK, reszta (1000) idzie do IKZE
        assert second["ppk"] == pytest.approx(500.0)
        assert second["ikze"] == pytest.approx(1_000.0)
        assert state.ppk_ytd == pytest.approx(2_000.0)

    def test_liquidity_first_prioritizes_oki_over_ikze_and_ike(self):
        state = AccountYTDState()
        limits = self.make_limits()
        surplus = limits["ppk"] + 10_000.0
        allocation = allocate_monthly_surplus(
            surplus, state, limits, priority_mode="liquidity_first"
        )
        assert allocation["ppk"] == pytest.approx(limits["ppk"])
        assert allocation["oki"] == pytest.approx(10_000.0)
        assert allocation["ikze"] == pytest.approx(0.0)
        assert allocation["ike"] == pytest.approx(0.0)

    def test_ppk_ineligible_skips_ppk_entirely(self):
        state = AccountYTDState()
        limits = self.make_limits()
        allocation = allocate_monthly_surplus(
            1_000.0, state, limits, ppk_eligible=False
        )
        assert allocation["ppk"] == pytest.approx(0.0)
        assert allocation["ikze"] == pytest.approx(1_000.0)


class TestPpkEarlyWithdrawalPenalty:
    def test_penalty_breakdown(self):
        result = ppk_early_withdrawal_penalty(
            state_topups_total=730.0,       # 250 powitalna + 2x240 roczna
            employer_contrib_total=5_000.0,
            investment_gain=8_000.0,
        )
        assert result["lost_state_topups"] == pytest.approx(730.0)
        assert result["lost_employer_share"] == pytest.approx(1_500.0)  # 30% z 5000
        # opodatkowany zysk = 8000 - 730 - 1500 = 5770; podatek 19%
        assert result["belka_tax"] == pytest.approx(5_770.0 * 0.19)
        assert result["total_penalty"] == pytest.approx(
            730.0 + 1_500.0 + 5_770.0 * 0.19
        )

    def test_penalty_gain_cannot_go_negative(self):
        # zysk mniejszy niż suma utraconych dopłat -- opodatkowany zysk = 0, nie ujemny
        result = ppk_early_withdrawal_penalty(
            state_topups_total=730.0,
            employer_contrib_total=5_000.0,
            investment_gain=100.0,
        )
        assert result["belka_tax"] == pytest.approx(0.0)


class TestLossCarryforward:
    def test_partial_relief_capped_at_50_percent_per_year(self):
        losses = LossCarryforward()
        register_loss(losses, year=2025, amount=10_000.0)

        relief, remaining_gain = apply_loss_relief(losses, current_year=2026, gain=20_000.0)
        assert relief == pytest.approx(5_000.0)  # max 50% z 10 000
        assert remaining_gain == pytest.approx(15_000.0)
        # połowa straty pozostaje do wykorzystania w kolejnych latach
        assert losses.entries == [(2025, 5_000.0)]

        relief2, _ = apply_loss_relief(losses, current_year=2027, gain=20_000.0)
        assert relief2 == pytest.approx(2_500.0)  # 50% z pozostałych 5000

    def test_full_lump_sum_uses_entire_loss_at_once(self):
        losses = LossCarryforward()
        register_loss(losses, year=2025, amount=10_000.0)
        relief, remaining_gain = apply_loss_relief(
            losses, current_year=2026, gain=20_000.0, full_lump_sum=True
        )
        assert relief == pytest.approx(10_000.0)
        assert remaining_gain == pytest.approx(10_000.0)
        assert losses.entries == []

    def test_loss_older_than_five_years_expires(self):
        losses = LossCarryforward()
        register_loss(losses, year=2018, amount=10_000.0)
        relief, remaining_gain = apply_loss_relief(losses, current_year=2025, gain=20_000.0)
        assert relief == pytest.approx(0.0)
        assert remaining_gain == pytest.approx(20_000.0)
        assert losses.entries == []

    def test_negative_gain_returns_zero_relief_untouched_registry(self):
        losses = LossCarryforward()
        register_loss(losses, year=2025, amount=10_000.0)
        relief, remaining = apply_loss_relief(losses, current_year=2026, gain=-500.0)
        assert relief == pytest.approx(0.0)
        assert remaining == pytest.approx(0.0)
        assert losses.entries == [(2025, 10_000.0)]

    def test_register_loss_rejects_negative_amount(self):
        losses = LossCarryforward()
        with pytest.raises(ValueError):
            register_loss(losses, year=2025, amount=-1.0)


class TestRetailBondRate:
    def test_first_year_uses_fixed_nominal_rate(self):
        rate = retail_bond_rate(
            cpi_period=0.05, margin=0.015, is_first_year=True, first_year_nominal_rate=0.061
        )
        assert rate == pytest.approx(0.061)

    def test_subsequent_period_uses_cpi_plus_margin(self):
        rate = retail_bond_rate(cpi_period=0.045, margin=0.0125)
        assert rate == pytest.approx(0.0575)

    def test_first_year_without_rate_raises(self):
        with pytest.raises(ValueError):
            retail_bond_rate(cpi_period=0.05, margin=0.015, is_first_year=True)
