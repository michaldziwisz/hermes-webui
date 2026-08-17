"""Wiersze listy rozmow musza byc LINKAMI, a nie tekstem bez roli.

Zgloszenie: "te sesje sa zwyklym tekstem, z ktorym uzytkownik nie wie, ze moze
cos zrobic; powinny byc linkami".

Zmierzony stan przed poprawka (Edge + CDP, drzewo dostepnosci na dzialajacej
aplikacji): wiersz to `DIV` bez `role`, bez `tabindex` i bez `href`, w calym
panelu bocznym ZERO wezlow `role=link`, a 40 tabow nie zatrzymalo sie na wierszu
ani raz. Czytnik ekranu nie mial czym ogloscic, ze wiersz cokolwiek robi
(WCAG 4.1.2), a klawiatura nie miala jak go uruchomic (WCAG 2.1.1).

Stan po poprawce: tytul jest `<a href="/session/<id>">`, wiec NVDA raportuje
rola 19 (LINK) + State.LINKED + State.FOCUSABLE z nazwa i adresem, a fokus
dochodzi tabulacja. Dodatkowo dziala to, czego div nie potrafi: Ctrl+klik /
srodkowy przycisk otwieraja rozmowe w nowej karcie, a menu kontekstowe
przegladarki pozwala skopiowac jej adres.

Testy sa zrodlowe (statyczne) — pelny dowod behawioralny wymaga przegladarki
i zywego czytnika, a te przebiegly osobno przy naprawie. Tutaj przypinamy
kontrakt, ktory nie moze cicho zniknac przy nastepnej edycji renderowania.
"""

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SESSIONS_JS = (REPO / "static" / "sessions.js").read_text(encoding="utf-8")
STYLE_CSS = (REPO / "static" / "style.css").read_text(encoding="utf-8")
A11Y_JS = (REPO / "static" / "a11y-helpers.js").read_text(encoding="utf-8")
ROUTES_PY = (REPO / "api" / "routes.py").read_text(encoding="utf-8")


class TestSessionTitleIsARealLink:

    def test_title_element_is_an_anchor_not_a_span(self):
        """Rola musi wynikac z elementu, nie z atrybutu doklejonego obok."""
        assert "const title=document.createElement('a');" in SESSIONS_JS, (
            "Tytul sesji musi byc <a>, zeby czytnik ekranu ogloszil go jako link "
            "(WCAG 4.1.2). Wersja ze <span> nie mowila uzytkownikowi nic."
        )
        assert "const title=document.createElement('span');\n    title.className='session-title';" not in SESSIONS_JS

    def test_title_gets_href_pointing_at_the_session_url(self):
        assert "title.setAttribute('href',_sessionUrlForSid(s.session_id))" in SESSIONS_JS, (
            "Link musi miec href z adresem TEJ rozmowy — inaczej jest atrapa: "
            "otwarcie w nowej karcie i kopiowanie adresu nie zadzialaja."
        )

    def test_session_url_is_actually_served_so_the_link_is_not_a_decoy(self):
        """Adres z href musi byc obslugiwany przez serwer, nie wymyslony."""
        assert 'parsed.path.startswith("/session/")' in ROUTES_PY, (
            "href prowadzi na /session/<id>; jesli serwer przestanie tam "
            "zwracac aplikacje, link stanie sie atrapa prowadzaca w 404."
        )

    def test_active_row_marks_aria_current(self):
        assert "if(isActive) title.setAttribute('aria-current','page');" in SESSIONS_JS, (
            "Biezaca rozmowa byla oznaczona wylacznie klasa CSS 'active'. "
            "Dla czytnika ekranu klasa nie istnieje — potrzebne aria-current."
        )

    def test_modified_click_is_left_to_the_browser(self):
        """Ctrl/Cmd/Shift/Alt/srodkowy przycisk = nowa karta, tego nie przechwytujemy."""
        idx = SESSIONS_JS.find("title.addEventListener('click'")
        assert idx > 0, "brak obslugi klikniecia na linku tytulu"
        blok = SESSIONS_JS[idx:idx + 600]
        assert "e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||e.button===1" in blok, (
            "Klik z modyfikatorem musi trafic do przegladarki, inaczej tracimy "
            "otwieranie rozmowy w nowej karcie — glowny zysk z prawdziwego linku."
        )
        assert "return" in blok

    def test_keyboard_activation_opens_session_in_place(self):
        """Enter z klawiatury (detail===0) otwiera rozmowe bez przeladowania."""
        idx = SESSIONS_JS.find("title.addEventListener('click'")
        blok = SESSIONS_JS[idx:idx + 600]
        assert "e.detail===0" in blok, (
            "Aktywacja z klawiatury musi byc rozpoznana (click detail===0), "
            "zeby otworzyc rozmowe sciezka aplikacji zamiast przeladowac strone."
        )
        assert "_openSidebarSession(s)" in blok


class TestSidebarClickablesHaveRoleAndKeyboard:
    """Ta sama klasa defektu poza wierszem: 7 klikalnych elementow bez roli."""

    def test_shared_helpers_exist(self):
        assert "function a11yAsButton(el, opts)" in A11Y_JS
        assert "function a11yAsLink(el, href, opts)" in A11Y_JS
        assert "window.a11yAsButton = a11yAsButton;" in A11Y_JS
        assert "window.a11yAsLink = a11yAsLink;" in A11Y_JS

    def test_button_helper_handles_enter_and_space(self):
        idx = A11Y_JS.find("function a11yAsButton(el, opts)")
        blok = A11Y_JS[idx:A11Y_JS.find("function a11yAsLink", idx)]
        assert "ev.key !== 'Enter' && ev.key !== ' '" in blok
        assert "ev.preventDefault();" in blok, (
            "Spacja bez preventDefault przewija strone pod uzytkownikiem."
        )
        assert "role', 'button'" in blok
        assert "tabindex', '0'" in blok

    def test_key_handler_is_attached_once_per_element(self):
        """Lista jest przerysowywana czesto — podwojny nasluch = podwojna akcja."""
        assert "dataset.a11yKeyActivated === '1'" in A11Y_JS

    def test_date_group_header_is_a_button_with_expanded_state(self):
        assert "a11yAsButton(hdr,{expanded:!isGroupCollapsed" in SESSIONS_JS, (
            "Naglowek grupy zwija liste, a stan zwiniecia pokazywal tylko "
            "obrocony daszek — czytnik potrzebuje aria-expanded."
        )

    def test_project_filter_chips_expose_pressed_state(self):
        for wywolanie in (
            "a11yAsButton(allChip,{pressed:!_activeProject",
            "a11yAsButton(noneChip,{pressed:_activeProject===NO_PROJECT_FILTER",
            "a11yAsButton(chip,{pressed:p.project_id===_activeProject",
        ):
            assert wywolanie in SESSIONS_JS, (
                f"brak stanu wybrania na chipie filtra: {wywolanie}"
            )

    def test_remaining_sidebar_toggles_are_buttons(self):
        assert "a11yAsButton(pfToggle)" in SESSIONS_JS
        assert "a11yAsButton(toggle,{pressed:_showArchived})" in SESSIONS_JS
        assert "a11yAsButton(more)" in SESSIONS_JS
        assert "a11yAsButton(toggleBtn,{label:t('session_select_mode')})" in SESSIONS_JS

    def test_helper_calls_are_capability_guarded(self):
        """Harnessy node podstawiaja atrapy DOM — wywolanie bez strazy je wywala."""
        for linia in SESSIONS_JS.splitlines():
            if "a11yAsButton(" in linia and "function a11yAsButton" not in linia:
                assert "typeof a11yAsButton==='function'" in linia, (
                    f"wywolanie helpera bez strazy typeof: {linia.strip()[:90]}"
                )


class TestLinkLooksUnchangedButFocusIsVisible:

    def test_anchor_keeps_the_previous_span_appearance(self):
        """Link musi wygladac dokladnie jak dawny <span>.

        UWAGA na `color`: NIE `inherit`. Pierwsza wersja tej poprawki uzywala
        `color:inherit` i ZMIERZONO regresje wizualna — `inherit` bierze kolor
        RODZICA (.session-item ma var(--muted)), a dawny <span class=session-title>
        mial wlasna regule z var(--text). Tytuly zrobily sie szare
        rgb(192,192,192) zamiast rgb(255,248,220), czyli poprawka dostepnosci
        przygasila cala liste rozmow. Dlatego wprost var(--text).
        """
        assert "a.session-title{text-decoration:none;color:var(--text);cursor:pointer;}" in STYLE_CSS, (
            "Link nie moze zmienic wygladu listy: bez podkreslenia, kolor "
            "var(--text) (NIE inherit — dziedziczy szary z wiersza)."
        )
        assert "color:inherit" not in STYLE_CSS.split("a.session-title")[1][:120], (
            "color:inherit na tytule-linku przygasza liste (zmierzone)."
        )
        # Wiersz aktywny ma wlasny kolor akcentu i jego regula MUSI wygrac:
        # .session-item.active .session-title = specyficznosc (0,2,0)
        # a.session-title                     = specyficznosc (0,1,1)
        assert ".session-item.active .session-title{color:var(--accent-text);}" in STYLE_CSS

    def test_focus_indicator_uses_an_opaque_colour(self):
        """--focus-ring ma alfe .35 i zlewa sie z tlem: zmierzone 1,15:1."""
        assert "a.session-title:focus-visible{outline:2px solid var(--accent);" in STYLE_CSS, (
            "Wskaznik fokusu musi miec kontrast >=3:1 (WCAG 1.4.11). "
            "var(--focus-ring) jest polprzezroczysty i dal 1,15:1; "
            "var(--accent) zmierzono na 11,12:1."
        )
        assert "a.session-title:focus-visible{outline:2px solid var(--focus-ring)" not in STYLE_CSS

    def test_other_sidebar_controls_also_show_focus(self):
        assert ".session-date-header:focus-visible" in STYLE_CSS
        assert ".session-select-toggle:focus-visible" in STYLE_CSS
        assert ".project-chip:focus-visible" in STYLE_CSS


class TestBatchSelectCheckboxNamesTheConversation:
    """Znalezione dopiero w pomiarze pokrycia stanow, nie w spoczynku.

    Tryb wyboru wsadowego to osobny stan panelu — w spoczynku pol wyboru nie ma.
    Zmierzone tam: 4 kontrolki bez nazwy dostepnej (2 pola + 2 opakowania).
    Czytnik oglaszal gole "pole wyboru, nieoznaczone", wiec przy kilku wierszach
    nie bylo jak ustalic, ktora rozmowa zostanie zarchiwizowana lub usunieta.
    """

    def test_checkbox_has_accessible_name_with_the_session_title(self):
        assert "cb.setAttribute('aria-label',cbNazwa+': '+(cleanTitle||'Untitled'));" in SESSIONS_JS, (
            "Pole wyboru musi nazywac KONKRETNA rozmowe — sama etykieta "
            "'Select conversation' nie rozroznia wierszy przy operacji wsadowej."
        )

    def test_checkbox_label_key_exists_in_the_base_locale(self):
        i18n = (REPO / "static" / "i18n.js").read_text(encoding="utf-8")
        assert "session_batch_select_one: 'Select conversation'," in i18n, (
            "t() zwraca sam klucz, gdy go nie ma w locale — bez wpisu w 'en' "
            "czytnik przeczytalby uzytkownikowi 'session_batch_select_one'."
        )
