"""Praca prowadzona z CLI/TUI musi byc widoczna w przegladarce.

Zgloszenie (18.08.2026): ta sama sesja otwarta rownolegle w terminalu i w WebUI.
W terminalu widac, ze tura trwa; w przegladarce wyglada, jakby Hermes skonczyl
dzialac. Dla uzytkownika czytnika ekranu to najgorszy mozliwy stan: cisza
nieodrozninalna od awarii (WCAG 4.1.3).

ZMIERZONA PRZYCZYNA (na zywej sesji, w ktorej agent wlasnie pisal):
``/api/session`` zwracalo ``is_streaming=false`` i ``active_stream_id=null`` —
serwer sledzi wylacznie strumienie, ktore sam obsluguje, wiec tura lecaca w CLI
jest dla niego niewidoczna. Porownanie sesji pracujacej z bezczynna nie dawalo
ZADNEJ roznicy w polach *stream*/*active*/*pending*.

Sygnal istnial, tylko nikt go nie przekazywal: agent zapisuje swoj biezacy etap
do ``sessions.last_activity_at`` / ``last_activity_description``
("receiving stream response", "executing tool: terminal",
"terminal command running (60s elapsed)"). WebUI nie czytal tych kolumn nigdzie.

DLACZEGO PROG WYNOSI 90 s, a nie 10 czy 30: probkowanie 22x co 4 s w trakcie
realnej pracy pokazalo, ze znacznik potrafi stac 58 s (aktualizuje sie przy
ZMIANIE ETAPU, nie co sekunde), a licznik wiadomosci stal przez cale 88 s
pomiaru. Prog krotszy niz zmierzone maksimum sprawia, ze komunikat MIGA w
srodku jednego dlugiego wywolania modelu — a stan migajacy jest dla uzytkownika
czytnika gorszy niz brak stanu.

Testy WYKONUJA prawdziwe funkcje w node, bo defekt dotyczy DECYZJI podejmowanej
na danych, a nie obecnosci tekstu w zrodle.
"""

from pathlib import Path
import json
import shutil
import subprocess

import pytest

REPO = Path(__file__).resolve().parent.parent
A11Y_JS = (REPO / "static" / "a11y-helpers.js").read_text(encoding="utf-8")
I18N_JS = (REPO / "static" / "i18n.js").read_text(encoding="utf-8")
ROUTES_PY = (REPO / "api" / "routes.py").read_text(encoding="utf-8")
MODELS_PY = (REPO / "api" / "models.py").read_text(encoding="utf-8")
AGENT_SESSIONS_PY = (REPO / "api" / "agent_sessions.py").read_text(encoding="utf-8")
NODE = shutil.which("node")

HARNESS = r"""
const fs = require('fs');
const vm = require('vm');

function mkEl(tag) {
  return {
    tagName: (tag || 'div').toUpperCase(),
    children: [], attrs: {}, classes: new Set(), dataset: {}, id: '',
    style: {}, textContent: '', innerHTML: '', parentNode: null, parentElement: null,
    setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; },
    removeAttribute(k) { delete this.attrs[k]; },
    appendChild(c) { c.parentNode = this; c.parentElement = this; this.children.push(c); return c; },
    insertBefore(c) { c.parentNode = this; c.parentElement = this; this.children.unshift(c); return c; },
    addEventListener() {}, getClientRects() { return [{}]; },
    get classList() {
      const s = this.classes;
      return { add: (c) => s.add(c), remove: (c) => s.delete(c), contains: (c) => s.has(c),
               toggle: (c, on) => { if (on) s.add(c); else s.delete(c); } };
    },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    closest() { return null; },
  };
}

const rejestr = {};
const ctx = {
  window: {},
  document: {
    activeElement: null, readyState: 'complete',
    createElement: (t) => mkEl(t),
    getElementById: (id) => rejestr[id] || null,
    querySelector: () => null, querySelectorAll: () => [],
    addEventListener: () => {}, body: mkEl('body'),
  },
  console, Math, JSON, String, Number, Boolean, Array, Object, Date, RegExp, Set, Map,
  requestAnimationFrame: (fn) => fn(),
  setTimeout: () => 0, clearTimeout: () => {},
  setInterval: () => 0, clearInterval: () => {},
  MutationObserver: function () { return { observe() {}, disconnect() {} }; },
  location: { href: 'http://127.0.0.1/', search: '' },
  fetch: async () => ({ ok: false }),
};
ctx.window.document = ctx.document;
vm.createContext(ctx);
vm.runInContext("function t(k){return null;}", ctx);
vm.runInContext(fs.readFileSync(A11Y_PATH, 'utf8'), ctx);

const sek = () => Date.now() / 1000;
const out = {};

out.pracaSwieza = ctx.a11yForeignRunActivity({
  last_activity_at: sek() - 5,
  last_activity_description: 'executing tool: terminal',
  ended_at: null,
});
out.pracaPrzerwa58 = ctx.a11yForeignRunActivity({
  last_activity_at: sek() - 58,
  last_activity_description: 'receiving stream response',
  ended_at: null,
});
out.znacznikStary = ctx.a11yForeignRunActivity({
  last_activity_at: sek() - 200,
  last_activity_description: 'receiving stream response',
  ended_at: null,
});
out.sesjaZakonczona = ctx.a11yForeignRunActivity({
  last_activity_at: sek() - 3,
  last_activity_description: 'receiving stream response',
  ended_at: 1787000000,
});
out.brakOpisu = ctx.a11yForeignRunActivity({
  last_activity_at: sek() - 3, last_activity_description: '',
});
out.brakZnacznika = ctx.a11yForeignRunActivity({});
out.pusteDane = ctx.a11yForeignRunActivity(null);
out.znacznikZPrzyszlosci = ctx.a11yForeignRunActivity({
  last_activity_at: sek() + 600,
  last_activity_description: 'receiving stream response',
});

const host = mkEl('div'); host.id = 'a11yRunStatus'; rejestr['a11yRunStatus'] = host;
out.zapalony = ctx.a11ySyncForeignRunState({
  last_activity_at: sek() - 4,
  last_activity_description: 'executing tool: terminal',
});
out.tekstStanu = host.textContent;

out.zgaszony = ctx.a11ySyncForeignRunState({
  last_activity_at: sek() - 300,
  last_activity_description: 'receiving stream response',
});
out.tekstPoZgaszeniu = host.textContent;

let ogloszenia = 0;
ctx.a11yAnnounce = () => { ogloszenia += 1; };
ctx.window.a11yAnnounce = ctx.a11yAnnounce;
const dane = { last_activity_at: sek() - 2, last_activity_description: 'executing tool: read_file' };
ctx.a11ySyncForeignRunState(dane);
ctx.a11ySyncForeignRunState(dane);
ctx.a11ySyncForeignRunState(dane);
out.ogloszenia = ogloszenia;

ctx.a11yRunStarted();
out.wlasnyMaPierwszenstwo = ctx.a11ySyncForeignRunState({
  last_activity_at: sek() - 2,
  last_activity_description: 'executing tool: terminal',
});

console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def zachowanie(tmp_path_factory):
    if not NODE:
        pytest.skip("node niedostepny - nie da sie zmierzyc zachowania")
    skrypt = tmp_path_factory.mktemp("obcy") / "harness.js"
    skrypt.write_text(
        f"const A11Y_PATH = {json.dumps(str(REPO / 'static' / 'a11y-helpers.js'))};\n"
        + HARNESS,
        encoding="utf-8",
    )
    proc = subprocess.run([NODE, str(skrypt)], capture_output=True, text=True, timeout=90)
    assert proc.returncode == 0, f"harness padl: {proc.stderr[-2000:]}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


class TestRozpoznawaniePracyZCLI:
    def test_swieza_praca_jest_rozpoznana(self, zachowanie):
        assert zachowanie["pracaSwieza"] == "executing tool: terminal", (
            "tura z CLI musi byc widoczna w przegladarce"
        )

    def test_dluga_przerwa_nie_gasi_stanu(self, zachowanie):
        """Zmierzone maksimum przerwy w sygnale to 58 s."""
        assert zachowanie["pracaPrzerwa58"] == "receiving stream response", (
            "prog musi przetrwac najdluzsza ZMIERZONA przerwe, inaczej komunikat "
            "miga w srodku jednego dlugiego wywolania modelu"
        )

    def test_czynnosc_jest_konkretna(self, zachowanie):
        """Uzytkownik ma wiedziec CO sie dzieje, nie tylko ze cos sie dzieje."""
        assert "tool" in zachowanie["pracaSwieza"] or "stream" in zachowanie["pracaSwieza"]


class TestKiedyStanuNieWolnoZapalac:
    def test_stary_znacznik_to_nie_praca(self, zachowanie):
        assert zachowanie["znacznikStary"] == ""

    def test_zakonczona_sesja_nie_pracuje(self, zachowanie):
        assert zachowanie["sesjaZakonczona"] == "", (
            "ended_at wygrywa ze swiezoscia znacznika"
        )

    def test_bez_opisu_nie_zgadujemy(self, zachowanie):
        assert zachowanie["brakOpisu"] == "", (
            "'cos sie dzieje' bez tresci to szum, nie informacja"
        )

    def test_brak_danych_nie_zapala_stanu(self, zachowanie):
        assert zachowanie["brakZnacznika"] == ""
        assert zachowanie["pusteDane"] == ""

    def test_znacznik_z_przyszlosci_jest_odrzucany(self, zachowanie):
        """Rozjechany zegar nie moze dawac wiecznej 'pracy'."""
        assert zachowanie["znacznikZPrzyszlosci"] == ""


class TestCichyStan:
    def test_stan_zapala_sie_i_niesie_czynnosc(self, zachowanie):
        assert zachowanie["zapalony"] is True
        assert "executing tool: terminal" in zachowanie["tekstStanu"]

    def test_stan_mowi_ze_praca_jest_gdzie_indziej(self, zachowanie):
        tekst = zachowanie["tekstStanu"].lower()
        assert "elsewhere" in tekst or "another" in tekst, (
            "uzytkownik musi wiedziec, ze to nie jest bieg tej karty"
        )

    def test_stan_gasnie_gdy_praca_ustala(self, zachowanie):
        assert zachowanie["zgaszony"] is False
        assert zachowanie["tekstPoZgaszeniu"] == ""

    def test_powtorzenia_nie_gadaja(self, zachowanie):
        assert zachowanie["ogloszenia"] <= 1, (
            "czytnik ma uslyszec komunikat RAZ; odswiezenia sa ciche"
        )

    def test_wlasny_bieg_ma_pierwszenstwo(self, zachowanie):
        assert zachowanie["wlasnyMaPierwszenstwo"] is False, (
            "stan tej karty jest dokladniejszy - nie wolno go nadpisywac"
        )


class TestSciezkaDanychNaSerwerze:
    """Sygnal musi realnie dojsc z bazy do przegladarki."""

    def test_zapytanie_pobiera_kolumny_stanu_pracy(self):
        assert "last_activity_at_expr" in AGENT_SESSIONS_PY
        assert "last_activity_description_expr" in AGENT_SESSIONS_PY
        assert "{last_activity_at_expr}" in AGENT_SESSIONS_PY, (
            "kolumny musza byc w SELECT, nie tylko zdefiniowane"
        )

    def test_projekcja_przekazuje_stan_we_wszystkich_przebiegach(self):
        """Projekcja powstaje w czterech blizniaczych przebiegach."""
        assert MODELS_PY.count("_agent_row_live_work_state(row)") >= 4, (
            "kazdy przebieg musi przekazac stan, inaczej czesc sesji bedzie niema"
        )

    def test_api_session_podaje_stan_dla_kazdego_zrodla(self):
        """Sesja CLI wypadala z obu istniejacych galezi scalania metadanych."""
        idx = ROUTES_PY.find("_merge_cli_sidebar_metadata(raw, cli_meta)")
        assert idx > 0
        okno = ROUTES_PY[idx:idx + 1800]
        assert "last_activity_at" in okno and "last_activity_description" in okno, (
            "przekazanie musi stac POZA galeziami webui/messaging"
        )

    def test_watchdog_uwzglednia_sygnal_agenta(self):
        idx = A11Y_JS.find("_a11yForeignPoll")
        assert idx > 0
        okno = A11Y_JS[idx:idx + 4000]
        assert "last_activity_at" in okno, (
            "sam last_message_at daje martwe okna: zmierzone 88 s pracy bez "
            "ani jednej nowej wiadomosci"
        )


class TestTlumaczenia:
    def test_komunikat_jest_we_wszystkich_locale(self):
        assert I18N_JS.count("a11y_run_working_elsewhere") >= 15, (
            f"klucz w {I18N_JS.count('a11y_run_working_elsewhere')} locale zamiast 15"
        )
