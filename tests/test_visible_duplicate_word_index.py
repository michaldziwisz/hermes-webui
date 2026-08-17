"""Indeks slow zawezajacy kandydatow deduplikacji nie moze zmieniac wyniku.

``_matching_visible_duplicate`` decyduje, czy wiersz z state.db jest powtorzeniem
tego, co WebUI juz pokazuje. Skanowal wszystkie klucze tej samej roli, co jest
kosztem kwadratowym: profilowanie realnego zapisu rozmowy (14 779 wiadomosci)
pokazalo 5,67 mln przejrzanych kandydatow i 97,5% czasu zuzyte na dowodzenie, ze
duplikatu NIE MA (1327 sond, 905 tys. kandydatow, 2,2 s).

Indeks slow zawęza te liste. Jest wylacznie FILTREM - kazdy kandydat, ktorego
zwroci, przechodzi te same porownania co wczesniej. Dlatego kontrakt brzmi:
wynik MUSI byc identyczny, a jedyna dozwolona zmiana to mniej iteracji.

Testy pilnuja obu wlasnosci naraz, bo kazda osobno da sie spelnic bledna
implementacja: indeks zwracajacy wszystko jest poprawny ale bezuzyteczny, a
indeks zwracajacy nic jest szybki i psuje deduplikacje.

Dwa bledy z budowy tej optymalizacji, ktore te testy zapinaja na stale:
1. Zapytanie tylko o slowa TRESCI SPRAWDZANEJ gubilo dopasowania, gdzie krotszy
   byl KANDYDAT ("1", "Start" wobec dlugiego zapytania) - zawieranie jest
   testowane w obie strony, wiec indeks tez musi byc dwukierunkowy.
2. Obcinanie zbioru slow (pierwsza wersja brala 400 pierwszych) gubilo
   dopasowanie, w ktorym slowo-reprezentant kandydata lezalo dalej w tekscie.
"""

from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import api.models as models


def _visible_key(role, content, sidecar=None):
    """Klucz w kształcie, jakiego uzywa _matching_visible_duplicate."""
    return (role, content, "", sidecar)


def _lookup(keys):
    return models._build_visible_duplicate_lookup(set(keys))


def _pelny_skan(visible_key, keys):
    """Wynik z indeksem WYLACZONYM - wzorzec odniesienia."""
    stary = models._WORD_INDEX_MIN_CANDIDATES
    models._WORD_INDEX_MIN_CANDIDATES = 10 ** 9
    try:
        return models._matching_visible_duplicate(visible_key, set(keys), _lookup(keys))
    finally:
        models._WORD_INDEX_MIN_CANDIDATES = stary


def _z_indeksem(visible_key, keys):
    """Wynik z indeksem WLACZONYM od pierwszego kandydata."""
    stary = models._WORD_INDEX_MIN_CANDIDATES
    models._WORD_INDEX_MIN_CANDIDATES = 1
    try:
        return models._matching_visible_duplicate(visible_key, set(keys), _lookup(keys))
    finally:
        models._WORD_INDEX_MIN_CANDIDATES = stary


def _zawezone_i_wynik(visible_key, keys):
    """(wynik, ile kandydatow realnie przejrzano) przy WLACZONYM indeksie.

    Liczba przejrzanych kandydatow jest tu istotna, bo bez niej test przechodzi
    takze na kodzie BEZ indeksu - a wtedy niczego nie pilnuje. Zliczamy odczyty
    listy kandydatow, podstawiajac liste, ktora raportuje kazda iteracje.
    """
    stary = models._WORD_INDEX_MIN_CANDIDATES
    models._WORD_INDEX_MIN_CANDIDATES = 1
    licznik = {"n": 0}
    oryg_narrow = models._narrowed_visible_duplicate_candidates

    def licz(index, content):
        wynik = oryg_narrow(index, content)
        licznik["n"] += len(wynik)
        return wynik

    models._narrowed_visible_duplicate_candidates = licz
    try:
        wynik = models._matching_visible_duplicate(visible_key, set(keys), _lookup(keys))
    finally:
        models._narrowed_visible_duplicate_candidates = oryg_narrow
        models._WORD_INDEX_MIN_CANDIDATES = stary
    return wynik, licznik["n"]


def _sprawdz_zgodnosc(visible_key, keys, *, wymagaj_zawezenia=True):
    """Wynik identyczny jak pelny skan ORAZ indeks faktycznie zawezil liste.

    Dwa warunki naraz, bo kazdy osobno spelnia bledna implementacja: indeks
    zwracajacy wszystko jest zgodny lecz bezuzyteczny, a zwracajacy nic jest
    szybki i psuje deduplikacje.
    """
    wzorzec = _pelny_skan(visible_key, keys)
    wynik, przejrzanych = _zawezone_i_wynik(visible_key, keys)
    assert wynik == wzorzec, (
        f"indeks zmienil wynik: {wynik!r} zamiast {wzorzec!r}"
    )
    if wymagaj_zawezenia:
        assert przejrzanych > 0, (
            "indeks nie zostal uzyty - test nie sprawdza tego, co mial sprawdzac"
        )
        assert przejrzanych < len(keys), (
            f"indeks przejrzal {przejrzanych} z {len(keys)} kandydatow - brak zawezenia"
        )
    return wzorzec


class TestIndeksNieZmieniaWyniku:
    """Kazdy kształt dopasowania musi wyjsc tak samo z indeksem i bez niego."""

    def test_dlugie_zapytanie_i_krotki_kandydat_nadal_sie_dopasowuja(self):
        """Blad nr 1: zawieranie dziala TEZ gdy kandydat jest krotszy.

        Pierwsza wersja indeksu pytala tylko o slowa sprawdzanej tresci i brala
        kandydatow, ktorzy je maja. Kandydat "Start" nie zawiera zadnego rzadkiego
        slowa dlugiego zapytania, wiec wypadal z listy - i dopasowanie ginelo.
        Na realnych danych tak przepadlo 37 z 187 dopasowan.
        """
        krotki = "Start"
        dlugi = ("Start" + " zainstalowalem nowy nadzorca usługi oraz "
                 "poprawilem dostepnosc zakladek w panelu ustawien " * 3)
        keys = [_visible_key("user", krotki)]
        keys += [_visible_key("user", f"zupelnie inna tresc numer {i} "
                                      f"z wieloma slowami do wypelnienia indeksu")
                 for i in range(40)]
        probe = _visible_key("user", dlugi)

        assert _pelny_skan(probe, keys) is not None, "wzorzec: pelny skan dopasowuje"
        _sprawdz_zgodnosc(probe, keys)

    def test_slowo_kandydata_daleko_w_tresci_nadal_sie_dopasowuje(self):
        """Blad nr 2: obcinanie zbioru slow gubi dopasowania.

        Wersja z limitem 400 slow zgubila pare, w ktorej slowo-reprezentant
        kandydata (122 znaki) wystepowalo w zapytaniu (9653 znaki) dopiero za
        limitem. Tokenizacja musi byc pelna dla wszystkiego, co wchodzi do indeksu.
        """
        wypelniacz = " ".join(f"wyraz{i}" for i in range(1200))
        kandydat = ("ta koncowka jest wystarczajaco dluga, zeby wejsc do indeksu "
                    "zamiast na liste zawsze sprawdzanych kluczy")
        keys = [_visible_key("assistant", kandydat)]
        keys += [_visible_key("assistant", f"inny kandydat {i} " + "tekst " * 20)
                 for i in range(40)]
        probe = _visible_key("assistant", wypelniacz + " " + kandydat)

        assert _pelny_skan(probe, keys) is not None
        _sprawdz_zgodnosc(probe, keys)

    def test_zawieranie_w_srodku_tekstu_nadal_sie_dopasowuje(self):
        """Dopasowania nie sa tylko prefiksowe.

        Na realnych sesjach 20 z 187 dopasowan mialo krotszy tekst w SRODKU
        dluzszego, dlatego indeks prefiksowy (tanszy) zostal odrzucony.
        """
        srodek = ("fragment ktory wystepuje w srodku dluzszej wypowiedzi "
                  "i ma dosc slow, aby trafic do indeksu")
        keys = [_visible_key("assistant", srodek)]
        keys += [_visible_key("assistant", f"wypelnienie {i} " + "slowo " * 25)
                 for i in range(40)]
        probe = _visible_key("assistant", "poczatek wypowiedzi " + srodek + " i zakonczenie")

        assert _pelny_skan(probe, keys) is not None
        _sprawdz_zgodnosc(probe, keys)

    def test_krotkie_tresci_lamiace_granice_slow_nadal_sie_dopasowuja(self):
        """Zawieranie SUROWE nie respektuje granic slow.

        "abc" zawiera sie w "xabcy", ale zbiory slow sa rozlaczne - warunek
        konieczny indeksu tego nie obejmuje. Dlatego krotkie teksty musza zostac
        na liscie zawsze sprawdzanych, a nie w indeksie.
        """
        keys = [_visible_key("user", "abc")]
        keys += [_visible_key("user", f"wypelnienie numer {i} z paroma slowami")
                 for i in range(40)]
        probe = _visible_key("user", "xabcy")

        assert _pelny_skan(probe, keys) is not None, "wzorzec: pelny skan to lapie"
        wynik, przejrzanych = _zawezone_i_wynik(probe, keys)
        assert wynik == _pelny_skan(probe, keys), (
            "krotkie tresci musza byc sprawdzane zawsze, nie przez indeks slow"
        )
        assert przejrzanych > 0, "indeks nie zostal uzyty - test nic nie pilnuje"

    def test_tresc_bez_slow_nie_gubi_dopasowania(self):
        """Tresc z samych znakow niealfanumerycznych nie da sie zaindeksowac."""
        keys = [_visible_key("assistant", "!!! ???")]
        keys += [_visible_key("assistant", f"kandydat {i} " + "tekst " * 20)
                 for i in range(40)]
        probe = _visible_key("assistant", ">>> !!! ??? <<<")

        wynik, przejrzanych = _zawezone_i_wynik(probe, keys)
        assert wynik == _pelny_skan(probe, keys)
        assert przejrzanych > 0, "indeks nie zostal uzyty - test nic nie pilnuje"

    def test_brak_duplikatu_zwraca_none_w_obu_trybach(self):
        """Najczestszy przypadek (97,5% kosztu) musi dawac ten sam wynik."""
        keys = [_visible_key("tool", f"wynik narzedzia numer {i} " + "dane " * 30)
                for i in range(60)]
        probe = _visible_key("tool", "cos zupelnie niepowiazanego z niczym powyzej")

        assert _pelny_skan(probe, keys) is None
        wynik, przejrzanych = _zawezone_i_wynik(probe, keys)
        assert wynik is None
        assert przejrzanych < len(keys), (
            f"przejrzano {przejrzanych} z {len(keys)} - indeks nie zawezil "
            "najczestszego przypadku (97,5% kosztu)"
        )

    def test_inna_rola_nie_jest_dopasowywana(self):
        """Indeks jest per rola - nie moze przeciekac miedzy rolami."""
        tresc = "identyczna tresc w dwoch roznych rolach " + "slowo " * 20
        keys = [_visible_key("assistant", tresc)]
        keys += [_visible_key("assistant", f"inne {i} " + "tekst " * 20) for i in range(40)]
        probe = _visible_key("user", tresc)

        _sprawdz_zgodnosc(probe, keys, wymagaj_zawezenia=False)

    def test_rozny_sidecar_nie_jest_dopasowywany(self):
        """Warunek na sidecar z petli obowiazuje tez po zawezeniu."""
        tresc = "ta sama tresc ale inny sidecar " + "slowo " * 20
        keys = [_visible_key("assistant", tresc, sidecar="A")]
        keys += [_visible_key("assistant", f"inne {i} " + "tekst " * 20) for i in range(40)]
        probe = _visible_key("assistant", tresc, sidecar="B")

        _sprawdz_zgodnosc(probe, keys)


class TestIndeksFaktycznieZawez:
    """Bez tego indeks moglby byc 'poprawny' przez zwracanie wszystkiego."""

    def test_indeks_odsiewa_wieksza_czesc_kandydatow(self):
        kandydaci = [_visible_key("tool", f"unikalny wpis numer {i} " +
                                          f"charakterystyczne slowo{i} " + "dane " * 25)
                     for i in range(400)]
        index = models._visible_duplicate_word_index(kandydaci)
        zawezeni = models._narrowed_visible_duplicate_candidates(
            index, "zupelnie inna tresc bez wspolnych slow z kandydatami")

        assert len(zawezeni) < len(kandydaci) / 5, (
            f"indeks zwrocil {len(zawezeni)} z {len(kandydaci)} kandydatow - "
            "za slabe zawezenie, zysk wydajnosciowy by zniknal"
        )

    def test_krotkie_i_dlugie_tresci_sa_zawsze_sprawdzane(self):
        krotka = _visible_key("tool", "abc")
        dluga = _visible_key("tool", "x" * (models._WORD_INDEX_MAX_CHARS + 10))
        zwykla = _visible_key("tool", "zwykla tresc kandydata " + "slowo " * 30)
        index = models._visible_duplicate_word_index([krotka, dluga, zwykla])

        assert krotka in index["always"], "krotkie tresci musza byc zawsze sprawdzane"
        assert dluga in index["always"], "bardzo dlugie tresci nie wchodza do indeksu"
        assert zwykla not in index["always"], "zwykla tresc powinna trafic do indeksu"

    def test_zapytanie_bez_slow_dostaje_wszystkich_kandydatow(self):
        """Fail open: nie umiemy zawezic, wiec oddajemy wszystko."""
        kandydaci = [_visible_key("tool", f"kandydat {i} " + "slowo " * 30)
                     for i in range(30)]
        index = models._visible_duplicate_word_index(kandydaci)
        zawezeni = models._narrowed_visible_duplicate_candidates(index, "!!! ???")

        assert len(zawezeni) >= len(kandydaci), (
            "zapytanie bez slow nie moze zawezac listy kandydatow"
        )


class TestProgWlaczaniaIndeksu:
    def test_male_role_zostaja_na_starej_sciezce(self):
        """Ponizej progu indeks sie nie oplaca i nie ma go w lookup."""
        keys = [_visible_key("user", f"tresc {i} " + "slowo " * 20)
                for i in range(models._WORD_INDEX_MIN_CANDIDATES - 1)]
        lookup = _lookup(keys)
        models._matching_visible_duplicate(
            _visible_key("user", "cos nowego bez duplikatu"), set(keys), lookup)

        assert "word_indexes" not in lookup, (
            "przy malej liczbie kandydatow indeks nie powinien byc budowany"
        )

    def test_duze_role_buduja_indeks_raz(self):
        """Indeks ma byc budowany raz na role, nie na kazde zapytanie."""
        keys = [_visible_key("tool", f"tresc {i} " + f"slowo{i} " * 20)
                for i in range(models._WORD_INDEX_MIN_CANDIDATES + 50)]
        lookup = _lookup(keys)
        wolania = {"n": 0}
        oryg = models._visible_duplicate_word_index

        def licz(kandydaci):
            wolania["n"] += 1
            return oryg(kandydaci)

        models._visible_duplicate_word_index = licz
        try:
            for i in range(5):
                models._matching_visible_duplicate(
                    _visible_key("tool", f"nowa tresc {i} bez duplikatu"),
                    set(keys), lookup)
        finally:
            models._visible_duplicate_word_index = oryg

        assert wolania["n"] == 1, f"indeks zbudowany {wolania['n']} razy, powinien raz"


class TestStalejKonfiguracji:
    def test_progi_maja_sensowne_wartosci(self):
        assert models._WORD_INDEX_MIN_CHARS >= 8, (
            "zbyt niski prog dlugosci wpuscilby do indeksu teksty, dla ktorych "
            "tokenizacja nie odwzorowuje zawierania surowego"
        )
        assert models._WORD_INDEX_MAX_CHARS >= 1000
        assert models._WORD_INDEX_MIN_CANDIDATES >= 50, (
            "za niski prog wlaczania spowalnia male rozmowy narzutem budowy indeksu"
        )
        assert isinstance(models._WORD_INDEX_TOKEN.pattern, str)
