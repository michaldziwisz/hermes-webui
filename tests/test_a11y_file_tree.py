"""Drzewo plikow musi mowic, czym jest kazdy wiersz i jak sie nim poslugiwac.

Zgloszenie (18.08.2026): w zakladce Files czytnik czytal
    "▸  .cache  ×      ▸  .cloak-venv  ×      ▸  .cloakbrowser  ×"
Slowa uzytkownika: "i badz tu madry co to jest, o co chodzi i jak z tym sie
obchodzic". Trzy rzeczy naraz byly nie do odczytania: czym jest wiersz, w jakim
jest stanie i co robi przycisk obok.

ZMIERZONE BRAKI (wszystkie 7 jednoczesnie, krok142):
  wiersz ma role .................. BRAK  -> <div>, czytnik nie widzi kontrolki
  wiersz ma tabindex .............. BRAK  -> nie da sie dojsc klawiatura
  strzalka ma aria-expanded ....... BRAK  -> brak "zwiniete/rozwiniete"
  strzalka ma nazwe ............... BRAK  -> czytany sam znak ▸
  przycisk usuwania ma aria-label . BRAK  -> czytany znak × albo nic
  wiersz ma aria-level ............ BRAK  -> nieznany poziom zagniezdzenia
  kontener ma role=tree ........... BRAK  -> zbior luznych elementow

DECYZJE PROJEKTOWE, ktore te testy pilnuja:
 * role=tree, nie lista przyciskow - katalogi sie ZWIJAJA i wiersze sa
   ZAGNIEZDZONE; tylko drzewo ma slownictwo na oba fakty (aria-expanded,
   aria-level) i gotowa nawigacje w czytnikach,
 * PLIK nie dostaje aria-expanded - dla liscia ten atrybut klamie, sugerujac
   ze cos da sie rozwinac,
 * roving tabindex (jeden wiersz w kolejnosci Tab) - drzewo z setka plikow nie
   moze wymagac setki nacisniec Tab, zeby je przeskoczyc,
 * nazwa przycisku usuwania zawiera NAZWE WPISU - przy 20 wierszach samo "usun"
   nie pozwala odroznic, ktory przycisk co usunie,
 * strzalka i ikona sa aria-hidden - stan i rodzaj niesie wiersz, wiec inaczej
   czytnik powtarzalby znak ▸ przed kazda nazwa.
"""

from pathlib import Path
import json
import shutil
import subprocess

import pytest

REPO = Path(__file__).resolve().parent.parent
A11Y_JS = (REPO / "static" / "a11y-helpers.js").read_text(encoding="utf-8")
UI_JS = (REPO / "static" / "ui.js").read_text(encoding="utf-8")
I18N_JS = (REPO / "static" / "i18n.js").read_text(encoding="utf-8")
NODE = shutil.which("node")

HARNESS = Path(__file__).parent / "_harness_drzewo.js"


class TestHelperyIstniejaISaWpiete:
    def test_helpery_drzewa_istnieja(self):
        assert "function a11yTreeRow(" in A11Y_JS
        assert "function a11yTree(" in A11Y_JS

    def test_helpery_sa_eksportowane(self):
        assert "window.a11yTree = a11yTree" in A11Y_JS
        assert "window.a11yTreeRow = a11yTreeRow" in A11Y_JS

    def test_wiersz_drzewa_uzywa_helpera(self):
        assert "a11yTreeRow(el, {" in UI_JS, (
            "wiersze drzewa plikow musza przechodzic przez helper"
        )

    def test_kontener_drzewa_uzywa_helpera(self):
        idx = UI_JS.find("_renderTreeItems(box, visibleEntries, 0);")
        assert idx > 0
        assert "a11yTree(box" in UI_JS[idx:idx + 900], (
            "kontener musi dostac role=tree po kazdym przerysowaniu"
        )

    def test_wpiecie_jest_po_kazdym_przerysowaniu(self):
        """innerHTML='' niszczy wiersze, wiec kontrakt trzeba odtwarzac."""
        idx = UI_JS.find("function renderFileTree(")
        assert idx > 0
        cialo = UI_JS[idx:idx + 3000]
        assert "box.innerHTML=''" in cialo
        assert "a11yTree(box" in cialo


class TestDekoracjeSaUkryte:
    def test_strzalka_jest_ukryta(self):
        idx = UI_JS.find("arrow.className='file-tree-toggle'")
        assert idx > 0
        assert "aria-hidden" in UI_JS[idx:idx + 500], (
            "bez tego czytnik czyta znak ▸ przed kazda nazwa"
        )

    def test_ikona_jest_ukryta(self):
        idx = UI_JS.find("iconEl.className='file-icon'")
        assert idx > 0
        assert "aria-hidden" in UI_JS[idx:idx + 400]


class TestPrzyciskUsuwaniaMowiCoUsuwa:
    def test_ma_nazwe_dostepna(self):
        assert UI_JS.count("del.setAttribute('aria-label'") >= 2, (
            "oba przyciski (plik i katalog) musza miec nazwe"
        )

    def test_nazwa_zawiera_nazwe_wpisu(self):
        assert "_delLabel(item.name)" in UI_JS, (
            "samo 'usun' nie odroznia dwudziestu przyciskow od siebie"
        )

    def test_ma_typ_button(self):
        assert UI_JS.count("del.setAttribute('type','button')") >= 2

    def test_klucz_tlumaczenia_ma_miejsce_na_nazwe(self):
        assert "delete_entry_aria" in I18N_JS
        assert "{name}" in I18N_JS


class TestTlumaczeniaWeWszystkichLocale:
    @pytest.mark.parametrize("klucz", [
        "workspace_tree_aria", "tree_folder_aria", "tree_file_aria",
        "tree_external_link_aria", "delete_entry_aria",
    ])
    def test_klucz_w_15_locale(self, klucz):
        assert I18N_JS.count(f"{klucz}:") == 15, (
            f"{klucz}: {I18N_JS.count(klucz + ':')} wystapien, oczekiwano 15"
        )


# ── pomiar zachowania w node ────────────────────────────────────────────────

@pytest.fixture(scope="module")
def zachowanie(tmp_path_factory):
    if not NODE:
        pytest.skip("node niedostepny")
    if not HARNESS.exists():
        pytest.skip("brak harnessu")
    proc = subprocess.run([NODE, str(HARNESS)], capture_output=True, text=True, timeout=90)
    assert proc.returncode == 0, f"harness padl: {proc.stderr[-2000:]}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


class TestZachowanieWiersza:
    def test_katalog_ma_kontrakt_drzewa(self, zachowanie):
        k = zachowanie["katalogZwiniety"]
        assert k["role"] == "treeitem"
        assert k["expanded"] == "false"
        assert k["level"] == "1"

    def test_katalog_mowi_czym_jest(self, zachowanie):
        """Sedno zgloszenia: zamiast "▸" ma byc "folder .cache"."""
        label = zachowanie["katalogZwiniety"]["label"] or ""
        assert "folder" in label and ".cache" in label, f"label={label}"

    def test_rozwiniety_katalog_to_mowi(self, zachowanie):
        assert zachowanie["katalogRozwiniety"]["expanded"] == "true"

    def test_glebokosc_jest_podana(self, zachowanie):
        assert zachowanie["katalogRozwiniety"]["level"] == "3"

    def test_plik_nie_udaje_ze_da_sie_rozwinac(self, zachowanie):
        assert zachowanie["plik"]["maExpanded"] is False, (
            "aria-expanded na lisciu klamie"
        )

    def test_plik_mowi_ze_to_plik(self, zachowanie):
        assert "file" in (zachowanie["plik"]["label"] or "")


class TestZachowanieKontenera:
    def test_kontener_jest_drzewem(self, zachowanie):
        assert zachowanie["kontener"]["role"] == "tree"

    def test_kontener_ma_nazwe(self, zachowanie):
        assert zachowanie["kontener"]["maNazwe"] is True

    def test_nasluch_nie_mnozy_sie_przy_przerysowaniu(self, zachowanie):
        """renderFileTree wola helper po kazdym rysowaniu - musi byc idempotentny."""
        assert zachowanie["kontener"]["nasluchowPoTrzechWywolaniach"] == 1


class TestNawigacjaKlawiatura:
    def test_strzalki_w_dol_i_gore(self, zachowanie):
        assert zachowanie["nawigacja"]["dolNaDrugi"] is True
        assert zachowanie["nawigacja"]["goraWraca"] is True

    def test_roving_tabindex(self, zachowanie):
        assert zachowanie["nawigacja"]["rovingPrzeszedl"] is True, (
            "tylko jeden wiersz moze byc w kolejnosci Tab"
        )

    def test_home_i_end(self, zachowanie):
        assert zachowanie["nawigacja"]["endNaOstatni"] is True
        assert zachowanie["nawigacja"]["homeNaPierwszy"] is True

    def test_prawo_rozwija_lewo_zwija(self, zachowanie):
        assert zachowanie["nawigacja"]["prawoRozwija"] is True
        assert zachowanie["nawigacja"]["lewoZwija"] is True

    def test_lewo_na_pliku_wychodzi_do_rodzica(self, zachowanie):
        assert zachowanie["nawigacja"]["lewoDoRodzica"] is True

    def test_enter_aktywuje(self, zachowanie):
        assert zachowanie["nawigacja"]["enterAktywuje"] is True


class TestOdpornosc:
    def test_null_nie_wywraca_renderowania(self, zachowanie):
        assert zachowanie["odpornosc"]["nullOk"] is True

    def test_bez_opcji_nadal_treeitem(self, zachowanie):
        assert zachowanie["odpornosc"]["bezOpcjiRole"] == "treeitem"

    def test_nie_zgadujemy_poziomu(self, zachowanie):
        assert zachowanie["odpornosc"]["bezPoziomuMaLevel"] is False
