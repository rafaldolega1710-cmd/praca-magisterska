"""Silnik podatkowy modelu FIRE-PL: kaskadowa alokacja nadwyżki budżetowej
(PPK -> IKZE -> IKE -> OKI -> rachunek standardowy) oraz mechanika podatkowa
poszczególnych wehikułów.

Zgodnie z podrozdziałem 3.3 pracy magisterskiej ("Algorytmizacja wpływu
polskiego systemu podatkowego na akumulację kapitału") oraz sekcją 3
`fire_model_spec.md`. Moduł jest celowo niezależny od danych rynkowych
(`data_loader.py`) i pętli symulacyjnej (`simulation.py`) -- operuje
wyłącznie na kwotach pieniężnych i datach, co czyni go w pełni testowalnym
w oderwaniu od reszty modelu.

Wszystkie kwoty pieniężne jako `float`. Model ma charakter ilustracyjny co
do rzędu wielkości (patrz ograniczenia w README), nie księgowości co do
grosza, a `float` zachowuje spójność z wektoryzacją w pandas/numpy, na
której oprze się `simulation.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

AccountType = Literal["IKE", "IKZE"]
EmploymentForm = Literal["uop", "b2b"]
OkiKind = Literal["investment", "savings"]
PriorityMode = Literal["tax_efficiency", "liquidity_first"]

# Progi ustawowe Osobistego Konta Inwestycyjnego (OKI), stałe do 2030 r.,
# zgodnie z sekcją 3.3 spec ("indeksowany inflacyjnie dopiero od 2030 r.").
OKI_THRESHOLD_INVESTMENT = 100_000.0
OKI_THRESHOLD_SAVINGS = 25_000.0
OKI_INDEXATION_START_YEAR = 2030

# Stawki ustawowe wykorzystywane w kilku miejscach modułu.
BELKA_TAX_RATE = 0.19          # zryczałtowany podatek od zysków kapitałowych i dywidend
IKZE_PAYOUT_TAX_RATE = 0.10    # ryczałt od wypłaty z IKZE po osiągnięciu wieku uprawniającego
PPK_EMPLOYEE_RATE_DEFAULT = 0.02
PPK_EMPLOYER_RATE_DEFAULT = 0.015
PPK_WELCOME_BONUS = 250.0
PPK_ANNUAL_STATE_TOPUP = 240.0
PPK_EMPLOYER_PENALTY_RATE = 0.30  # utrata 30% wpłat pracodawcy przy zwrocie
LOSS_CARRYFORWARD_YEARS = 5
LOSS_CARRYFORWARD_MAX_SHARE = 0.5  # max 50% pierwotnej straty odliczane w jednym roku


# ---------------------------------------------------------------------------
# 1. Mnożnik efektywny IKE vs IKZE
# ---------------------------------------------------------------------------

def effective_multiplier(account_type: AccountType, marginal_tax_rate: float) -> float:
    """Zwraca ułamek kwoty brutto X, jaki po opodatkowaniu i skumulowanym
    wzroście `g` trafia ostatecznie do inwestora netto z danego konta
    (z pominięciem `g`, wspólnego dla obu wehikułów -- porównanie sprowadza
    się do porównania samych mnożników podatkowych).

    IKE: brak ulgi na wejściu (wpłacamy X*(1-t)), zwolnienie w całości na
    wyjściu -> mnożnik = (1 - t).
    IKZE: cała kwota X trafia na konto (ulga na wejściu), na wyjściu
    ryczałt 10% od całości -> mnożnik = 0.9, niezależnie od `t`.

    Ponieważ polskie stawki skali PIT (12%, 32%) obie przekraczają 10%,
    (1 - t) < 0.9 zawsze -- IKZE matematycznie dominuje nad IKE przy
    założeniu reinwestycji zwrotu podatku z ulgi (patrz `ikze_refund_payout_date`).
    Przewaga: 2 p.p. przy t=12%, 22 p.p. przy t=32%. To uzasadnia kolejność
    IKZE przed IKE w kaskadzie (`allocate_monthly_surplus`).
    """
    if account_type == "IKE":
        return 1.0 - marginal_tax_rate
    if account_type == "IKZE":
        return 1.0 - IKZE_PAYOUT_TAX_RATE
    raise ValueError(f"Nieznany typ konta: {account_type!r}")


# ---------------------------------------------------------------------------
# 2. Roczne limity wpłat
# ---------------------------------------------------------------------------

def annual_limit(
    account_type: Literal["IKE", "IKZE", "OKI"],
    avg_wage: float,
    employment_form: EmploymentForm | None = None,
    oki_kind: OkiKind | None = None,
    year: int | None = None,
    cumulative_inflation_since_2030: float = 1.0,
) -> float:
    """Roczny limit wpłat na dane konto.

    Limity IKE/IKZE nie są stałe -- przeliczane są co rok symulacji na
    podstawie prognozowanego przeciętnego wynagrodzenia `avg_wage`
    (podrozdz. 3.3): IKE = 3*W, IKZE = 1,2*W (UoP) lub 1,8*W (B2B/JDG),
    bo wyższy limit dla działalności gospodarczej wynika z konstrukcji
    ustawowej niezależnej od tego modelu.

    Próg OKI jest odmienny: to nie wielokrotność wynagrodzenia, lecz
    kwota nominalna (100 000 zł aktywa inwestycyjne / 25 000 zł
    oszczędnościowe), niezmieniona aż do 2030 r., dopiero od tego roku
    indeksowana inflacyjnie -- stąd osobny parametr
    `cumulative_inflation_since_2030`, przekazywany przez wywołującego
    (symulację), a nie liczony tutaj, żeby ten moduł pozostał wolny od
    zależności od pełnej ścieżki inflacji.
    """
    if account_type == "IKE":
        return 3.0 * avg_wage
    if account_type == "IKZE":
        if employment_form is None:
            raise ValueError("IKZE wymaga podania employment_form ('uop' lub 'b2b')")
        multiplier = 1.8 if employment_form == "b2b" else 1.2
        return multiplier * avg_wage
    if account_type == "OKI":
        if oki_kind is None:
            raise ValueError("OKI wymaga podania oki_kind ('investment' lub 'savings')")
        base = OKI_THRESHOLD_INVESTMENT if oki_kind == "investment" else OKI_THRESHOLD_SAVINGS
        if year is not None and year >= OKI_INDEXATION_START_YEAR:
            return base * cumulative_inflation_since_2030
        return base
    raise ValueError(f"Nieznany typ konta: {account_type!r}")


# ---------------------------------------------------------------------------
# 3. Mechanika PPK
# ---------------------------------------------------------------------------

def ppk_monthly_contribution(
    gross_salary: float,
    employee_rate: float = PPK_EMPLOYEE_RATE_DEFAULT,
    employer_rate: float = PPK_EMPLOYER_RATE_DEFAULT,
) -> tuple[float, float]:
    """Miesięczna składka podstawowa PPK: (składka pracownika, składka pracodawcy).

    Składka pracownika pomniejsza bieżący budżet operacyjny gospodarstwa
    domowego (nie jest częścią "nadwyżki" kierowanej do kaskady -- jest
    potrącana bezpośrednio z wynagrodzenia). Składka pracodawcy to kapitał
    zewnętrzny, niezależny od stopy oszczędności inwestora.
    """
    return gross_salary * employee_rate, gross_salary * employer_rate


def ppk_state_topups(month_index_in_program: int) -> float:
    """Dopłaty państwa do PPK należne w danym miesiącu uczestnictwa
    (indeksowanym od 1).

    Wpłata powitalna 250 zł jednorazowo w pierwszym miesiącu uczestnictwa,
    dopłata roczna 240 zł w każdym miesiącu rocznicowym (co 12 miesięcy).
    """
    topup = 0.0
    if month_index_in_program == 1:
        topup += PPK_WELCOME_BONUS
    if month_index_in_program % 12 == 0:
        topup += PPK_ANNUAL_STATE_TOPUP
    return topup


def ppk_early_withdrawal_penalty(
    state_topups_total: float,
    employer_contrib_total: float,
    investment_gain: float,
) -> dict[str, float]:
    """Rozbicie kary za wcześniejszy zwrot środków z PPK (przed 60 r.ż.,
    poza wyjątkami ustawowymi).

    Sankcja obejmuje trzy niezależne elementy (podrozdz. 3.3/2.2): utratę
    100% dopłat państwowych (powitalnej + rocznych), utratę 30% skumulowanych
    wpłat pracodawcy, oraz 19% podatek Belki od zysku inwestycyjnego, który
    pozostaje po odjęciu utraconych dopłat i wpłat pracodawcy (bo to on,
    a nie wpłaty własne pracownika, stanowi "zysk" w rozumieniu ustawy o PPK
    w tym uproszczonym modelu).
    """
    lost_state_topups = state_topups_total
    lost_employer_share = employer_contrib_total * PPK_EMPLOYER_PENALTY_RATE
    taxable_gain = max(0.0, investment_gain - lost_state_topups - lost_employer_share)
    belka_tax = taxable_gain * BELKA_TAX_RATE
    total_penalty = lost_state_topups + lost_employer_share + belka_tax
    return {
        "lost_state_topups": lost_state_topups,
        "lost_employer_share": lost_employer_share,
        "belka_tax": belka_tax,
        "total_penalty": total_penalty,
    }


# ---------------------------------------------------------------------------
# 4. Kaskadowa alokacja nadwyżki (waterfall / asset location)
# ---------------------------------------------------------------------------

@dataclass
class AccountYTDState:
    """Kwoty wpłacone od początku bieżącego roku kalendarzowego na każde
    z kont objętych kaskadą. Resetowane przez wywołującego (symulację) na
    początku każdego roku -- ten moduł świadomie nie zna bieżącej daty.
    """

    ppk_ytd: float = 0.0
    ikze_ytd: float = 0.0
    ike_ytd: float = 0.0
    oki_ytd: float = 0.0


def allocate_monthly_surplus(
    surplus: float,
    state: AccountYTDState,
    limits: dict[str, float],
    priority_mode: PriorityMode = "tax_efficiency",
    ppk_eligible: bool = True,
) -> dict[str, float]:
    """Rozdziela miesięczną nadwyżkę budżetową na konta zgodnie z algorytmem
    kaskadowym (waterfall / asset location, podrozdz. 3.1/3.3).

    `limits` to słownik rocznych limitów dla kluczy "ppk", "ikze", "ike",
    "oki" (patrz `annual_limit`; limit PPK w tym uproszczeniu modelowany
    jest jako brak twardego pułapu -- w praktyce ograniczony jedynie
    wysokością wynagrodzenia, więc wywołujący może przekazać dużą liczbę
    lub pominąć klucz "ppk", jeśli nie chce PPK w kaskadzie).

    Domyślna kolejność ("tax_efficiency"): PPK -> IKZE -> IKE -> OKI ->
    reszta na rachunek standardowy -- każde konto wysycane jest w pełni
    (do limitu), zanim nadwyżka przejdzie do kolejnego, a nie proporcjonalnie
    między wszystkie na raz, bo to właśnie ta kolejność maksymalizuje
    efektywność podatkową (patrz `effective_multiplier`).

    "liquidity_first" podnosi OKI przed IKE/IKZE -- wariant dla scenariuszy,
    w których płynność środków przed 60. rokiem życia jest wiążącym
    ograniczeniem (podrozdz. 3.4), kosztem części korzyści podatkowej.

    Modyfikuje `state` w miejscu (akumulacja YTD) i zwraca rozbicie kwot
    przydzielonych w danym miesiącu do każdego konta.
    """
    remaining = surplus
    allocation = {"ppk": 0.0, "ikze": 0.0, "ike": 0.0, "oki": 0.0, "standard": 0.0}

    if priority_mode == "tax_efficiency":
        order = ["ppk", "ikze", "ike", "oki"]
    elif priority_mode == "liquidity_first":
        order = ["ppk", "oki", "ikze", "ike"]
    else:
        raise ValueError(f"Nieznany priority_mode: {priority_mode!r}")

    ytd_by_key = {
        "ppk": "ppk_ytd",
        "ikze": "ikze_ytd",
        "ike": "ike_ytd",
        "oki": "oki_ytd",
    }

    for key in order:
        if key == "ppk" and not ppk_eligible:
            continue
        if remaining <= 0.0:
            break
        limit = limits.get(key)
        if limit is None:
            continue
        ytd_attr = ytd_by_key[key]
        headroom = max(0.0, limit - getattr(state, ytd_attr))
        contribution = min(remaining, headroom)
        if contribution > 0.0:
            allocation[key] = contribution
            setattr(state, ytd_attr, getattr(state, ytd_attr) + contribution)
            remaining -= contribution

    allocation["standard"] = remaining
    return allocation


# ---------------------------------------------------------------------------
# 5. Rachunek standardowy -- mechanika podatkowa
# ---------------------------------------------------------------------------

def dividend_tax(dividend_gross: float, rate: float = BELKA_TAX_RATE) -> tuple[float, float]:
    """Dywidenda na rachunku standardowym jest opodatkowana natychmiast w
    miesiącu wypłaty (bez odroczenia, w przeciwieństwie do funduszy
    akumulujących zyski wewnętrznie) -- zwraca (podatek, kwota netto do
    reinwestycji).
    """
    tax = dividend_gross * rate
    return tax, dividend_gross - tax


def capital_gains_tax_on_rebalancing(realized_gain: float, rate: float = BELKA_TAX_RATE) -> float:
    """Podatek Belki od zysku zrealizowanego przy rebalancingu na
    rachunku standardowym. Model przeprowadza rebalancing w pierwszej
    kolejności na IKE/IKZE (bezkosztowo podatkowo), więc tę funkcję
    stosuje się wyłącznie do części korekty, która musi sięgnąć po środki
    na rachunku standardowym. Strata (`realized_gain` < 0) nie generuje
    tu podatku -- trafia do `register_loss`.
    """
    if realized_gain <= 0.0:
        return 0.0
    return realized_gain * rate


def tax_drag(gross_return: float, net_return: float) -> float:
    """Tax drag = stopa brutto - stopa netto portfela w danym okresie
    (podrozdz. 3.3/3.6) -- raportowana jako osobna zmienna wynikowa modelu,
    nie tylko efekt uboczny."""
    return gross_return - net_return


# ---------------------------------------------------------------------------
# 6. Kompensacja strat kapitałowych (PIT-38, art. 9 ust. 3 i 6 ustawy o PIT)
# ---------------------------------------------------------------------------

@dataclass
class LossCarryforward:
    """Rejestr strat kapitałowych z rachunku standardowego dostępnych do
    rozliczenia w kolejnych latach. Każdy wpis to (rok_poniesienia_straty,
    pozostała_do_wykorzystania_kwota)."""

    entries: list[tuple[int, float]] = field(default_factory=list)


def register_loss(losses: LossCarryforward, year: int, amount: float) -> None:
    """Rejestruje stratę poniesioną w danym roku podatkowym na rachunku
    standardowym. `amount` musi być nieujemne (wartość bezwzględna straty).
    """
    if amount < 0.0:
        raise ValueError("Kwota straty musi być nieujemna")
    if amount > 0.0:
        losses.entries.append((year, amount))


def apply_loss_relief(
    losses: LossCarryforward,
    current_year: int,
    gain: float,
    full_lump_sum: bool = False,
) -> tuple[float, float]:
    """Rozlicza dodatni wynik roku `current_year` na rachunku standardowym
    względem zarejestrowanych wcześniej strat (art. 9 ust. 3 i 6 ustawy o PIT).

    Strata z danego roku pomniejsza dochód w jednym z pięciu kolejnych lat;
    domyślnie jednorazowe odliczenie nie może przekroczyć 50% pierwotnej
    wysokości danej straty (`full_lump_sum=False`). Podatnik może zamiast
    tego rozliczyć całość straty jednorazowo do ustawowego limitu 5 mln zł
    (`full_lump_sum=True`), z rozłożeniem nadwyżki ponad ten limit na
    pozostałe lata okresu -- w tym uproszczonym modelu, operującym na
    kwotach rzędu dziesiątek/setek tysięcy złotych, próg 5 mln zł w
    praktyce nigdy nie jest wiążący, ale parametr pozostaje jawny dla
    zgodności z przepisem.

    Wpisy starsze niż `LOSS_CARRYFORWARD_YEARS` lat (przedawnione) są
    pomijane i usuwane z rejestru. Zwraca (kwota_odliczona,
    pozostały_dochód_do_opodatkowania).
    """
    if gain <= 0.0:
        return 0.0, max(0.0, gain)

    LUMP_SUM_LIMIT = 5_000_000.0
    active_entries: list[tuple[int, float]] = []
    total_relief = 0.0
    remaining_gain = gain

    for loss_year, remaining_loss in losses.entries:
        age = current_year - loss_year
        expired = age < 0 or age > LOSS_CARRYFORWARD_YEARS or remaining_loss <= 0.0
        if expired:
            continue  # przedawnione (>5 lat) lub już w pełni wykorzystane -- usuwamy z rejestru

        if remaining_gain <= 0.0:
            active_entries.append((loss_year, remaining_loss))
            continue

        if full_lump_sum:
            usable_loss = min(remaining_loss, LUMP_SUM_LIMIT)
        else:
            usable_loss = remaining_loss * LOSS_CARRYFORWARD_MAX_SHARE

        relief_this_entry = min(usable_loss, remaining_gain)
        total_relief += relief_this_entry
        remaining_gain -= relief_this_entry
        leftover_loss = remaining_loss - relief_this_entry
        if leftover_loss > 0.0:
            active_entries.append((loss_year, leftover_loss))

    losses.entries = active_entries
    return total_relief, remaining_gain


# ---------------------------------------------------------------------------
# 7. Harmonogram zwrotu ulgi IKZE
# ---------------------------------------------------------------------------

def ikze_refund_payout_date(contribution_year: int) -> tuple[int, int]:
    """Zwrot podatku z tytułu ulgi IKZE nie jest rejestrowany w miesiącu
    wpłaty, lecz w drugim kwartale roku następującego po roku wpłaty --
    odpowiada to ustawowemu 45-dniowemu terminowi zwrotu nadpłaty dla
    zeznań składanych elektronicznie, liczonemu od końca okresu
    rozliczeniowego (30 kwietnia). Zwraca (rok, kwartał).
    """
    return contribution_year + 1, 2


# ---------------------------------------------------------------------------
# 8. Obligacje detaliczne EDO/COI/ROD -- brak notowanego indeksu
# ---------------------------------------------------------------------------

def retail_bond_rate(
    cpi_period: float,
    margin: float,
    is_first_year: bool = False,
    first_year_nominal_rate: float | None = None,
) -> float:
    """Stopa zwrotu z detalicznych obligacji skarbowych (EDO, COI, ROD)
    nabywanych bezpośrednio -- w przeciwieństwie do WIG czy TBSP.Index nie
    istnieje dla nich notowany indeks rynkowy, więc model odtwarza ją
    formułowo (sekcja 2 spec): w pierwszym roku życia obligacji obowiązuje
    stałe oprocentowanie nominalne z oferty emisji, w kolejnych okresach
    odsetkowych -- suma inflacji GUS za dany okres i stałej marży emisyjnej
    właściwej dla danej serii.
    """
    if is_first_year:
        if first_year_nominal_rate is None:
            raise ValueError(
                "is_first_year=True wymaga podania first_year_nominal_rate"
            )
        return first_year_nominal_rate
    return cpi_period + margin
