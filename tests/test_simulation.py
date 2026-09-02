"""Testy pętli symulacyjnej (`src/simulation.py`).

Testy operują na małym, syntetycznym `market_data` o kontrolowanych,
ręcznie dobranych zwrotach -- nie na prawdziwych danych historycznych --
żeby sprawdzać konkretne własności (poprawność okablowania kaskady,
opodatkowanie dywidendy, rebalancing, wykrycie celu FIRE), a nie całe
wieloletnie trajektorie.

Portfel ma dwie nogi: akcje (ACWI) i obligacje (EDO) -- bez globalnych
obligacji (UST10Y), na wyraźną decyzję użytkownika.
"""

import pandas as pd
import pytest

from src.simulation import (
    ALL_ACCOUNTS,
    NO_ACCOUNTS,
    Archetype,
    SimulationAssumptions,
    _grow_account,
    _rebalance_standard_account,
    run_rolling_accumulation,
    run_simulation,
)
from src.tax_engine import LossCarryforward


def make_market_data(
    n_months: int = 14,
    start: str = "2020-01",
    acwi_return: float = 0.0,
    edo_return: float = 0.0,
    usd_pln: float = 4.0,
    avg_wage: float = 8_000.0,
    cpi: float = 103.0,
) -> pd.DataFrame:
    index = pd.period_range(start=start, periods=n_months, freq="M")
    return pd.DataFrame(
        {
            "acwi_monthly_return": acwi_return,
            "usd_pln": usd_pln,
            "edo_reference_monthly_return": edo_return,
            "cpi_prev_year_100": cpi,
            "avg_gross_wage_pln": avg_wage,
        },
        index=index,
    )


def make_archetype(**overrides) -> Archetype:
    defaults = dict(
        name="Test",
        monthly_net_income=5_000.0,
        savings_rate=0.30,
        employment_form="uop",
        marginal_tax_rate=0.12,
        ppk_eligible=False,
        household_multiplier=1,
    )
    defaults.update(overrides)
    return Archetype(**defaults)


class TestCascadeWiring:
    def test_surplus_within_ikze_limit_goes_to_ikze_not_standard(self):
        # wysokie przecietne wynagrodzenie -> wysokie limity -> caly, niewielki
        # miesieczny surplus mieści sie w limicie IKZE
        market_data = make_market_data(n_months=6, avg_wage=50_000.0)
        archetype = make_archetype(monthly_net_income=3_000.0, savings_rate=0.10)  # 300 zl/mies. surplus
        ledger, summary = run_simulation(archetype, market_data, enabled_accounts=ALL_ACCOUNTS)
        assert ledger["ikze"].iloc[-1] > 0
        assert ledger["standard"].iloc[-1] == pytest.approx(0.0)

    def test_no_accounts_enabled_sends_everything_to_standard(self):
        market_data = make_market_data(n_months=6, avg_wage=50_000.0)
        archetype = make_archetype(monthly_net_income=3_000.0, savings_rate=0.10)
        ledger, summary = run_simulation(archetype, market_data, enabled_accounts=NO_ACCOUNTS)
        assert ledger["ikze"].iloc[-1] == pytest.approx(0.0)
        assert ledger["ike"].iloc[-1] == pytest.approx(0.0)
        assert ledger["oki"].iloc[-1] == pytest.approx(0.0)
        assert ledger["standard"].iloc[-1] > 0

    def test_large_surplus_overflows_through_full_cascade_to_standard(self):
        # niskie przecietne wynagrodzenie -> male roczne limity -> duzy surplus
        # przelewa sie przez IKZE/IKE/OKI az do rachunku standardowego
        market_data = make_market_data(n_months=3, avg_wage=1_000.0)
        archetype = make_archetype(monthly_net_income=200_000.0, savings_rate=0.90)
        ledger, summary = run_simulation(archetype, market_data, enabled_accounts=ALL_ACCOUNTS)
        assert ledger["ikze"].iloc[0] > 0
        assert ledger["ike"].iloc[0] > 0
        assert ledger["oki"].iloc[0] > 0
        assert ledger["standard"].iloc[0] > 0

    def test_ppk_eligible_household_accumulates_ppk_balance(self):
        market_data = make_market_data(n_months=3, avg_wage=50_000.0)
        archetype = make_archetype(monthly_net_income=3_000.0, savings_rate=0.10, ppk_eligible=True)
        ledger, summary = run_simulation(archetype, market_data, enabled_accounts=ALL_ACCOUNTS)
        assert ledger["ppk"].iloc[-1] > 0

    def test_ppk_not_used_when_not_in_enabled_accounts_even_if_eligible(self):
        market_data = make_market_data(n_months=3, avg_wage=50_000.0)
        archetype = make_archetype(monthly_net_income=3_000.0, savings_rate=0.10, ppk_eligible=True)
        ledger, summary = run_simulation(
            archetype, market_data, enabled_accounts=frozenset({"ikze", "ike", "oki"})
        )
        assert ledger["ppk"].iloc[-1] == pytest.approx(0.0)
        assert ledger["ikze"].iloc[-1] > 0  # pozostale konta nadal aktywne

    def test_disabling_only_ike_spills_surplus_to_ikze_not_standard(self):
        # niski surplus, wysokie limity -> mieściłby się w IKE, ale IKE jest
        # wylaczone -> kaskada powinna go skierowac do IKZE (kolejne ogniwo),
        # nie od razu do rachunku standardowego
        market_data = make_market_data(n_months=3, avg_wage=50_000.0)
        archetype = make_archetype(monthly_net_income=3_000.0, savings_rate=0.10)
        ledger, summary = run_simulation(
            archetype, market_data, enabled_accounts=frozenset({"ikze", "oki"})
        )
        assert ledger["ike"].iloc[-1] == pytest.approx(0.0)
        assert ledger["ikze"].iloc[-1] > 0
        assert ledger["standard"].iloc[-1] == pytest.approx(0.0)


class TestGrowAccount:
    def test_dividend_tax_applies_only_on_standard_account(self):
        assumptions = SimulationAssumptions(dividend_yield_annual=0.024, acwi_ter_annual=0.0)  # 0.2%/mies.
        standard = {"equity": 100_000.0, "bond": 0.0}
        tax_advantaged = {"equity": 100_000.0, "bond": 0.0}

        div_tax_standard = _grow_account(standard, 0.01, 0.0, assumptions, is_standard=True)
        div_tax_taxadv = _grow_account(tax_advantaged, 0.01, 0.0, assumptions, is_standard=False)

        assert div_tax_standard > 0.0
        assert div_tax_taxadv == 0.0
        # ta sama stopa brutto -> konto uprzywilejowane rosnie szybciej (brak podatku od dywidendy)
        assert tax_advantaged["equity"] > standard["equity"]

    def test_grow_account_matches_manual_calculation_without_dividend(self):
        assumptions = SimulationAssumptions(dividend_yield_annual=0.0, acwi_ter_annual=0.0)
        account = {"equity": 1_000.0, "bond": 2_000.0}
        _grow_account(account, 0.05, 0.02, assumptions, is_standard=False)
        assert account["equity"] == pytest.approx(1_000.0 * 1.05)
        assert account["bond"] == pytest.approx(2_000.0 * 1.02)


class TestRebalanceStandardAccount:
    def test_overweight_equity_with_gain_generates_capital_gains_tax(self):
        assumptions = SimulationAssumptions()  # 80/20
        account = {"equity": 90_000.0, "bond": 10_000.0}  # 90/10, cel 80/20
        cost_basis = 60_000.0  # cale konto ma niezrealizowany zysk
        loss_registry = LossCarryforward()

        original_total = sum(account.values())
        tax_paid, new_cost_basis = _rebalance_standard_account(
            account, cost_basis, assumptions, loss_registry, current_year=2024
        )

        assert tax_paid > 0.0
        # sprzedaz doprowadza saldo equity dokladnie do docelowej kwoty (wzgledem
        # oryginalnego -- sprzed podatku -- salda); podatek pomniejsza jedynie
        # kwote dostepna do odkupienia niedowazonej obligacji
        assert account["equity"] == pytest.approx(original_total * assumptions.equity_weight)

    def test_account_at_a_loss_registers_loss_not_tax(self):
        assumptions = SimulationAssumptions()
        account = {"equity": 90_000.0, "bond": 10_000.0}
        cost_basis = 150_000.0  # cale konto ponizej kosztu
        loss_registry = LossCarryforward()

        tax_paid, _ = _rebalance_standard_account(
            account, cost_basis, assumptions, loss_registry, current_year=2024
        )

        assert tax_paid == pytest.approx(0.0)
        assert len(loss_registry.entries) == 1
        assert loss_registry.entries[0][0] == 2024


class TestAllocationVariants:
    def test_equity_weight_controls_bond_bond_split(self):
        market_data = make_market_data(n_months=3, avg_wage=50_000.0, acwi_return=0.0, edo_return=0.0)
        archetype = make_archetype(monthly_net_income=3_000.0, savings_rate=0.10)
        for equity_weight in (0.80, 0.60, 0.40):
            assumptions = SimulationAssumptions(equity_weight=equity_weight, bond_weight=1 - equity_weight)
            ledger, summary = run_simulation(
                archetype, market_data, enabled_accounts=NO_ACCOUNTS, assumptions=assumptions
            )
            assert summary["equity_weight"] == pytest.approx(equity_weight)
            # 100% nadwyzki na standard, zaraz po pierwszej wplacie, przed wzrostem/rebalancingiem
            # (miesiac 1) -- proporcja powinna odpowiadac zadanej wadze
            assert ledger["standard"].iloc[0] > 0


class TestMissingTailData:
    def test_nan_tail_in_annual_series_does_not_poison_portfolio_value(self):
        # regresja: GUS publikuje CPI/wynagrodzenie raz w roku, wiec ostatnie
        # miesiace biezacego roku maja NaN, dopoki symulacja sama ich nie
        # uzupelni (ffill) -- bez tego mnozenie salda przez (1+NaN) zeruje
        # caly wynik do konca.
        market_data = make_market_data(n_months=6, avg_wage=8_000.0)
        market_data.loc[market_data.index[-3:], "cpi_prev_year_100"] = float("nan")
        market_data.loc[market_data.index[-3:], "avg_gross_wage_pln"] = float("nan")

        archetype = make_archetype(monthly_net_income=5_000.0, savings_rate=0.10)
        ledger, summary = run_simulation(archetype, market_data, enabled_accounts=ALL_ACCOUNTS)

        assert not pd.isna(summary["final_portfolio_value"])
        assert not ledger["portfolio_value"].isna().any()

    def test_nan_head_in_usd_pln_does_not_poison_portfolio_value(self):
        # regresja: indeks MSCI ACWI siega 1988 r., ale kurs USD/PLN z NBP
        # dopiero 2002 r. -- wczesniejsze miesiace maja NaN w usd_pln, dopoki
        # symulacja ich nie odetnie (nie da sie ich forward-fillowac, bo to
        # brak danych na POCZATKU szeregu, a nie na koncu).
        market_data = make_market_data(n_months=6, avg_wage=8_000.0)
        market_data.loc[market_data.index[:2], "usd_pln"] = float("nan")

        archetype = make_archetype(monthly_net_income=5_000.0, savings_rate=0.10)
        ledger, summary = run_simulation(archetype, market_data, enabled_accounts=ALL_ACCOUNTS)

        assert not pd.isna(summary["final_portfolio_value"])
        assert not ledger["portfolio_value"].isna().any()
        # symulacja powinna zaczac sie dopiero od 3. miesiaca (pierwszy z realnym usd_pln)
        assert len(ledger) == 4

    def test_nan_head_in_avg_wage_does_not_poison_portfolio_value(self):
        # regresja: po wydluzeniu historii kursu NBP do 1995 r. i EDO/referencyjnej
        # do 1998 r., to dane GUS o przecietnym wynagrodzeniu (dostepne dopiero
        # od 2002 r.) staly sie najkrotszym z wymaganych zrodel -- bez odciecia
        # poczatku szeregu base_wage (pierwsza wartosc) bylby NaN, zatruwajac
        # caly wskaznik wzrostu dochodu od pierwszego miesiaca.
        market_data = make_market_data(n_months=6, avg_wage=8_000.0)
        market_data.loc[market_data.index[:2], "avg_gross_wage_pln"] = float("nan")

        archetype = make_archetype(monthly_net_income=5_000.0, savings_rate=0.10)
        ledger, summary = run_simulation(archetype, market_data, enabled_accounts=ALL_ACCOUNTS)

        assert not pd.isna(summary["final_portfolio_value"])
        assert not ledger["portfolio_value"].isna().any()
        assert len(ledger) == 4


class TestFireDetection:
    def test_huge_return_triggers_fire_detection(self):
        # zwrot dobrany tak, by przy skladaniu przez kilka miesiecy z pewnoscia
        # przekroczyc cel -- test sprawdza samo wykrycie, nie konkretny miesiac
        market_data = make_market_data(n_months=3, acwi_return=10.0, avg_wage=50_000.0)
        archetype = make_archetype(monthly_net_income=5_000.0, savings_rate=0.30)
        ledger, summary = run_simulation(archetype, market_data, enabled_accounts=ALL_ACCOUNTS)
        assert summary["fire_reached"] is True
        assert summary["fire_month"] is not None
        assert summary["final_portfolio_value"] >= summary["target_at_fire"]

    def test_flat_returns_do_not_reach_fire_within_short_window(self):
        market_data = make_market_data(n_months=6, acwi_return=0.0, avg_wage=8_000.0)
        archetype = make_archetype(monthly_net_income=5_000.0, savings_rate=0.10)
        ledger, summary = run_simulation(archetype, market_data, enabled_accounts=ALL_ACCOUNTS)
        assert summary["fire_reached"] is False
        assert summary["fire_month"] is None
        assert summary["final_portfolio_value"] < summary["target_at_end"]


class TestStartMonth:
    def test_omitting_start_month_uses_full_range(self):
        market_data = make_market_data(n_months=6, avg_wage=8_000.0)
        archetype = make_archetype(monthly_net_income=5_000.0, savings_rate=0.30)
        ledger, _ = run_simulation(archetype, market_data, enabled_accounts=ALL_ACCOUNTS)
        assert ledger.index[0] == market_data.index[0]

    def test_start_month_anchors_income_to_wage_at_that_month_not_month_zero(self):
        # przecietne wynagrodzenie rosnie z kazdym miesiacem -- jesli symulacja
        # poprawnie kotwiczy dochod archetypu w miesiacu STARTOWYM (nie
        # pierwszym miesiacu calego zbioru danych), to target w PIERWSZYM
        # wierszu ledgera powinien byc taki sam niezaleznie od tego, kiedy
        # zaczynamy -- bo wskaznik wzrostu wynagrodzenia = 1.0 na starcie
        # kazdego okna z osobna.
        market_data = make_market_data(n_months=12)
        index = market_data.index
        market_data["avg_gross_wage_pln"] = [8_000.0 * (1.01**i) for i in range(12)]

        archetype = make_archetype(monthly_net_income=5_000.0, savings_rate=0.50)
        ledger_from_start, _ = run_simulation(archetype, market_data, enabled_accounts=ALL_ACCOUNTS)
        ledger_later, _ = run_simulation(
            archetype, market_data, enabled_accounts=ALL_ACCOUNTS, start_month=index[5]
        )

        expected_target = 25.0 * 12.0 * 5_000.0 * 0.50
        # cel w pierwszym wierszu obu ledgerow powinien byc identyczny -- kazdy
        # z nich liczy wskaznik wzrostu wynagrodzenia wzgledem WLASNEGO miesiaca
        # startowego, wiec oba "startuja" z tym samym, niezaburzonym dochodem
        assert ledger_from_start["target"].iloc[0] == pytest.approx(expected_target)
        assert ledger_later["target"].iloc[0] == pytest.approx(expected_target)

    def test_start_month_outside_data_range_raises(self):
        market_data = make_market_data(n_months=6, avg_wage=8_000.0)
        archetype = make_archetype(monthly_net_income=5_000.0, savings_rate=0.30)
        with pytest.raises(ValueError):
            run_simulation(
                archetype,
                market_data,
                enabled_accounts=ALL_ACCOUNTS,
                start_month=pd.Period("2099-01", freq="M"),
            )


class TestRollingAccumulation:
    def test_ample_runway_gives_zero_percent_not_reached_and_ordered_stats(self):
        # zwrot dobrany tak, by cel byl osiagany w ciagu pojedynczych miesiecy
        # (jak w TestFireDetection) -- przy takim tempie prawie kazdy mozliwy
        # miesiac startowy ma wystarczajaco duzo danych naprzod, zeby zdazyc
        market_data = make_market_data(n_months=24, acwi_return=10.0, avg_wage=50_000.0)
        archetype = make_archetype(monthly_net_income=3_000.0, savings_rate=0.50)

        result = run_rolling_accumulation(archetype, market_data, enabled_accounts=ALL_ACCOUNTS)

        assert result["n_windows"] == 4  # 24 miesiace // step_months=6 (domyslny krok)
        # dopuszczamy niewielki odsetek okien tuz przy koncu danych, ktorym moglo
        # zabraknac nawet 1-2 miesiecy zapasu -- istotna jest zdecydowana wiekszosc
        assert result["pct_windows_not_reached"] < 0.2
        assert result["n_reached"] > 0
        assert result["years_to_fire_min"] <= result["years_to_fire_median"] <= result["years_to_fire_max"]

    def test_insufficient_runway_reports_all_windows_not_reached(self):
        # za malo miesiecy w calym zbiorze danych, zeby ktokolwiek zdazyl
        market_data = make_market_data(n_months=2, avg_wage=1_000.0)
        archetype = make_archetype(monthly_net_income=3_000.0, savings_rate=0.10)

        result = run_rolling_accumulation(archetype, market_data, enabled_accounts=ALL_ACCOUNTS)

        assert result["n_reached"] == 0
        assert result["pct_windows_not_reached"] == pytest.approx(1.0)
        assert result["years_to_fire_median"] is None
        assert result["years_to_fire_min"] is None
        assert result["years_to_fire_max"] is None
