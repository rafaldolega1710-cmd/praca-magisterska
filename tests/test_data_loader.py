"""Testy pipeline'u danych (`src/data_loader.py`).

Żadna z tych testów nie wykonuje prawdziwych zapytań sieciowych -- HTTP jest
zamockowane, a parsowanie plików binarnych (xls) testowane na małym fixture
wygenerowanym w locie. To celowe: testy muszą przechodzić identycznie u
każdego, bez dostępu do internetu i bez zależności od tego, czy zewnętrzne
API akurat odpowiada.
"""

from unittest.mock import MagicMock, patch

import openpyxl
import pandas as pd
import pytest

from src.data_loader import (
    _parse_damodaran_xls,
    _parse_price_series_to_monthly_returns,
    annualize_to_monthly,
    fetch_gus_series,
    fetch_nbp_usdpln_monthly,
)


class TestAnnualizeToMonthly:
    def test_zero_annual_return_is_zero_monthly(self):
        assert annualize_to_monthly(0.0) == pytest.approx(0.0)

    def test_known_compounding_value(self):
        # (1.01)**12 - 1 ~= 0.126825 -- zaokrąglona roczna stopa odtwarzająca
        # dokładnie 1% miesięcznie po złożeniu
        annual = 1.01**12 - 1
        assert annualize_to_monthly(annual) == pytest.approx(0.01)

    def test_negative_annual_return(self):
        # spadek o 50% w skali roku -> ujemna stopa miesięczna
        result = annualize_to_monthly(-0.5)
        assert result < 0.0
        assert (1 + result) ** 12 == pytest.approx(0.5)


class TestParseDamodaranXls:
    def _make_fixture(self, tmp_path):
        """Buduje minimalny plik xls odwzorowujący zweryfikowany układ
        arkusza 'Returns by year': 19 wierszy nagłówkowych/notatek, nagłówek
        kolumn w wierszu 20 (1-indeksowanym), potem dane roczne."""
        path = tmp_path / "histretSP_fixture.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Returns by year"
        for _ in range(19):  # wiersze 1..19: notatki/metadane, jak w realnym pliku
            ws.append([None])
        ws.append(
            [
                "Year",
                "S&P 500 (includes dividends)",
                "US Small cap (bottom decile)",
                "3-month T.Bill",
                "US T. Bond (10-year)",
            ]
        )
        ws.append([2020, 0.1840, 0.20, 0.0054, 0.1133])
        ws.append([2021, 0.2871, 0.25, 0.0005, -0.0404])
        ws.append([2022, -0.1811, -0.20, 0.0201, -0.1259])
        wb.save(path)
        return path

    def test_parses_expected_columns_and_index(self, tmp_path):
        path = self._make_fixture(tmp_path)
        df = _parse_damodaran_xls(path)
        assert list(df.index) == [2020, 2021, 2022]
        assert df.loc[2021, "sp500_annual_return"] == pytest.approx(0.2871)
        assert df.loc[2022, "ust10y_annual_return"] == pytest.approx(-0.1259)


class TestFetchNbpUsdplnMonthly:
    def test_rejects_start_year_before_api_range(self):
        with pytest.raises(ValueError, match="2002"):
            fetch_nbp_usdpln_monthly(start_year=1995)

    def test_resamples_daily_rates_to_monthly_last(self, tmp_path):
        cache_path = tmp_path / "nbp_usdpln.csv"

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "rates": [
                {"effectiveDate": "2002-01-10", "mid": 4.00},
                {"effectiveDate": "2002-01-31", "mid": 4.10},
                {"effectiveDate": "2002-02-15", "mid": 4.20},
                {"effectiveDate": "2002-02-28", "mid": 4.25},
            ]
        }

        with patch("src.data_loader.requests.get", return_value=mock_response):
            result = fetch_nbp_usdpln_monthly(
                start_year=2002, end_year=2002, cache_path=cache_path
            )

        assert result.loc[pd.Period("2002-01", freq="M"), "usd_pln"] == pytest.approx(4.10)
        assert result.loc[pd.Period("2002-02", freq="M"), "usd_pln"] == pytest.approx(4.25)

    def test_current_year_range_capped_at_today_not_dec_31(self, tmp_path):
        # regresja: zapytanie o pelny rok biezacy do 31 grudnia zwraca z NBP
        # API blad 400 "Invalid date range" dla dni, ktore jeszcze nie
        # nastapily -- zakres musi byc ucinany do dzisiejszej daty.
        cache_path = tmp_path / "nbp_usdpln.csv"
        current_year = pd.Timestamp.today().year

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"rates": []}

        with patch("src.data_loader.requests.get", return_value=mock_response) as mock_get:
            fetch_nbp_usdpln_monthly(
                start_year=current_year, end_year=current_year, cache_path=cache_path
            )

        called_url = mock_get.call_args[0][0]
        assert f"{current_year}-12-31" not in called_url

    def test_uses_cache_without_hitting_network(self, tmp_path):
        cache_path = tmp_path / "nbp_usdpln.csv"
        cache_path.write_text("date,usd_pln\n2002-01-31,4.10\n2002-02-28,4.25\n")

        with patch("src.data_loader.requests.get") as mock_get:
            result = fetch_nbp_usdpln_monthly(
                start_year=2002, end_year=2002, cache_path=cache_path
            )
            mock_get.assert_not_called()

        assert result.loc[pd.Period("2002-01", freq="M"), "usd_pln"] == pytest.approx(4.10)


class TestFetchGusSeries:
    def test_parses_gus_bdl_response(self, tmp_path):
        cache_path = tmp_path / "gus_test.csv"
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "results": [
                {
                    "id": "000000000000",
                    "name": "POLSKA",
                    "values": [
                        {"year": "2022", "val": 114.4, "attrId": 1},
                        {"year": "2023", "val": 111.4, "attrId": 1},
                    ],
                }
            ]
        }

        with patch("src.data_loader.requests.get", return_value=mock_response):
            df = fetch_gus_series(217230, cache_path)

        assert df.loc[2022, "value"] == pytest.approx(114.4)
        assert df.loc[2023, "value"] == pytest.approx(111.4)
        assert cache_path.exists()  # wynik zapisany do cache

    def test_second_call_reads_cache_not_network(self, tmp_path):
        cache_path = tmp_path / "gus_test.csv"
        cache_path.write_text("year,value\n2022,114.4\n2023,111.4\n")

        with patch("src.data_loader.requests.get") as mock_get:
            df = fetch_gus_series(217230, cache_path)
            mock_get.assert_not_called()

        assert df.loc[2023, "value"] == pytest.approx(111.4)


class TestParsePriceSeriesToMonthlyReturns:
    def test_missing_file_raises_with_instructions(self, tmp_path):
        missing = tmp_path / "wig.csv"
        with pytest.raises(FileNotFoundError, match="README"):
            _parse_price_series_to_monthly_returns(missing, "wig_monthly_return")

    def test_parses_stooq_polish_format(self, tmp_path):
        path = tmp_path / "wig.csv"
        path.write_text(
            "Data;Otwarcie;Najwyzszy;Najnizszy;Zamkniecie;Wolumen\n"
            "20230131;1000;1050;990;1000;123456\n"
            "20230228;1000;1100;995;1100;123456\n"
            "20230331;1100;1150;1080;1210;123456\n",
            encoding="utf-8",
        )
        result = _parse_price_series_to_monthly_returns(path, "wig_monthly_return")

        assert result.loc[pd.Period("2023-02", freq="M"), "wig_monthly_return"] == pytest.approx(0.10)
        assert result.loc[pd.Period("2023-03", freq="M"), "wig_monthly_return"] == pytest.approx(0.10)
        # pierwszy miesiąc nie ma poprzedniej wartości do policzenia zwrotu
        assert pd.Period("2023-01", freq="M") not in result.index

    def test_parses_english_format(self, tmp_path):
        path = tmp_path / "tbsp.csv"
        path.write_text(
            "Date,Open,High,Low,Close,Volume\n"
            "2023-01-31,100,105,99,100,1000\n"
            "2023-02-28,100,110,99.5,110,1000\n",
            encoding="utf-8",
        )
        result = _parse_price_series_to_monthly_returns(path, "tbsp_monthly_return")
        assert result.loc[pd.Period("2023-02", freq="M"), "tbsp_monthly_return"] == pytest.approx(0.10)

    def test_unrecognized_columns_raise_value_error(self, tmp_path):
        path = tmp_path / "bad.csv"
        path.write_text("foo,bar\n1,2\n", encoding="utf-8")
        with pytest.raises(ValueError):
            _parse_price_series_to_monthly_returns(path, "x")
