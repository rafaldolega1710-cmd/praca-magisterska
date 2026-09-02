"""Testy fazy dekumulacji (`src/decumulation.py`).

Tak jak w `test_simulation.py`, testy operują na małym, syntetycznym
`market_data` o kontrolowanych zwrotach -- nie na prawdziwych danych
historycznych.
"""

import pandas as pd
import pytest

from src.decumulation import (
    run_decumulation_window,
    run_rolling_decumulation,
    summarize_decumulation,
)
from src.simulation import SimulationAssumptions


def make_market_data(
    n_months: int = 24,
    start: str = "2020-01",
    acwi_return: float = 0.0,
    edo_return: float = 0.0,
    usd_pln: float = 4.0,
    cpi: float = 100.0,  # 100 = zerowa inflacja (rok poprzedni = 100)
) -> pd.DataFrame:
    index = pd.period_range(start=start, periods=n_months, freq="M")
    return pd.DataFrame(
        {
            "acwi_monthly_return": acwi_return,
            "usd_pln": usd_pln,
            "edo_reference_monthly_return": edo_return,
            "cpi_prev_year_100": cpi,
        },
        index=index,
    )


class TestRunDecumulationWindow:
    def test_insufficient_runway_returns_none(self):
        market_data = make_market_data(n_months=6)
        assumptions = SimulationAssumptions()
        result = run_decumulation_window(
            market_data.index[0], market_data, assumptions, horizon_years=1
        )
        assert result is None  # 6 miesiecy danych, potrzeba 12

    def test_survives_with_zero_returns_zero_inflation_matches_exact_withdrawal(self):
        market_data = make_market_data(n_months=12, acwi_return=0.0, edo_return=0.0, cpi=100.0)
        assumptions = SimulationAssumptions(equity_weight=0.8, bond_weight=0.2, acwi_ter_annual=0.0)
        result = run_decumulation_window(
            market_data.index[0], market_data, assumptions, horizon_years=1, swr=0.04
        )
        assert result is not None
        assert result["survived"] is True
        # brak wzrostu, brak inflacji -> saldo koncowe = 1 - 12*(0.04/12) = 0.96 dokladnie
        assert result["ending_balance"] == pytest.approx(0.96, abs=1e-9)

    def test_huge_swr_exhausts_portfolio(self):
        market_data = make_market_data(n_months=12, acwi_return=0.0, edo_return=0.0)
        assumptions = SimulationAssumptions()
        result = run_decumulation_window(
            market_data.index[0], market_data, assumptions, horizon_years=1, swr=1.5
        )
        assert result is not None
        assert result["survived"] is False
        assert result["ending_balance"] == pytest.approx(0.0)
        assert result["min_balance"] == pytest.approx(0.0)

    def test_inflation_raises_withdrawal_each_january_not_mid_year(self):
        # 20% inflacji w pierwszym roku -- wyplata powinna wzrosnac dopiero
        # w 13. miesiacu (styczen kolejnego roku), nie wczesniej
        market_data = make_market_data(n_months=24, acwi_return=0.0, edo_return=0.0, cpi=120.0)
        assumptions = SimulationAssumptions(equity_weight=0.8, bond_weight=0.2, acwi_ter_annual=0.0)
        result = run_decumulation_window(
            market_data.index[0], market_data, assumptions, horizon_years=2, swr=0.04
        )
        # rok 1 (mies. 1-12): wyplacono 12*(0.04/12) = 0.04 -> saldo po roku 1 = 0.96
        # rok 2 (mies. 13-24): wyplata podniesiona o 20% (inflacja z roku 1) -> 0.04/12*1.2 miesiecznie
        expected = 0.96 - 12 * (0.04 / 12 * 1.2)
        assert result["ending_balance"] == pytest.approx(expected, abs=1e-9)


class TestAgeGatedDecumulation:
    """Bramkowanie wiekowe IKE/IKZE/PPK (patrz docstring `decumulation.py`):
    konto zablokowane wiekiem nie liczy się do dostępnego (płynnego) salda,
    nawet jeśli w sumie portfel jest wystarczający."""

    def test_requires_both_account_split_and_start_age_or_neither(self):
        market_data = make_market_data(n_months=12)
        assumptions = SimulationAssumptions()
        with pytest.raises(ValueError):
            run_decumulation_window(
                market_data.index[0], market_data, assumptions, horizon_years=1,
                account_split={"standard": 1.0}, start_age_at_fire=None,
            )
        with pytest.raises(ValueError):
            run_decumulation_window(
                market_data.index[0], market_data, assumptions, horizon_years=1,
                account_split=None, start_age_at_fire=50.0,
            )

    def test_past_all_access_ages_matches_pooled_result(self):
        # caly kapital w IKZE (najostrzejszy prog, 65 lat), ale start_age_at_fire=70
        # -- wszystko juz odblokowane od 1. miesiaca -> wynik identyczny jak
        # pula bez podzialu (test_survives_with_zero_returns... = 0.96)
        market_data = make_market_data(n_months=12, acwi_return=0.0, edo_return=0.0, cpi=100.0)
        assumptions = SimulationAssumptions(equity_weight=0.8, bond_weight=0.2, acwi_ter_annual=0.0)
        result = run_decumulation_window(
            market_data.index[0], market_data, assumptions, horizon_years=1, swr=0.04,
            account_split={"ppk": 0.0, "ikze": 1.0, "ike": 0.0, "oki": 0.0, "standard": 0.0},
            start_age_at_fire=70.0,
        )
        assert result is not None
        assert result["survived"] is True
        assert result["ending_balance"] == pytest.approx(0.96, abs=1e-9)
        assert result["locked_balance_at_end"] == pytest.approx(0.0)

    def test_liquidity_gap_when_locked_capital_cannot_be_touched(self):
        # 90% w IKZE (zablokowane do 65 lat), 10% na rachunku standardowym;
        # start_age_at_fire=50 -> caly horyzont ponizej progow IKE/IKZE/PPK.
        # Wyplata 0.5/12 miesiecznie wyczerpuje plynne 10% w 3 miesiace,
        # mimo ze w sumie portfel ma 0.9+ kapitalu.
        market_data = make_market_data(n_months=12, acwi_return=0.0, edo_return=0.0, cpi=100.0)
        assumptions = SimulationAssumptions(equity_weight=0.8, bond_weight=0.2, acwi_ter_annual=0.0)
        result = run_decumulation_window(
            market_data.index[0], market_data, assumptions, horizon_years=1, swr=0.5,
            account_split={"ppk": 0.0, "ikze": 0.9, "ike": 0.0, "oki": 0.0, "standard": 0.1},
            start_age_at_fire=50.0,
        )
        assert result is not None
        assert result["survived"] is False
        assert result["failure_reason"] == "liquidity_gap"
        # kapital NIE jest zerowany -- 90% wciaz istnieje, tylko zablokowane
        assert result["ending_balance"] == pytest.approx(0.9166667, abs=1e-6)
        assert result["locked_balance_at_end"] == pytest.approx(0.9 / 0.9166667, abs=1e-4)

    def test_account_unlocking_mid_horizon_prevents_liquidity_gap(self):
        # IKE (prog 60 lat) trzyma 90% kapitalu; start_age_at_fire=59.9 ->
        # IKE odblokowuje sie w 3. miesiacu (59.9 + 2/12 > 60), akurat na czas,
        # zeby uratowac wyplate, ktora bez tego wyczerpalaby plynne 10%
        market_data = make_market_data(n_months=12, acwi_return=0.0, edo_return=0.0, cpi=100.0)
        assumptions = SimulationAssumptions(equity_weight=0.8, bond_weight=0.2, acwi_ter_annual=0.0)
        split = {"ppk": 0.0, "ikze": 0.0, "ike": 0.9, "oki": 0.0, "standard": 0.1}

        unlocks_in_time = run_decumulation_window(
            market_data.index[0], market_data, assumptions, horizon_years=1, swr=0.48,
            account_split=split, start_age_at_fire=59.9,
        )
        assert unlocks_in_time is not None
        assert unlocks_in_time["survived"] is True

        stays_locked_whole_horizon = run_decumulation_window(
            market_data.index[0], market_data, assumptions, horizon_years=1, swr=0.48,
            account_split=split, start_age_at_fire=30.0,
        )
        assert stays_locked_whole_horizon is not None
        assert stays_locked_whole_horizon["survived"] is False
        assert stays_locked_whole_horizon["failure_reason"] == "liquidity_gap"


class TestRunRollingDecumulation:
    def test_skips_windows_without_enough_runway(self):
        market_data = make_market_data(n_months=24)
        assumptions = SimulationAssumptions()
        results = run_rolling_decumulation(
            market_data, assumptions, horizon_years=1, step_months=1
        )
        # 24 miesiace danych, horyzont 12 mies. -> tylko pierwsze 13 miesiecy
        # startowych ma wystarczajaco duzo miejsca (24-12=12, wiec starty 0..12)
        assert len(results) == 13
        assert set(results.columns) >= {"start_month", "survived", "ending_balance", "min_balance"}


class TestSummarizeDecumulation:
    def test_empty_results(self):
        summary = summarize_decumulation(pd.DataFrame())
        assert summary["n_windows"] == 0
        assert summary["success_rate"] is None

    def test_mixed_survival_computes_success_rate_and_medians(self):
        results = pd.DataFrame(
            [
                {"start_month": 1, "survived": True, "ending_balance": 1.2, "min_balance": 0.5},
                {"start_month": 2, "survived": True, "ending_balance": 0.8, "min_balance": 0.3},
                {"start_month": 3, "survived": False, "ending_balance": 0.0, "min_balance": 0.0},
            ]
        )
        summary = summarize_decumulation(results)
        assert summary["n_windows"] == 3
        assert summary["success_rate"] == pytest.approx(2 / 3)
        assert summary["ending_balance_median"] == pytest.approx(1.0)  # mediana z [1.2, 0.8]
        assert summary["ending_balance_min"] == pytest.approx(0.8)
        assert summary["min_balance_median"] == pytest.approx(0.3)  # mediana z [0.5, 0.3, 0.0]
