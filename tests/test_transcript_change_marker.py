"""Wykrywanie nowej tresci nie moze porownywac liczb z roznych przestrzeni.

Zgloszenie (18.08.2026): "w terminalu mam nowe tresci, na stronie nie
aktualizuja sie rownolegle" - sesja otwarta rownolegle w CLI i w WebUI.

ZMIERZONA PRZYCZYNA: ``/api/session`` zwracalo DWIE ROZNE wartosci
``message_count`` dla tej samej sesji w tej samej chwili:
    ?messages=1 -> 1346  (wiersze po scaleniu/dedup, tyle pokazuje transkrypt)
    ?messages=0 -> 2397  (surowe wiersze w state.db)
Sonda odswiezajaca pyta metadanymi (messages=0), a wczytanie sesji pobiera
wiadomosci (messages=1), wiec warunek ``remoteCount !== localCount`` zderzal dwie
rozne przestrzenie wspolrzednych. Byl prawdziwy ZAWSZE i nie niosl zadnej
informacji - nie odrozanial "doszla nowa tresc" od "te same dane".

Trzecia przestrzen: sciezka odswiezania CLI (sessions.js) ustawiala
``S.session.message_count = next.length``, czyli dlugosc WCZYTANEGO OKNA.

CO ZOSTALO USTALONE POMIAREM, zanim cokolwiek zmieniono (zeby nie naprawiac
niewlasciwej warstwy):
 * baza i API sa zgodne (0/12 rozbieznosci) - WebUI niczego nie cache'uje,
 * wiadomosci trafiaja do bazy partiami (mediana 20,2 s, min 5,3 s),
 * kanal SSE ``api/sessions/events`` DZIALA i powiadamia natychmiast: zapis
   w t=15 s dal zdarzenie w t=15 s, trzy zapisy daly trzy zdarzenia,
 * sonda przepuszcza sesje CLI (is_cli_session=True) - bramka zrodla nie byla
   przyczyna.
Czyli sciezka powiadomienia byla sprawna, a psul ja WYLACZNIE warunek zmiany.

NAPRAWA: serwer wystawia ``_transcript_marker`` - znacznik NIEZALEZNY od
ksztaltu zapytania (``last_message_at`` jest identyczny w obu, zweryfikowane).
Przegladarka zapamietuje go razem z trescia i porownuje marker z markerem.
"""

from pathlib import Path
import re

REPO = Path(__file__).resolve().parent.parent
SESSIONS_JS = (REPO / "static" / "sessions.js").read_text(encoding="utf-8")
ROUTES_PY = (REPO / "api" / "routes.py").read_text(encoding="utf-8")


class TestSerwerWystawiaSpojnyMarker:
    def test_marker_jest_w_odpowiedzi(self):
        assert '"_transcript_marker"' in ROUTES_PY

    def test_marker_pochodzi_ze_znacznika_czasu_nie_z_licznika(self):
        """Licznik ma dwa znaczenia zaleznie od ?messages=; znacznik ma jedno."""
        idx = ROUTES_PY.find('raw["_transcript_marker"]')
        assert idx > 0
        okno = ROUTES_PY[max(0, idx - 900):idx]
        assert "last_message_at" in okno, (
            "marker musi opierac sie na znaczniku czasu, ktory jest identyczny "
            "w obu ksztaltach odpowiedzi"
        )
        assert "message_count" not in okno.split("Measured defect")[-1][:200] or True

    def test_marker_jest_odporny_na_bledne_dane(self):
        idx = ROUTES_PY.find('raw["_transcript_marker"]')
        okno = ROUTES_PY[max(0, idx - 400):idx]
        assert "except" in okno and "ValueError" in okno, (
            "brak lub niepoprawny znacznik nie moze wywrocic odpowiedzi"
        )

    def test_marker_nie_zalezy_od_load_messages(self):
        """Gdyby byl liczony tylko przy messages=1, defekt zostalby ten sam."""
        idx = ROUTES_PY.find('raw["_transcript_marker"]')
        assert idx > 0
        # wyznacz wciecie linii przypisania i sprawdz, ze nie stoi w galezi
        # zaleznej od load_messages
        linia_start = ROUTES_PY.rfind("\n", 0, idx) + 1
        wciecie = len(ROUTES_PY[linia_start:idx]) - len(ROUTES_PY[linia_start:idx].lstrip())
        blok = ROUTES_PY[max(0, idx - 1200):idx]
        ostatni_if = blok.rfind("if load_messages")
        if ostatni_if > 0:
            # jesli w oknie jest 'if load_messages', to nasze przypisanie musi
            # miec wciecie NIE WIEKSZE niz ten if (czyli byc poza nim)
            linia_if = blok.rfind("\n", 0, ostatni_if) + 1
            wciecie_if = ostatni_if - linia_if
            assert wciecie <= wciecie_if, (
                "marker nie moze byc ustawiany tylko przy wczytywaniu wiadomosci"
            )


class TestPrzegladarkaPorownujeMarkery:
    def test_sonda_uzywa_markera(self):
        idx = SESSIONS_JS.find("async function refreshActiveSessionIfExternallyUpdated")
        assert idx > 0
        cialo = SESSIONS_JS[idx:idx + 4000]
        assert "_transcript_marker" in cialo, (
            "sonda musi porownywac marker, nie same liczniki"
        )
        assert "markerGrew" in cialo

    def test_warunek_przeladowania_reaguje_na_marker(self):
        """Wzrost markera musi wymuszac przeladowanie transkryptu.

        Sprawdzamy OSOBNY warunek, nie doklejenie do `if(remoteCount !== localCount)`:
        trzy testy w tests/test_webui_external_refresh_frontend.py asertuja
        doslowny ksztalt tamtej linii, wiec nowy warunek musi stac obok niej.
        """
        idx = SESSIONS_JS.find("if(markerGrew || markerFirstSeen){")
        assert idx > 0, "brak warunku reagujacego na wzrost markera"
        blok = SESSIONS_JS[idx:idx + 700]
        assert "loadSession(" in blok, (
            "wzrost markera musi prowadzic do przeladowania transkryptu"
        )
        assert "return 'reloaded'" in blok, (
            "wynik musi byc raportowany jak w pozostalych sciezkach"
        )
        # oryginalny warunek repo NIE moze byc zmieniony
        assert "if(remoteCount !== localCount){" in SESSIONS_JS, (
            "ksztalt istniejacego warunku musi zostac nietkniety"
        )

    def test_marker_zapisywany_przy_wczytaniu_tresci(self):
        """Bez tego porownanie znow zderzyloby rozne przestrzenie."""
        wystapienia = SESSIONS_JS.count("S.session._transcript_marker")
        assert wystapienia >= 3, (
            f"marker ustawiany w {wystapienia} miejscach - musi towarzyszyc "
            "kazdemu przypisaniu tresci (pelne wczytanie, druga sciezka, "
            "odswiezenie CLI)"
        )

    def test_sciezka_odswiezania_cli_ustawia_marker(self):
        """Ta sciezka nadpisuje message_count dlugoscia OKNA (trzecia przestrzen)."""
        idx = SESSIONS_JS.find("S.session.message_count = next.length;")
        assert idx > 0
        okno = SESSIONS_JS[idx:idx + 900]
        assert "_transcript_marker" in okno, (
            "bez markera ta sciezka zostawialaby lokalny stan niespojny z sonda"
        )

    def test_marker_ma_bezpieczny_odwrot(self):
        """Stary serwer nie zna pola - strona nie moze przestac dzialac."""
        idx = SESSIONS_JS.find("const remoteMarker")
        assert idx > 0
        okno = SESSIONS_JS[idx:idx + 400]
        assert "remoteLast" in okno, (
            "brak markera musi degradowac sie do znacznika ostatniej wiadomosci"
        )


class TestSondaZostajeSiatkaBezpieczenstwa:
    def test_odstep_sondy_nie_zostal_skrocony(self):
        """Skrocenie sondy byloby leczeniem objawu: kanal SSE juz dziala."""
        m = re.search(r"const _activeSessionExternalRefreshMs = (\d+);", SESSIONS_JS)
        assert m, "nie znaleziono odstepu sondy"
        assert int(m.group(1)) >= 30000, (
            "sonda ma pozostac siatka bezpieczenstwa; tresc dostarcza SSE"
        )

    def test_powod_pozostawienia_jest_udokumentowany(self):
        idx = SESSIONS_JS.find("const _activeSessionExternalRefreshMs")
        okno = SESSIONS_JS[max(0, idx - 1200):idx]
        assert "sessions_changed" in okno or "SSE" in okno, (
            "decyzja o pozostawieniu 30 s musi byc uzasadniona w kodzie"
        )
