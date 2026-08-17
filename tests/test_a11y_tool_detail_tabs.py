"""Zakladki Full/Output w kartach narzedzi musza mowic, ktora jest wybrana.

Zmierzony defekt (18.08.2026): pasek ma role="tablist" i dwa role="tab", ale stan
wybrania istnial WYLACZNIE jako klasa CSS `.active`. Czytnik ekranu mowil wiec
"zakladka Output" i nie mowil, czy jest wlaczona - informacja dostepna tylko dla
osoby widzacej (WCAG 4.1.2). Brakowalo tez aria-controls, nazwy paska i nawigacji
strzalkami, ktorej rola tab wymaga (ARIA APG: Tabs).

To TRZECIA kopia tego samego wzorca w tym pliku - pasek powstaje w trzech
miejscach (dwa razy przez createElement, raz w szablonie HTML karty). Dlatego
stan deklaruje JEDNA funkcja `_syncTransparentDetailTabsA11y` wolana ze wszystkich
sciezek, a nie atrybuty dopisane w trzech szablonach: czwarta kopia inaczej
znowu urodzilaby sie niema.

Testy sprawdzaja ZACHOWANIE (wykonuja kod w node), a nie obecnosc tekstu w
zrodle, bo naprawa polega na tym, KIEDY atrybuty powstaja - grep po zrodle
przeszedlby tez na kodzie, ktory ustawia je tylko po kliknięciu.

Dwie pulapki tej naprawy zapiete tutaj na stale:
1. STAN POCZATKOWY. Zanim ktos kliknie, pasek tez musi byc zadeklarowany -
   pierwsza wersja poprzedniej naprawy (Settings > Extensions) wolala helper po
   wczesnym `return`, wiec kontrakt nie powstawal wcale.
2. SCIEZKA Z SZABLONU. Gdy detal przychodzi z gotowego HTML, ktory JUZ zawiera
   pasek, warunek "doklej pasek" jest falszywy - a to wlasnie ten pasek nie ma
   zadeklarowanego stanu. Synchronizacja musi stac POZA tym warunkiem.
"""

from pathlib import Path
import json
import re
import shutil
import subprocess

import pytest

REPO = Path(__file__).resolve().parent.parent
UI_JS = (REPO / "static" / "ui.js").read_text(encoding="utf-8")
A11Y_JS = (REPO / "static" / "a11y-helpers.js").read_text(encoding="utf-8")
I18N_JS = (REPO / "static" / "i18n.js").read_text(encoding="utf-8")

NODE = shutil.which("node")

# Scena i asercje wykonywane w node: minimalna atrapa DOM + PRAWDZIWE funkcje
# wyciete ze zrodla ui.js (nie kopie, zeby test nie mogl sie rozjechac z kodem).
HARNESS = r"""
const fs = require('fs');
const vm = require('vm');

function mkEl(tag) {
  return {
    tagName: (tag || 'div').toUpperCase(),
    children: [], attrs: {}, classes: new Set(), dataset: {}, id: '',
    textContent: '', parentNode: null, listeners: {},
    setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; },
    hasAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k); },
    removeAttribute(k) { delete this.attrs[k]; },
    appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
    insertBefore(c) { c.parentNode = this; this.children.unshift(c); return c; },
    addEventListener(t, fn) { (this.listeners[t] = this.listeners[t] || []).push(fn); },
    get firstChild() { return this.children[0] || null; },
    get classList() {
      const s = this.classes;
      return { add: (c) => s.add(c), remove: (c) => s.delete(c), contains: (c) => s.has(c),
               toggle: (c, on) => { if (on === undefined) { s.has(c) ? s.delete(c) : s.add(c); }
                                    else if (on) s.add(c); else s.delete(c); } };
    },
    descendants() { let o = []; for (const c of this.children) { o.push(c); o = o.concat(c.descendants()); } return o; },
    matches(sel) {
      if (sel === '[role="tab"]') return this.getAttribute('role') === 'tab';
      if (sel === '.transparent-detail-mode') return this.classes.has('transparent-detail-mode');
      if (sel === '.transparent-detail-modes') return this.classes.has('transparent-detail-modes');
      if (sel === '.tool-card-detail') return this.classes.has('tool-card-detail');
      if (sel === '.transparent-event-row') return this.classes.has('transparent-event-row');
      throw new Error('atrapa nie zna selektora ' + sel);
    },
    querySelectorAll(sel) { return this.descendants().filter((d) => d.matches(sel)); },
    querySelector(sel) { return this.querySelectorAll(sel)[0] || null; },
    closest(sel) { let n = this; while (n) { if (n.matches && n.matches(sel)) return n; n = n.parentNode; } return null; },
    focus() { ctx.document.activeElement = this; },
    click() { if (this._onclick) this._onclick(); },
  };
}

const ctx = {
  window: {},
  document: { activeElement: null, getElementById: () => null, createElement: (t) => mkEl(t),
              querySelectorAll: () => [], querySelector: () => null,
              addEventListener: () => {}, readyState: 'complete', body: mkEl('body') },
  console, Math, JSON, String, Number, Boolean, Array, Object, Date, RegExp, Set, Map,
  requestAnimationFrame: (fn) => fn(),
  setTimeout: () => 0, clearTimeout: () => {}, setInterval: () => 0, clearInterval: () => {},
  MutationObserver: function () { return { observe() {}, disconnect() {} }; },
  location: { href: 'http://127.0.0.1/' },
};
ctx.window.document = ctx.document;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(A11Y_PATH, 'utf8'), ctx);

const uiSrc = fs.readFileSync(UI_PATH, 'utf8');
function wytnij(nazwa) {
  const start = uiSrc.indexOf('function ' + nazwa + '(');
  if (start < 0) throw new Error('brak funkcji ' + nazwa + ' w ui.js');
  let g = 0;
  for (let j = uiSrc.indexOf('{', start); j < uiSrc.length; j++) {
    if (uiSrc[j] === '{') g++;
    else if (uiSrc[j] === '}') { g--; if (!g) return uiSrc.slice(start, j + 1); }
  }
  throw new Error('nie domknalem ' + nazwa);
}
vm.runInContext(wytnij('_syncTransparentDetailTabsA11y'), ctx);
vm.runInContext(wytnij('_setTransparentDetailMode'), ctx);

function scena() {
  const row = mkEl('div'); row.classList.add('transparent-event-row');
  const detail = mkEl('div'); detail.classList.add('tool-card-detail');
  detail.setAttribute('data-transparent-detail-mode', 'full');
  const modes = mkEl('div'); modes.classList.add('transparent-detail-modes');
  modes.setAttribute('role', 'tablist');
  const full = mkEl('span');
  full.classList.add('transparent-detail-mode'); full.classList.add('active');
  full.setAttribute('role', 'tab'); full.setAttribute('data-mode', 'full'); full.textContent = 'Full';
  const output = mkEl('span');
  output.classList.add('transparent-detail-mode');
  output.setAttribute('role', 'tab'); output.setAttribute('data-mode', 'output'); output.textContent = 'Output';
  modes.appendChild(full); modes.appendChild(output);
  detail.appendChild(modes); row.appendChild(detail);
  return { row, detail, modes, full, output };
}

const out = {};
let s = scena();
ctx._syncTransparentDetailTabsA11y(s.detail, 'full');
out.start = {
  fullSelected: s.full.getAttribute('aria-selected'),
  outputSelected: s.output.getAttribute('aria-selected'),
  tablistNazwa: !!(s.modes.getAttribute('aria-label') || s.modes.getAttribute('aria-labelledby')),
  controlsWskazujePanel: s.full.getAttribute('aria-controls') === s.detail.id && !!s.detail.id,
  panelRola: s.detail.getAttribute('role'),
  panelNazwanyAktywna: s.detail.getAttribute('aria-labelledby') === s.full.id,
  tabindexFull: s.full.getAttribute('tabindex'),
  tabindexOutput: s.output.getAttribute('tabindex'),
};

ctx._setTransparentDetailMode(s.output, 'output');
out.poPrzelaczeniu = {
  fullSelected: s.full.getAttribute('aria-selected'),
  outputSelected: s.output.getAttribute('aria-selected'),
  ariaZgodneZCss: s.output.classList.contains('active') === (s.output.getAttribute('aria-selected') === 'true')
                  && s.full.classList.contains('active') === (s.full.getAttribute('aria-selected') === 'true'),
  panelNazwanyOutput: s.detail.getAttribute('aria-labelledby') === s.output.id,
  tabindexFull: s.full.getAttribute('tabindex'),
  tabindexOutput: s.output.getAttribute('tabindex'),
  tryb: s.detail.getAttribute('data-transparent-detail-mode'),
};

ctx._setTransparentDetailMode(s.full, 'full');
out.powrot = {
  fullSelected: s.full.getAttribute('aria-selected'),
  panelNazwanyFull: s.detail.getAttribute('aria-labelledby') === s.full.id,
};

const przed = (s.modes.listeners.keydown || []).length;
ctx._syncTransparentDetailTabsA11y(s.detail, 'full');
ctx._syncTransparentDetailTabsA11y(s.detail, 'full');
out.idempotencja = {
  nasluchowPrzed: przed,
  nasluchowPo: (s.modes.listeners.keydown || []).length,
  fullSelected: s.full.getAttribute('aria-selected'),
};

s = scena();
ctx._syncTransparentDetailTabsA11y(s.detail, 'full');
s.output._onclick = () => ctx._setTransparentDetailMode(s.output, 'output');
ctx.document.activeElement = s.full;
const keydown = (s.modes.listeners.keydown || [])[0];
out.strzalki = { nasluch: typeof keydown === 'function' };
if (typeof keydown === 'function') {
  keydown({ key: 'ArrowRight', preventDefault() {}, stopPropagation() {} });
  out.strzalki.fokusNaOutput = ctx.document.activeElement === s.output;
  out.strzalki.trybPoStrzalce = s.detail.getAttribute('data-transparent-detail-mode');
}

const s2 = scena();
const zapas = ctx.a11yTablist;
ctx.a11yTablist = undefined;
ctx._syncTransparentDetailTabsA11y(s2.detail, 'output');
out.bezHelpera = {
  outputSelected: s2.output.getAttribute('aria-selected'),
  fullSelected: s2.full.getAttribute('aria-selected'),
};
ctx.a11yTablist = zapas;

console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def zachowanie(tmp_path_factory):
    """Uruchamia kontrakt w node i zwraca zmierzone zachowanie."""
    if not NODE:
        pytest.skip("node niedostepny - nie da sie zmierzyc zachowania")
    katalog = tmp_path_factory.mktemp("tabs")
    skrypt = katalog / "harness.js"
    skrypt.write_text(
        f"const A11Y_PATH = {json.dumps(str(REPO / 'static' / 'a11y-helpers.js'))};\n"
        f"const UI_PATH = {json.dumps(str(REPO / 'static' / 'ui.js'))};\n" + HARNESS,
        encoding="utf-8",
    )
    proc = subprocess.run([NODE, str(skrypt)], capture_output=True, text=True, timeout=90)
    assert proc.returncode == 0, f"harness padl: {proc.stderr[-2000:]}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


class TestStanPoczatkowy:
    """Najczestszy przypadek: uzytkownik czyta karte, nikt nic nie klikal."""

    def test_wybrana_zakladka_jest_zadeklarowana(self, zachowanie):
        s = zachowanie["start"]
        assert s["fullSelected"] == "true", (
            "bez aria-selected czytnik nie powie, ktory widok jest wlaczony"
        )
        assert s["outputSelected"] == "false"

    def test_pasek_ma_nazwe(self, zachowanie):
        assert zachowanie["start"]["tablistNazwa"], (
            "zestaw zakladek bez nazwy brzmi w czytniku jak zbior luznych kontrolek"
        )

    def test_zakladki_wskazuja_panel(self, zachowanie):
        s = zachowanie["start"]
        assert s["controlsWskazujePanel"], "brak aria-controls"
        assert s["panelRola"] == "tabpanel"
        assert s["panelNazwanyAktywna"], "panel musi byc nazwany aktywna zakladka"

    def test_po_zestawie_chodzi_sie_strzalkami_nie_tabem(self, zachowanie):
        s = zachowanie["start"]
        assert (s["tabindexFull"], s["tabindexOutput"]) == ("0", "-1"), (
            "roving tabindex: tylko aktywna zakladka w kolejnosci Tab"
        )


class TestPoPrzelaczeniu:
    def test_stan_wybrania_przechodzi_na_nowa_zakladke(self, zachowanie):
        p = zachowanie["poPrzelaczeniu"]
        assert p["outputSelected"] == "true"
        assert p["fullSelected"] == "false"

    def test_aria_nie_rozjezdza_sie_z_wygladem(self, zachowanie):
        assert zachowanie["poPrzelaczeniu"]["ariaZgodneZCss"], (
            "to, co widac (klasa .active), i to, co slychac (aria-selected), "
            "musi byc tym samym stanem"
        )

    def test_wspolny_panel_zmienia_nazwe_na_aktywna_zakladke(self, zachowanie):
        assert zachowanie["poPrzelaczeniu"]["panelNazwanyOutput"], (
            "oba widoki dziela jeden kontener; gdyby nazwa zostala przy 'Full', "
            "czytnik po przejsciu na 'Output' klamalby o tym, co pokazuje"
        )

    def test_fokus_klawiatury_idzie_za_wyborem(self, zachowanie):
        p = zachowanie["poPrzelaczeniu"]
        assert (p["tabindexFull"], p["tabindexOutput"]) == ("-1", "0")

    def test_widok_faktycznie_sie_przelacza(self, zachowanie):
        assert zachowanie["poPrzelaczeniu"]["tryb"] == "output", (
            "naprawa dostepnosci nie moze zepsuc samego przelaczania widoku"
        )

    def test_powrot_na_pierwsza_zakladke_dziala(self, zachowanie):
        assert zachowanie["powrot"]["fullSelected"] == "true"
        assert zachowanie["powrot"]["panelNazwanyFull"]


class TestNawigacjaStrzalkami:
    """Strzalki sa czescia kontraktu roli tab (ARIA APG: Tabs)."""

    def test_nasluch_klawiatury_jest_zalozony(self, zachowanie):
        assert zachowanie["strzalki"]["nasluch"]

    def test_strzalka_przenosi_fokus_i_przelacza(self, zachowanie):
        assert zachowanie["strzalki"]["fokusNaOutput"]
        assert zachowanie["strzalki"]["trybPoStrzalce"] == "output", (
            "wzorzec automatic activation: strzalka od razu przelacza widok"
        )


class TestOdpornosc:
    def test_powtorne_wywolanie_nie_mnozy_nasluchow(self, zachowanie):
        i = zachowanie["idempotencja"]
        assert i["nasluchowPo"] == i["nasluchowPrzed"], (
            "synchronizacja jest wolana z kilku sciezek renderowania, wiec musi "
            "byc idempotentna - inaczej jedno nacisniecie strzalki zadziala N razy"
        )
        assert i["fullSelected"] == "true"

    def test_bez_helpera_stan_wybrania_i_tak_powstaje(self, zachowanie):
        b = zachowanie["bezHelpera"]
        assert b["outputSelected"] == "true" and b["fullSelected"] == "false", (
            "gdy przegladarka ma stary cache bez a11yTablist, sciezka awaryjna "
            "musi nadal deklarowac, ktora zakladka jest wybrana"
        )


class TestWszystkieSciezkiRenderowania:
    """Pasek powstaje w 3 miejscach - kazde musi deklarowac stan."""

    def test_synchronizacja_wolana_ze_wszystkich_sciezek(self):
        wywolania = UI_JS.count("_syncTransparentDetailTabsA11y(")
        # 1 definicja + 1 z przelacznika + 2 sciezki renderowania
        assert wywolania >= 4, (
            f"tylko {wywolania} wystapien - pasek powstaje w kilku miejscach, "
            "kazde musi zadeklarowac stan, inaczej czesc kart bedzie niema"
        )

    def test_synchronizacja_stoi_poza_warunkiem_doklejania_paska(self):
        """Sciezka z gotowego szablonu nie wchodzi w blok 'doklej pasek'.

        Gdy detal przychodzi z HTML, ktory JUZ ma pasek, warunek
        `!detail.querySelector('.transparent-detail-modes')` jest falszywy -
        a to wlasnie ten pasek nie ma zadeklarowanego stanu.
        """
        for blok in re.findall(
            r"if\(detail&&!detail\.querySelector\('\.transparent-detail-modes'\)\)\{"
            r"(.*?)\n(\s*)\}", UI_JS, re.S
        ):
            assert "_syncTransparentDetailTabsA11y" not in blok[0], (
                "synchronizacja nie moze byc TYLKO wewnatrz warunku doklejania "
                "paska - sciezka z szablonu wtedy ja pominie"
            )
        assert re.search(
            r"if\(detail\)\{\s*\n\s*_syncTransparentDetailTabsA11y\(", UI_JS
        ), "brak bezwarunkowej synchronizacji dla sciezek renderowania"


class TestTlumaczenia:
    def test_nazwa_paska_jest_we_wszystkich_locale(self):
        wystapienia = I18N_JS.count("tool_detail_tabs_aria")
        assert wystapienia >= 15, (
            f"klucz w {wystapienia} locale - repo wymaga pokrycia we wszystkich 15"
        )

    def test_helper_uzywa_klucza_tlumaczenia(self):
        idx = UI_JS.find("function _syncTransparentDetailTabsA11y(")
        assert idx > 0
        assert "tool_detail_tabs_aria" in UI_JS[idx:idx + 1200], (
            "nazwa paska musi byc tlumaczona, nie zaszyta po angielsku"
        )
