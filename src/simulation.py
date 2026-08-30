"""Miesięczna pętla symulacyjna modelu FIRE-PL: spina `tax_engine` (kaskada
podatkowa) z `data_loader` (rzeczywiste dane rynkowe) w jedną, historyczną
ścieżkę akumulacji kapitału dla zadanego archetypu gospodarstwa domowego.

Zgodnie z ustaleniem: symulacja biegnie JEDNĄ, nieprzetworzoną historyczną
sekwencją zwrotów (od pierwszego pełnego miesiąca danych ACWI do ostatniego
dostępnego miesiąca w `market_data.csv`) -- bez cyklicznego powielania danych
i bez wielu okien startowych (Monte Carlo). Jeśli cel FIRE nie zostanie
osiągnięty w tym oknie, wynik jawnie to raportuje (`fire_reached=False`)
zamiast ekstrapolować nieistniejące dane, zgodnie z podrozdz. 3.1 pracy
("symulacja historyczna, nie Monte Carlo").

Portfel ma dwie nogi: globalny ETF akcyjny (ACWI) i polskie detaliczne
obligacje EDO -- na wyraźną decyzję użytkownika, w modelu nie ma już
globalnych obligacji (Damodaran/UST10Y). Proporcja akcje/obligacje jest
parametryzowana (`SimulationAssumptions.equity_weight`) -- `scenarios.py`
uruchamia każdy scenariusz w kilku wariantach alokacji (80/20, 60/40, 40/60),
żeby zbadać "elastyczną alokację aktywów" z hipotezy badawczej pracy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from src.tax_engine import (
    AccountYTDState,
    LossCarryforward,
    allocate_monthly_surplus,
    annual_limit,
    apply_loss_relief,
    capital_gains_tax_on_rebalancing,
    dividend_tax,
    ikze_refund_payout_date,
    ppk_monthly_contribution,
    ppk_state_topups,
    register_loss,
)

ACCOUNT_NAMES = ["ppk", "ikze", "ike", "oki", "standard"]
ASSET_NAMES = ["equity", "bond"]
TAX_FREE_ACCOUNTS = ["ppk", "ikze", "ike", "oki"]  # rebalancing bez zdarzenia podatkowego
OKI_INDEXATION_START_YEAR = 2030


@dataclass
class SimulationAssumptions:
    """Założenia rynkowo-kosztowe modelu, jawnie udokumentowane i uzasadnione
    (patrz README, sekcja "Symulacja i scenariusze") -- nie ukryte domysły.

    `equity_weight` + `bond_weight` powinny sumować się do 1.0 -- to
    `scenarios.py` odpowiada za wygenerowanie kilku wariantów tej pary
    (80/20, 60/40, 40/60), nie ten moduł.
    """

    equity_weight: float = 0.80
    bond_weight: float = 0.20
    acwi_ter_annual: float = 0.0020
    dividend_yield_annual: float = 0.015
    transaction_cost_rate: float = 0.0029
    rebalancing_month: int = 12
    fire_swr: float = 0.04


@dataclass
class Archetype:
    """Parametryzacja gospodarstwa domowego (podrozdz. 3.4 pracy / sekcja 4 spec)."""

    name: str
    monthly_net_income: float
    savings_rate: float
    employment_form: Literal["uop", "b2b"]
    marginal_tax_rate: float  # do obliczenia zwrotu podatku z ulgi IKZE (nie do wyboru kolejności kaskady -- ta jest stała)
    ppk_eligible: bool
    household_multiplier: int  # 1 = jedna osoba, 2 = oboje rodzice (podwójne roczne limity IKE/IKZE/PPK)


def _empty_account() -> dict[str, float]:
    return {asset: 0.0 for asset in ASSET_NAMES}


def _account_total(account: dict[str, float]) -> float:
    return sum(account.values())


def _portfolio_total(portfolio: dict[str, dict[str, float]]) -> float:
    return sum(_account_total(a) for a in portfolio.values())


def _add_contribution(account: dict[str, float], amount: float, assumptions: SimulationAssumptions) -> None:
    """Dopisuje nową wpłatę do konta, rozdzieloną wg wag docelowych -- nowe
    pieniądze zawsze trafiają "na wagę", więc dryf portfela bierze się
    wyłącznie z różnicy w tempie wzrostu poszczególnych klas aktywów
    w czasie, nie z samych wpłat."""
    account["equity"] += amount * assumptions.equity_weight
    account["bond"] += amount * assumptions.bond_weight


def _grow_account(
    account: dict[str, float],
    equity_gross_return: float,
    bond_return: float,
    assumptions: SimulationAssumptions,
    is_standard: bool,
) -> float:
    """Nalicza miesięczny zwrot na saldzie konta; zwraca kwotę podatku od
    dywidendy pobranego w tym miesiącu (0 dla kont uprzywilejowanych
    podatkowo). Dywidenda i TER dotyczą wyłącznie nogi akcyjnej (ACWI)."""
    ter_monthly = assumptions.acwi_ter_annual / 12
    if is_standard:
        dividend_monthly_rate = assumptions.dividend_yield_annual / 12
        dividend_gross = account["equity"] * dividend_monthly_rate
        dividend_tax_amount, dividend_net = dividend_tax(dividend_gross)
        price_return = equity_gross_return - dividend_monthly_rate - ter_monthly
        account["equity"] = account["equity"] * (1 + price_return) + dividend_net
    else:
        dividend_tax_amount = 0.0
        account["equity"] *= 1 + (equity_gross_return - ter_monthly)

    account["bond"] *= 1 + bond_return
    return dividend_tax_amount


def _rebalance_tax_free_account(account: dict[str, float], assumptions: SimulationAssumptions) -> None:
    """PPK/IKZE/IKE/OKI: sprzedaż i zakup wewnątrz konta uprzywilejowanego
    podatkowo nie generuje zdarzenia podatkowego -- po prostu ustawiamy
    salda na wagi docelowe."""
    total = _account_total(account)
    if total <= 0:
        return
    account["equity"] = total * assumptions.equity_weight
    account["bond"] = total * assumptions.bond_weight


def _rebalance_standard_account(
    account: dict[str, float],
    cost_basis: float,
    assumptions: SimulationAssumptions,
    loss_registry: LossCarryforward,
    current_year: int,
) -> tuple[float, float]:
    """Rachunek standardowy: sprzedaż przeważonej klasy aktywów generuje
    podatek Belki od części stanowiącej zysk (`capital_gains_tax_on_rebalancing`,
    z uwzględnieniem kompensacji strat), zakup niedoważonej -- nie.
    Zwraca (zapłacony podatek, zaktualizowana podstawa kosztowa).
    """
    total = _account_total(account)
    if total <= 0:
        return 0.0, cost_basis

    targets = {
        "equity": total * assumptions.equity_weight,
        "bond": total * assumptions.bond_weight,
    }
    # ulamek biezacej wartosci stanowiacy niezrealizowany zysk wzgledem podstawy
    # kosztowej -- moze byc ujemny (portfel ponizej kosztu, sprzedaz realizuje strate)
    gain_fraction = (total - cost_basis) / total

    tax_paid = 0.0
    pool_after_tax = 0.0
    shortfalls: dict[str, float] = {}
    for asset in ASSET_NAMES:
        diff = account[asset] - targets[asset]
        if diff > 1e-9:
            realized_pnl = diff * gain_fraction
            if realized_pnl > 0:
                _, taxable_gain = apply_loss_relief(loss_registry, current_year, realized_pnl)
                tax = capital_gains_tax_on_rebalancing(taxable_gain)
            else:
                tax = 0.0
                if realized_pnl < 0:
                    register_loss(loss_registry, current_year, -realized_pnl)
            tax_paid += tax
            cost_basis -= diff * (1 - gain_fraction)
            account[asset] -= diff
            pool_after_tax += diff - tax
        elif diff < -1e-9:
            shortfalls[asset] = -diff

    shortfall_total = sum(shortfalls.values())
    if shortfall_total > 0 and pool_after_tax > 0:
        for asset, need in shortfalls.items():
            share = pool_after_tax * (need / shortfall_total)
            account[asset] += share
            cost_basis += share

    return tax_paid, cost_basis


def run_simulation(
    archetype: Archetype,
    market_data: pd.DataFrame,
    use_tax_vehicles: bool,
    assumptions: SimulationAssumptions | None = None,
    oki_kind: str = "investment",
) -> tuple[pd.DataFrame, dict]:
    """Uruchamia miesięczną symulację akumulacji kapitału dla jednego
    archetypu i wariantu (z/bez wehikułów podatkowych) na rzeczywistej,
    historycznej sekwencji zwrotów z `market_data` (wynik
    `data_loader.build_processed_dataset()`).

    Zwraca (miesięczny_ledger, podsumowanie). Podsumowanie zawiera m.in.
    `fire_reached`, `fire_month`, `years_to_fire`, `final_portfolio_value`,
    `target_at_end`, `cumulative_tax_paid`.
    """
    assumptions = assumptions or SimulationAssumptions()

    data = market_data.sort_index().copy()
    # CPI i przecietne wynagrodzenie sa publikowane raz w roku -- dla miesiecy
    # nowszych niz ostatni opublikowany rok (np. biezacy rok kalendarzowy,
    # zanim GUS go zamknie danymi) przenosimy ostatnia znana wartosc naprzod.
    # To musi sie stac PRZED przycieciem (dropna) ponizej -- w przeciwnym
    # razie te "nadajace sie do naprawy" koncowe miesiace zostalyby po prostu
    # odciete zamiast wypelnione, sztucznie skracajac symulacje.
    data["cpi_prev_year_100"] = data["cpi_prev_year_100"].ffill()
    data["avg_gross_wage_pln"] = data["avg_gross_wage_pln"].ffill()

    # przycinamy do okresu, w ktorym WSZYSTKIE skladniki potrzebne do policzenia
    # zwrotu portfela ORAZ dochodu gospodarstwa sa dostepne. Kazde zrodlo ma
    # inny zweryfikowany zakres (ACWI: 1987+, NBP FX: 1995+, EDO/NBP
    # referencyjna: 1998+, GUS wynagrodzenie: 2002+) -- najkrotszy z nich
    # wyznacza faktyczny poczatek symulacji (a to, co zostalo naprawione
    # przez ffill powyzej, tu juz nie jest NaN, wiec nie zostanie ucietego).
    # Samo dropna po ACWI nie wystarcza: wczesniejsze miesiace mialyby NaN
    # w pozostalych kolumnach, co przez mnozenie (1+NaN) zatrulyby caly wynik.
    data = data.dropna(
        subset=[
            "acwi_monthly_return",
            "usd_pln",
            "edo_reference_monthly_return",
            "avg_gross_wage_pln",
        ]
    )
    data["usd_pln_change"] = data["usd_pln"].pct_change().fillna(0.0)

    base_wage = data["avg_gross_wage_pln"].iloc[0]

    portfolio: dict[str, dict[str, float]] = {name: _empty_account() for name in ACCOUNT_NAMES}
    standard_cost_basis = 0.0
    ytd_state = AccountYTDState()
    loss_registry = LossCarryforward()
    current_calendar_year: int | None = None
    cumulative_oki_inflation = 1.0
    prev_year_cpi_seen_for_oki: set[int] = set()
    limits = {"ikze": 0.0, "ike": 0.0, "oki": 0.0}
    ikze_contributions_this_year = 0.0
    pending_ikze_refunds: dict[tuple[int, int], float] = {}  # (rok, kwartal) -> kwota

    rows = []
    fire_month = None
    target_at_fire = None

    for month, row in data.iterrows():
        year, cal_month = month.year, month.month
        quarter = (cal_month - 1) // 3 + 1

        if year != current_calendar_year:
            # nowy rok kalendarzowy: reset limitow YTD i przeliczenie limitow rocznych
            current_calendar_year = year
            ytd_state = AccountYTDState()
            ikze_contributions_this_year = 0.0
            avg_wage_this_year = data.loc[data.index.year == year, "avg_gross_wage_pln"].iloc[0]
            if year >= OKI_INDEXATION_START_YEAR and year not in prev_year_cpi_seen_for_oki:
                prev_year_cpi_seen_for_oki.add(year)
                inflation_last_year = (
                    data.loc[data.index.year == year - 1, "cpi_prev_year_100"].iloc[-1] - 100.0
                ) / 100.0
                cumulative_oki_inflation *= 1.0 + inflation_last_year
            limits = {
                "ikze": annual_limit("IKZE", avg_wage_this_year, employment_form=archetype.employment_form)
                * archetype.household_multiplier,
                "ike": annual_limit("IKE", avg_wage_this_year) * archetype.household_multiplier,
                "oki": annual_limit(
                    "OKI",
                    avg_wage_this_year,
                    oki_kind=oki_kind,
                    year=year,
                    cumulative_inflation_since_2030=cumulative_oki_inflation,
                )
                * archetype.household_multiplier,
            }

        wage_index = row["avg_gross_wage_pln"] / base_wage
        monthly_net_income = archetype.monthly_net_income * wage_index
        surplus = monthly_net_income * archetype.savings_rate

        # zwrot podatku z ulgi IKZE zaplanowany na ten miesiac (Q2 roku t+1) -- reinwestowany ta sama kaskada
        refund_key = (year, quarter)
        if refund_key in pending_ikze_refunds and cal_month == 4:
            surplus += pending_ikze_refunds.pop(refund_key)

        if use_tax_vehicles:
            if archetype.ppk_eligible:
                employee_contrib, employer_contrib = ppk_monthly_contribution(monthly_net_income)
                # miesiac uczestnictwa w PPK liczony od poczatku symulacji (przyblizenie -- patrz README)
                month_index_in_ppk = len(rows) + 1
                state_topup = ppk_state_topups(month_index_in_ppk) * archetype.household_multiplier
                _add_contribution(portfolio["ppk"], employer_contrib + state_topup, assumptions)
                surplus_after_ppk = max(0.0, surplus - employee_contrib)
                _add_contribution(portfolio["ppk"], employee_contrib, assumptions)
            else:
                surplus_after_ppk = surplus

            allocation = allocate_monthly_surplus(
                surplus_after_ppk,
                ytd_state,
                {"ikze": limits["ikze"], "ike": limits["ike"], "oki": limits["oki"]},
                ppk_eligible=False,  # PPK juz obsluzone osobno powyzej
            )
            for account_name in ["ikze", "ike", "oki", "standard"]:
                _add_contribution(portfolio[account_name], allocation[account_name], assumptions)
            ikze_contributions_this_year += allocation["ikze"]
            standard_cost_basis += allocation["standard"]
        else:
            _add_contribution(portfolio["standard"], surplus, assumptions)
            standard_cost_basis += surplus

        equity_gross = (1 + row["acwi_monthly_return"]) * (1 + row["usd_pln_change"]) - 1
        bond_return = row["edo_reference_monthly_return"]  # EDO jest juz w PLN, bez przeliczenia FX

        dividend_tax_total = 0.0
        for account_name, account in portfolio.items():
            dividend_tax_total += _grow_account(
                account,
                equity_gross,
                bond_return,
                assumptions,
                is_standard=(account_name == "standard"),
            )

        rebalancing_tax = 0.0
        if cal_month == assumptions.rebalancing_month:
            for account_name in TAX_FREE_ACCOUNTS:
                _rebalance_tax_free_account(portfolio[account_name], assumptions)
            rebalancing_tax, standard_cost_basis = _rebalance_standard_account(
                portfolio["standard"], standard_cost_basis, assumptions, loss_registry, year
            )

        if cal_month == 12:
            refund_amount = ikze_contributions_this_year * archetype.marginal_tax_rate
            if refund_amount > 0:
                payout_year, payout_quarter = ikze_refund_payout_date(year)
                pending_ikze_refunds[(payout_year, payout_quarter)] = (
                    pending_ikze_refunds.get((payout_year, payout_quarter), 0.0) + refund_amount
                )

        total_value = _portfolio_total(portfolio)
        target = 25.0 * 12.0 * monthly_net_income * (1.0 - archetype.savings_rate)

        rows.append(
            {
                "month": month,
                "portfolio_value": total_value,
                "target": target,
                "ppk": _account_total(portfolio["ppk"]),
                "ikze": _account_total(portfolio["ikze"]),
                "ike": _account_total(portfolio["ike"]),
                "oki": _account_total(portfolio["oki"]),
                "standard": _account_total(portfolio["standard"]),
                "dividend_tax": dividend_tax_total,
                "rebalancing_tax": rebalancing_tax,
            }
        )

        if fire_month is None and total_value >= target:
            fire_month = month
            target_at_fire = target

    ledger = pd.DataFrame(rows).set_index("month")
    summary = {
        "archetype": archetype.name,
        "use_tax_vehicles": use_tax_vehicles,
        "equity_weight": assumptions.equity_weight,
        "fire_reached": fire_month is not None,
        "fire_month": str(fire_month) if fire_month is not None else None,
        "years_to_fire": (
            (fire_month - data.index[0]).n / 12.0 if fire_month is not None else None
        ),
        "final_portfolio_value": ledger["portfolio_value"].iloc[-1],
        "target_at_end": ledger["target"].iloc[-1],
        "target_at_fire": target_at_fire,
        "cumulative_dividend_tax": ledger["dividend_tax"].sum(),
        "cumulative_rebalancing_tax": ledger["rebalancing_tax"].sum(),
    }
    return ledger, summary
