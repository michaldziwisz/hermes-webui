"""Koniec tury musi domknac sie W WIDOKU, bez odswiezania strony.

Zgloszenie uzytkownika (czytnik ekranu): "model skonczy pisac po dluzszym czasie
i mam np. 5. Hermes, working / HHermes / Hermes is working / Idle, a po
odswiezeniu mam wypowiedz, tak nie powinno byc".

Zmierzone przyczyny — trzy osobne, wszystkie z naszych wczesniejszych zmian a11y:

1. `hideLiveRunStatus(sid)` wychodzilo w PIERWSZEJ linii, gdy identyfikator sesji
   nie zgadzal sie z zapamietanym, i wtedy NIE wolalo a11yRunFinished(). Stan
   biegu zostawal otwarty na zawsze.
2. `_a11yTurnIsLive()` traktowalo "bieg trwa" jako dowod, ze OSTATNIA tura
   asystenta jest zywa. W polaczeniu z (1) kazda zakonczona tura wygladala na
   trwajaca: naglowek czytal "working", a `_a11yReorderTurn` celowo omija tury
   zywe, wiec tresc odpowiedzi zostawala ZA dziennikiem aktywnosci. Odswiezenie
   budowalo widok od zera i dlatego "naprawialo" objaw.
3. Ikona roli to kolko z PIERWSZA LITERA nazwy ("H") renderowane obok podpisu.
   Bez aria-hidden czytnik czytal litere jako osobny tekst: "H Hermes".

Dowod z dzialajacej aplikacji po naprawie (pelny cykl tury, Edge + CDP):
w toku naglowek "11. Hermes, working"; po zakonczeniu BEZ odswiezenia
"26. Hermes 19:09", tresc obecna (102 znaki), bieg zamkniety, brak zdublowanej
litery; widok przed odswiezeniem identyczny z widokiem po odswiezeniu.
Drzewo dostepnosci: 0 samotnych wielkich liter, 7/7 ikon z aria-hidden, przy
zachowanej widocznosci wizualnej 7/7.
"""

from pathlib import Path

import json
import shutil
import subprocess

import pytest

REPO = Path(__file__).resolve().parent.parent
A11Y_JS = (REPO / "static" / "a11y-helpers.js").read_text(encoding="utf-8")
UI_JS = (REPO / "static" / "ui.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


class TestRunStateAlwaysCloses:

    def test_hide_status_closes_run_state_before_the_session_guard(self):
        """Bramka na sid nie moze przeskoczyc zamkniecia stanu biegu."""
        idx = UI_JS.find("function hideLiveRunStatus(sid){")
        assert idx > 0, "hideLiveRunStatus nie znaleziona"
        blok = UI_JS[idx:idx + 1400]
        poz_finish = blok.find("a11yRunFinished()")
        poz_guard = blok.find("if(sid&&_liveRunStatusSessionId&&sid!==_liveRunStatusSessionId) return;")
        assert poz_finish > 0, "brak wywolania a11yRunFinished"
        assert poz_guard > 0, "brak bramki na identyfikator sesji"
        assert poz_finish < poz_guard, (
            "a11yRunFinished() musi byc PRZED wyjsciem na niezgodny sid — inaczej "
            "stan 'Hermes is working' zostaje otwarty i widok nigdy nie domyka tury."
        )

    def test_stream_done_also_closes_run_state(self):
        """Druga, niezalezna droga zamkniecia — jedna moze zostac pominieta."""
        messages = (REPO / "static" / "messages.js").read_text(encoding="utf-8")
        assert "a11yRunFinished();" in messages, (
            "Handler zakonczenia strumienia musi tez zamykac stan biegu."
        )


class TestLivenessComesFromTheTurnItself:
    """Zywosc tury ma wynikac z jej WLASNYCH znacznikow, nie ze stanu globalnego."""

    def test_global_run_state_is_not_used_as_liveness_evidence(self):
        idx = A11Y_JS.find("function _a11yTurnIsLive(row){")
        assert idx > 0
        koniec = A11Y_JS.find("\n}", idx)
        cialo = A11Y_JS[idx:koniec]
        # Liczy sie KOD, nie komentarze: w ciele funkcji stoi celowo wyjasnienie,
        # dlaczego tej poszlaki nie uzywamy, i samo slowo a11yRunIsActive w nim
        # wystepuje. Pierwsza wersja tego testu padala wlasnie na komentarzu —
        # sprawdzalaby literalny tekst zamiast zachowania.
        bez_komentarzy = "\n".join(
            linia for linia in cialo.splitlines()
            if not linia.strip().startswith("//")
        )
        assert "a11yRunIsActive" not in bez_komentarzy, (
            "Poszlaka 'bieg trwa => ostatnia tura zywa' zamieniala JEDEN pominiety "
            "sygnal konca w trwale zawieszenie widoku (naglowek 'working', tresc "
            "za dziennikiem). Zywosc ustalamy wylacznie ze znacznikow tury."
        )

    def test_liveness_markers_belong_to_the_row(self):
        idx = A11Y_JS.find("function _a11yTurnIsLive(row){")
        cialo = A11Y_JS[idx:A11Y_JS.find("\n}", idx)]
        for marker in ("liveAssistantTurn", "dataset.live", ".stream-cursor"):
            assert marker in cialo, f"brak znacznika zywosci: {marker}"


class TestRoleIconIsDecorative:

    def test_role_icon_is_hidden_from_screen_readers(self):
        idx = UI_JS.find("function _assistantRoleHtml(")
        assert idx > 0
        blok = UI_JS[idx:idx + 1400]
        assert 'class="role-icon assistant" aria-hidden="true"' in blok, (
            "Kolko z pierwsza litera nazwy powtarza sasiedni podpis. Bez "
            "aria-hidden czytnik czyta 'H Hermes' — zgloszone jako 'HHermes'."
        )

    def test_role_name_is_still_exposed(self):
        """Ukrywamy DEKORACJE, nie informacje — nazwa musi zostac."""
        idx = UI_JS.find("function _assistantRoleHtml(")
        blok = UI_JS[idx:idx + 1400]
        assert '<span class="msg-role-name">' in blok
        assert 'aria-hidden="true">${esc(_bn)}' not in blok, (
            "Nazwa asystenta nie moze byc ukryta przed czytnikiem."
        )

    def test_snippet_filter_drops_role_parts_independently(self):
        """Filtr wycinka nie moze zakladac, ze czesci podpisu leza w .msg-role."""
        assert "'.msg-role', '.role-icon', '.msg-role-name'," in A11Y_JS, (
            "Ikona i nazwa roli musza byc odfiltrowane OSOBNO — filtrowanie "
            "samego rodzica bylo zalozeniem o strukturze znacznikow."
        )


class TestEmptyMeansDoneIdleMeansPause:
    """Rozroznienie ustalone z uzytkownikiem (czytnik ekranu).

    "Jesli faktycznie nic nie robi, to niech jest puste. Jesli np. czekamy
    i zaraz ma sie jeszcze cos pojawic, a chwilowo model nic nie robi, no to Idle."

    Czyli: PUSTE = koniec tury, "Idle" = chwilowa cisza W TOKU biegu. Wczesniej
    a11yRunFinished() wpisywalo tam "Idle", wiec po kazdej gotowej odpowiedzi
    uzytkownik zastawal komunikat sugerujacy, ze cos jeszcze sie dzieje.
    """

    def test_finished_run_clears_the_status_field(self):
        idx = A11Y_JS.find("function a11yRunFinished(){")
        assert idx > 0
        cialo = A11Y_JS[idx:A11Y_JS.find("\n}", idx)]
        assert "el.textContent = '';" in cialo, (
            "Po zakonczeniu pracy pole stanu musi byc PUSTE."
        )
        kod = "\n".join(l for l in cialo.splitlines() if not l.strip().startswith("//"))
        assert "a11y_run_idle" not in kod, (
            "Koniec tury nie moze wpisywac 'Idle' — to slowo jest zarezerwowane "
            "dla przerwy w toku pracy."
        )

    def test_idle_pause_helper_exists_and_requires_an_active_run(self):
        idx = A11Y_JS.find("function a11yRunIdlePause(){")
        assert idx > 0, "brak a11yRunIdlePause — 'Idle' nie mialoby gdzie powstac"
        cialo = A11Y_JS[idx:A11Y_JS.find("\n}", idx)]
        assert "if (!_a11yRunActive) return;" in cialo, (
            "'Idle' ma sens tylko przy AKTYWNYM biegu; po zakonczeniu pole jest puste."
        )
        assert "a11y_run_idle" in cialo

    def test_refresh_switches_to_idle_when_nothing_is_happening(self):
        """Bez tego wywolania helper byl kodem, ktorego nikt nie wola."""
        idx = A11Y_JS.find("function _a11yRefreshRunStatus(){")
        assert idx > 0
        cialo = A11Y_JS[idx:A11Y_JS.find("\n}", idx)]
        assert "a11yRunIdlePause()" in cialo, (
            "Cichy status musi sam przechodzic w 'Idle', gdy w toku biegu nie ma "
            "ani biezacej czynnosci, ani przyrostu tresci."
        )

    def test_output_probe_looks_only_at_the_live_turn(self):
        """Odcisk postepu musi patrzec na TURE NA ZYWO, nie na caly zapis.

        Wczesniejsza wersja (`_a11yRunProducedOutput`) miala zapasowe siegniecie
        do #messages, ktore znajdowalo proze POPRZEDNIEJ, zakonczonej tury —
        funkcja zwracala wtedy zawsze prawde i przerwa nigdy nie zostalaby
        wykryta. Mechanizm zostal zastapiony odciskiem postepu, ale ten sam
        warunek obowiazuje dalej.
        """
        idx = A11Y_JS.find("function _a11yRunProgressFingerprint(){")
        assert idx > 0, "brak odcisku postepu"
        cialo = A11Y_JS[idx:A11Y_JS.find("\n}", idx)]
        assert "getElementById('messages')" not in cialo, (
            "Pytanie o przyrost tresci musi dotyczyc TURY NA ZYWO; siegniecie do "
            "calego zapisu rozmowy zawsze znajdzie stara proze i przerwa nigdy "
            "nie zostalaby wykryta."
        )
        assert "liveAssistantTurn" in cialo

    def test_status_stays_quiet(self):
        """Cichy status: czytnik nie czyta go sam, uzytkownik wchodzi tam sam."""
        assert "el.setAttribute('aria-live', 'off');" in A11Y_JS

    def test_idle_threshold_measures_lack_of_change_not_lack_of_element(self):
        """Karta aktywnosci WISI na ekranie takze wtedy, gdy model milczy.

        Pierwsza wersja pytala "czy jest karta aktywnosci" i dlatego nigdy nie
        wchodzila w 'Idle' — zmierzone: status uparcie pokazywal
        "Hermes is working — Processed 0s", choc nic nie przyrastalo.
        """
        assert "A11Y_RUN_IDLE_AFTER_MS" in A11Y_JS
        idx = A11Y_JS.find("function _a11yRunProgressFingerprint(){")
        assert idx > 0, "brak odcisku postepu — nie da sie zmierzyc BRAKU zmiany"
        cialo = A11Y_JS[idx:A11Y_JS.find("\n}", idx)]
        assert "assistant-segment" in cialo, "odcisk musi obejmowac dlugosc prozy"
        assert "_a11yCurrentActivity()" in cialo
        odsw = A11Y_JS[A11Y_JS.find("function _a11yRefreshRunStatus(){"):]
        assert "_a11yRunSilenceMs() >= A11Y_RUN_IDLE_AFTER_MS" in odsw, (
            "'Idle' musi wynikac z progu CISZY, nie z braku elementu na ekranie."
        )


class TestForeignSessionStillRunningIsAnnounced:
    """Sesja prowadzona z zewnatrz (TUI/Telegram) tez musi dawac sygnal.

    Zgloszenie: "jesli otworze dzialajaca z webui sesje, ktora zaczalem z innego
    miejsca, to jesli tam sie dzieje cos, to tez chce o tym wiedziec i zeby lecial
    timer - sesja zyje, ja nie mam informacji, ze zyje".

    Zmierzone PRZED: dla trwajacej sesji TUI serwer zwracal active_stream_id=null
    i is_streaming=false (webui ustawia je tylko dla WLASNYCH tur), mimo ze w
    state.db ostatnia wiadomosc miala znacznik 4 s wczesniej. Wszystkie cztery
    kanaly milczaly: wskaznik ukryty, cichy status nieutworzony, stan biegu
    wylaczony, naglowek bez "working".

    Zmierzone PO (sesja 20260817_175957_970e47, zywa w trakcie pomiaru):
    naglowek "2. Hermes, working", licznik 5->10->15->20->25->30 s (TYKA),
    "Idle — 20 s" w przerwie, jednorazowe ogloszenie "Hermes is working",
    status nadal cichy (aria-live=off).
    """

    def test_watchdog_exists_and_is_started(self):
        assert "function a11yWatchForeignRun(){" in A11Y_JS
        assert "window.a11yWatchForeignRun = a11yWatchForeignRun;" in A11Y_JS
        assert "DOMContentLoaded" in A11Y_JS, (
            "Watchdog musi wstac sam — inaczej sygnal zalezy od tego, czy ktos go zawola."
        )

    def test_liveness_is_growth_of_last_message_at_not_a_flag(self):
        idx = A11Y_JS.find("async function _a11yForeignPoll(){")
        assert idx > 0
        cialo = A11Y_JS[idx:A11Y_JS.find("\nfunction a11yWatchForeignRun", idx)]
        assert "last_message_at" in cialo, (
            "Jedyne pole, ktore rosnie niezaleznie od wlasciciela strumienia."
        )
        assert "active_stream_id" not in cialo, (
            "active_stream_id jest puste dla sesji z TUI/Telegrama — opieranie sie "
            "na nim bylo wlasnie przyczyna ciszy."
        )
        assert "stamp > _a11yForeignLastStamp" in cialo, "trzeba mierzyc PRZYROST"

    def test_watchdog_defers_to_this_tab_when_it_owns_the_turn(self):
        idx = A11Y_JS.find("async function _a11yForeignPoll(){")
        cialo = A11Y_JS[idx:A11Y_JS.find("\nfunction a11yWatchForeignRun", idx)]
        assert "_a11yThisTabOwnsTurn()" in cialo, (
            "Gdy ture prowadzi ta karta, wlascicielem stanu jest zwykla sciezka "
            "strumienia — dwa wlascicieli to wyscig."
        )

    def test_watchdog_extinguishes_itself_so_state_cannot_hang(self):
        """Ta poszlaka nie moze powtorzyc bledu 'working na zawsze'."""
        assert "A11Y_FOREIGN_DONE_AFTER_MS" in A11Y_JS
        idx = A11Y_JS.find("async function _a11yForeignPoll(){")
        cialo = A11Y_JS[idx:A11Y_JS.find("\nfunction a11yWatchForeignRun", idx)]
        assert "a11yRunFinished()" in cialo, (
            "Watchdog MUSI sam gasic stan po zmierzonym braku przyrostu."
        )

    def test_network_failure_is_not_treated_as_finished(self):
        """Fail closed: brak odpowiedzi to nie dowod, ze praca sie skonczyla."""
        idx = A11Y_JS.find("async function _a11yForeignPoll(){")
        cialo = A11Y_JS[idx:A11Y_JS.find("\nfunction a11yWatchForeignRun", idx)]
        assert "catch (_e) { return; }" in cialo

    def test_heading_reads_working_for_a_foreign_run(self):
        """W obcej sesji NIE MA tury na zywo w DOM, a naglowek ma mowic 'working'."""
        idx = A11Y_JS.find("function _a11yTurnIsLive(row){")
        cialo = A11Y_JS[idx:A11Y_JS.find("\n}", idx)]
        assert "_a11yForeignOwnsRun" in cialo
        assert "typeof _a11yForeignOwnsRun !== 'undefined'" in cialo, (
            "Zmienna jest deklarowana przez let DALEJ w pliku — gole odwolanie "
            "moze rzucic ReferenceError i wywalic caly render."
        )


class TestSilenceBaselineBelongsToTheRun:
    """Nowy bieg nie moze dziedziczyc ciszy sprzed siebie.

    Zmierzony objaw (18.08.2026, CDP na dzialajacej aplikacji + node vm):
    zaraz po zapaleniu stanu cichy status pokazywal "Idle — 0 s". Ten komunikat
    jest SPRZECZNY WEWNETRZNIE: licznik biegu mowi 0 s, a slowo "Idle" wymaga
    A11Y_RUN_IDLE_AFTER_MS = 12 s BEZ zmiany odcisku postepu.

    Przyczyna: `_a11yRunLastFingerprint` / `_a11yRunLastChangeAt` sa modulowe
    i zerowaly sie tylko przy ZMIANIE odcisku, wiec gdy uzytkownik po prostu
    patrzyl na otwarta rozmowe, znacznik starzal sie bez konca i pierwszy
    pomiar nowego biegu od razu przekraczal prog.

    Skutek dla uzytkownika czytnika: dowiaduje sie "Idle" (nic sie nie dzieje)
    dokladnie w chwili, gdy praca sie ZACZYNA — czyli status klamie w drugą
    strone niz poprzednio naprawiany "working po zakonczeniu". WCAG 4.1.3.

    Testy wykonuja PRAWDZIWY kod w node (vm), a nie sprawdzaja tekstu zrodla —
    naprawa polega na kolejnosci przypisan w czasie, ktorej grep nie zmierzy.
    """

    HARNESS = r"""
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync(SRC, 'utf8');
function makeEl(id) {
  return {
    id, textContent: '', className: '', _attrs: {},
    setAttribute(k, v){ this._attrs[k] = v; },
    getAttribute(k){ return this._attrs[k] ?? null; },
    querySelector(){ return null; }, querySelectorAll(){ return []; },
    appendChild(){}, insertBefore(){}, parentElement: null,
  };
}
const status = makeEl('a11yRunStatus');
const context = {
  console,
  setInterval(){ return 1; }, clearInterval(){}, setTimeout(){ return 1; }, clearTimeout(){}, Date,
  document: {
    getElementById(id){ return id === 'a11yRunStatus' ? status : null; },
    querySelector(){ return null; }, querySelectorAll(){ return []; },
    createElement(){ return makeEl('nowy'); }, addEventListener(){},
    body: { appendChild(){} }, readyState: 'complete',
  },
  window: { addEventListener(){} },
  location: { pathname: '/session/abc' },
  t(k){ return {a11y_run_working: 'Hermes is working', a11y_run_idle: 'Idle',
                a11y_run_started: 'Hermes is working'}[k] || k; },
  fetch(){ return Promise.reject(new Error('no network in test')); },
};
context.globalThis = context;
vm.createContext(context);
vm.runInContext(src, context);
const out = vm.runInContext(SCENARIO, context);
console.log(JSON.stringify(out));
"""

    def _run(self, scenario):
        if not NODE:
            pytest.skip("node niedostepny")
        script = (
            self.HARNESS
            .replace("SRC", json.dumps(str(REPO / "static" / "a11y-helpers.js")))
            .replace("SCENARIO", json.dumps(scenario))
        )
        r = subprocess.run([NODE, "-e", script], capture_output=True, text=True)
        assert r.returncode == 0, f"node failed: {r.stderr[-2000:]}"
        return json.loads(r.stdout)

    def test_new_run_does_not_inherit_silence_from_before_it(self):
        """Bieg, ktory wlasnie wstal, mowi 'working' — nawet po dlugim bezruchu."""
        out = self._run("""(() => {
          _a11yRunSilenceMs();                        // ustal baze odcisku
          _a11yRunLastChangeAt = Date.now() - 20000;  // 20 s bezruchu STRONY
          a11yRunStarted();
          return {tekst: document.getElementById('a11yRunStatus').textContent,
                  licznik: _a11yRunElapsedText()};
        })()""")
        assert out["licznik"] == "0 s"
        assert out["tekst"].startswith("Hermes is working"), (
            f"Nowy bieg raportuje {out['tekst']!r} przy liczniku {out['licznik']!r} — "
            "'Idle' wymaga 12 s bez zmian, wiec ten komunikat jest sprzeczny sam ze soba."
        )

    def test_real_silence_during_a_run_still_reports_idle(self):
        """Kontrola negatywna: naprawa nie moze zabic funkcji, ktora chroni."""
        out = self._run("""(() => {
          a11yRunStarted();
          _a11yRunLastChangeAt = Date.now() - 20000;  // 20 s ciszy JUZ W TOKU biegu
          _a11yRefreshRunStatus();
          return {tekst: document.getElementById('a11yRunStatus').textContent};
        })()""")
        assert out["tekst"].startswith("Idle"), (
            "Przerwa w toku pracy musi nadal dawac 'Idle' — inaczej zamiast bledu "
            "komunikatu mamy brak informacji."
        )

    def test_second_run_after_a_finished_one_is_clean(self):
        """Bieg zwalnia swoja baze na koniec, wiec nastepny zaczyna od zera."""
        out = self._run("""(() => {
          a11yRunStarted();
          _a11yRunLastChangeAt = Date.now() - 20000;
          a11yRunFinished();
          const poKoncu = document.getElementById('a11yRunStatus').textContent;
          a11yRunStarted();
          return {poKoncu, drugi: document.getElementById('a11yRunStatus').textContent};
        })()""")
        assert out["poKoncu"] == "", "Koniec tury zostawia PUSTE pole."
        assert out["drugi"].startswith("Hermes is working"), (
            f"Drugi bieg raportuje {out['drugi']!r} — odziedziczyl znacznik po pierwszym."
        )

    def test_idle_never_appears_without_an_active_run(self):
        """Puste = koniec. Bez biegu zadna cisza nie moze zapalic 'Idle'."""
        out = self._run("""(() => {
          a11yRunStarted();
          a11yRunFinished();
          _a11yRunLastChangeAt = Date.now() - 60000;
          _a11yRefreshRunStatus();
          a11yRunIdlePause();
          return {tekst: document.getElementById('a11yRunStatus').textContent,
                  aktywny: a11yRunIsActive()};
        })()""")
        assert out["aktywny"] is False
        assert out["tekst"] == ""

    def test_baseline_reset_is_one_shared_helper_not_copies(self):
        """Chokepoint, nie N rownoleglych przypisan (wytyczna 8 z GUIDELINES)."""
        assert "function _a11yResetSilenceBaseline(){" in A11Y_JS
        for fn in ("function a11yRunStarted(){", "function a11yRunFinished(){"):
            idx = A11Y_JS.find(fn)
            assert idx > 0, f"brak {fn}"
            cialo = A11Y_JS[idx:A11Y_JS.find("\n}", idx)]
            assert "_a11yResetSilenceBaseline()" in cialo, (
                f"{fn} musi zwalniac baze ciszy przez WSPOLNY helper — granica biegu "
                "jest jedynym miejscem, w ktorym ten pomiar wolno zerowac."
            )
            assert "_a11yRunLastChangeAt =" not in cialo, (
                "Kopia przypisania zamiast helpera rozjedzie sie przy nastepnej zmianie."
            )

