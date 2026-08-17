"""Listy wyboru sterowane strzalkami musza oglaszac, co jest wybrane.

Zmierzony defekt (18.08.2026): podpowiedzi komend /slash i podpowiedzi sciezek
katalogu roboczego maja pelna nawigacje strzalkami, ale wybrana pozycja byla
oznaczona WYLACZNIE klasa CSS. Fokus zostaje w polu tekstowym, wiec czytnik
ekranu nie oglaszal niczego przy przechodzeniu po liscie - uzytkownik nie
wiedzial, co zatwierdzi Enterem (WCAG 4.1.2).

Repo rozwiazalo juz dokladnie ten problem dla listy modeli (static/ui.js,
_highlightRow, komentarz autora wprost o WCAG 4.1.2): role="option" +
aria-selected na wierszach oraz role="combobox" + aria-activedescendant na polu.
Te dwie listy byly niezaadresowanymi kopiami tego samego wzorca, dlatego zamiast
trzeciej kopii logiki wprowadzamy wspolny helper a11yActiveDescendantList.

Kontrakt jest CALOSCIOWY i testy pilnuja go w calosci: sama aria-selected nie
wystarczy, bo bez role="listbox"/"option" czytnik nie traktuje elementu jak listy
wyboru, a bez aria-activedescendant nie oglosi ruchu, skoro fokus nie wedruje.

Testy WYKONUJA prawdziwe funkcje wyciete ze zrodel (node vm), a nie sprawdzaja
obecnosci tekstu, bo defekt dotyczy tego, KIEDY atrybuty powstaja: kontrola
zrodla przeszlaby takze na kodzie ustawiajacym je w zlym momencie.
"""

from pathlib import Path
import json
import shutil
import subprocess

import pytest

REPO = Path(__file__).resolve().parent.parent
COMMANDS_JS = (REPO / "static" / "commands.js").read_text(encoding="utf-8")
PANELS_JS = (REPO / "static" / "panels.js").read_text(encoding="utf-8")
I18N_JS = (REPO / "static" / "i18n.js").read_text(encoding="utf-8")
NODE = shutil.which("node")

HARNESS = r"""
const fs = require('fs');
const vm = require('vm');

function mkEl(tag) {
  return {
    tagName: (tag || 'div').toUpperCase(),
    children: [], attrs: {}, classes: new Set(), dataset: {}, id: '',
    style: {}, textContent: '', innerHTML: '', parentNode: null, listeners: {},
    setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; },
    hasAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k); },
    removeAttribute(k) { delete this.attrs[k]; },
    appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
    addEventListener(t, fn) { (this.listeners[t] = this.listeners[t] || []).push(fn); },
    get classList() {
      const s = this.classes;
      return { add: (c) => s.add(c), remove: (c) => s.delete(c), contains: (c) => s.has(c),
               toggle: (c, on) => { if (on === undefined) { s.has(c) ? s.delete(c) : s.add(c); }
                                    else if (on) s.add(c); else s.delete(c); } };
    },
    descendants() { let o = []; for (const c of this.children) { o.push(c); o = o.concat(c.descendants()); } return o; },
    matches(sel) {
      if (sel === '.cmd-item') return this.classes.has('cmd-item');
      if (sel === '.ws-suggest-item') return this.classes.has('ws-suggest-item');
      throw new Error('atrapa nie zna selektora ' + sel);
    },
    querySelectorAll(sel) { return this.descendants().filter((d) => d.matches(sel)); },
    querySelector(sel) { return this.querySelectorAll(sel)[0] || null; },
    scrollIntoView() {},
  };
}

const el = {};
const ctx = {
  window: {},
  document: { activeElement: null, createElement: (t) => mkEl(t),
              getElementById: (id) => el[id] || null,
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
vm.runInContext("function $(id){return document.getElementById(id);} function t(k){return null;}", ctx);

function wytnij(plik, nazwa) {
  const src = fs.readFileSync(plik, 'utf8');
  const start = src.indexOf('function ' + nazwa + '(');
  if (start < 0) throw new Error('brak funkcji ' + nazwa + ' w ' + plik);
  let g = 0;
  for (let j = src.indexOf('{', start); j < src.length; j++) {
    if (src[j] === '{') g++;
    else if (src[j] === '}') { g--; if (!g) return src.slice(start, j + 1); }
  }
  throw new Error('nie domknalem ' + nazwa);
}

// UWAGA: `var`, nie `let`. W node vm `let` tworzy powiazanie leksykalne, ktore
// NIE jest wlasciwoscia kontekstu - ustawienie ctx._cmdSelectedIdx z zewnatrz
// byloby wtedy niewidoczne dla funkcji i test raportowalby falszywe padniecia
// dzialajacego kodu (zmierzone przy budowie tego testu).
vm.runInContext('var _cmdSelectedIdx=-1;', ctx);
vm.runInContext(wytnij(CMD_PATH, '_syncCmdDropdownA11y'), ctx);
vm.runInContext(wytnij(CMD_PATH, 'navigateCmdDropdown'), ctx);
vm.runInContext(wytnij(CMD_PATH, 'hideCmdDropdown'), ctx);
vm.runInContext(wytnij(PAN_PATH, '_highlightWorkspaceSuggestion'), ctx);

const out = {};

// ── lista podpowiedzi komend ──────────────────────────────────────────────
const pole = mkEl('textarea'); el.msg = pole;
const dd = mkEl('div'); el.cmdDropdown = dd;
dd.classList.add('open');
const poz = [];
for (let i = 0; i < 4; i++) {
  const it = mkEl('div'); it.classList.add('cmd-item');
  if (i === 0) it.classList.add('selected');
  dd.appendChild(it); poz.push(it);
}
ctx._cmdSelectedIdx = 0;
ctx._syncCmdDropdownA11y();
out.komendyStart = {
  rolaListy: dd.getAttribute('role'),
  wszystkieOption: poz.every((p) => p.getAttribute('role') === 'option'),
  rolaPola: pole.getAttribute('role'),
  expanded: pole.getAttribute('aria-expanded'),
  autocomplete: pole.getAttribute('aria-autocomplete'),
  wskazujeWybrana: pole.getAttribute('aria-activedescendant') === poz[0].id && !!poz[0].id,
  pierwszaSelected: poz[0].getAttribute('aria-selected'),
  pozostaleNieSelected: poz.slice(1).every((p) => p.getAttribute('aria-selected') === 'false'),
  wskazujeListe: pole.getAttribute('aria-controls') === dd.id && !!dd.id,
};

ctx.navigateCmdDropdown(1);
out.komendyPoStrzalce = {
  wskazujeDruga: pole.getAttribute('aria-activedescendant') === poz[1].id,
  ariaZgodneZCss: poz[1].classes.has('selected')
                  && poz[1].getAttribute('aria-selected') === 'true'
                  && !poz[0].classes.has('selected')
                  && poz[0].getAttribute('aria-selected') === 'false',
};

ctx._cmdSelectedIdx = 0;
ctx.navigateCmdDropdown(-1);
out.komendyZawijanie = { wskazujeOstatnia: pole.getAttribute('aria-activedescendant') === poz[3].id };

ctx.hideCmdDropdown();
out.komendyPoUkryciu = {
  brakWskaznika: !pole.getAttribute('aria-activedescendant'),
  expanded: pole.getAttribute('aria-expanded'),
};

// ── lista podpowiedzi sciezek ─────────────────────────────────────────────
const polePath = mkEl('input'); el.workspaceFormPath = polePath;
const box = mkEl('div'); el.workspaceFormPathSuggestions = box;
const sug = [];
for (let i = 0; i < 3; i++) { const it = mkEl('button'); it.classList.add('ws-suggest-item'); box.appendChild(it); sug.push(it); }

ctx._highlightWorkspaceSuggestion(1);
out.sciezki = {
  rolaListy: box.getAttribute('role'),
  rolaPola: polePath.getAttribute('role'),
  wskazujeWybrana: polePath.getAttribute('aria-activedescendant') === sug[1].id && !!sug[1].id,
  ariaZgodneZCss: sug[1].classes.has('active')
                  && sug[1].getAttribute('aria-selected') === 'true'
                  && sug[0].getAttribute('aria-selected') === 'false',
};
const idPrzed = sug[1].id;
ctx._highlightWorkspaceSuggestion(-1);
out.sciezkiBezWyboru = { brakWskaznika: !polePath.getAttribute('aria-activedescendant') };
ctx._highlightWorkspaceSuggestion(1);
ctx._highlightWorkspaceSuggestion(1);
out.sciezkiIdempotencja = { idStabilne: sug[1].id === idPrzed };

console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def zachowanie(tmp_path_factory):
    if not NODE:
        pytest.skip("node niedostepny - nie da sie zmierzyc zachowania")
    skrypt = tmp_path_factory.mktemp("listy") / "harness.js"
    skrypt.write_text(
        f"const A11Y_PATH = {json.dumps(str(REPO / 'static' / 'a11y-helpers.js'))};\n"
        f"const CMD_PATH = {json.dumps(str(REPO / 'static' / 'commands.js'))};\n"
        f"const PAN_PATH = {json.dumps(str(REPO / 'static' / 'panels.js'))};\n" + HARNESS,
        encoding="utf-8",
    )
    proc = subprocess.run([NODE, str(skrypt)], capture_output=True, text=True, timeout=90)
    assert proc.returncode == 0, f"harness padl: {proc.stderr[-2000:]}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


class TestPodpowiedziKomend:
    def test_lista_jest_listą_wyboru_dla_czytnika(self, zachowanie):
        s = zachowanie["komendyStart"]
        assert s["rolaListy"] == "listbox", (
            "bez role=listbox czytnik widzi zbior divow, a nie liste wyboru"
        )
        assert s["wszystkieOption"], "pozycje musza miec role=option"

    def test_pole_jest_polaczone_z_lista(self, zachowanie):
        s = zachowanie["komendyStart"]
        assert s["rolaPola"] == "combobox"
        assert s["expanded"] == "true"
        assert s["autocomplete"] == "list"
        assert s["wskazujeListe"], "brak aria-controls laczacego pole z lista"

    def test_wybrana_pozycja_jest_oglaszana_od_razu(self, zachowanie):
        """Lista otwiera sie z wybrana pierwsza pozycja - zanim ktos ruszy strzalka."""
        s = zachowanie["komendyStart"]
        assert s["wskazujeWybrana"], (
            "bez aria-activedescendant czytnik milczy, bo fokus zostaje w polu"
        )
        assert s["pierwszaSelected"] == "true"
        assert s["pozostaleNieSelected"]

    def test_strzalka_przesuwa_oglaszana_pozycje(self, zachowanie):
        p = zachowanie["komendyPoStrzalce"]
        assert p["wskazujeDruga"], "wskaznik musi isc za wyborem"
        assert p["ariaZgodneZCss"], (
            "to, co widac (klasa .selected), i to, co slychac, musi byc tym samym"
        )

    def test_zawijanie_listy_tez_jest_oglaszane(self, zachowanie):
        assert zachowanie["komendyZawijanie"]["wskazujeOstatnia"]

    def test_po_zwinieciu_pole_nie_wskazuje_znikniętej_pozycji(self, zachowanie):
        u = zachowanie["komendyPoUkryciu"]
        assert u["brakWskaznika"], (
            "aria-activedescendant wskazujacy usunięty element to zepsuty kontrakt"
        )
        assert u["expanded"] == "false"


class TestPodpowiedziSciezek:
    def test_lista_jest_listą_wyboru(self, zachowanie):
        s = zachowanie["sciezki"]
        assert s["rolaListy"] == "listbox"
        assert s["rolaPola"] == "combobox"

    def test_wybrana_podpowiedz_jest_oglaszana(self, zachowanie):
        s = zachowanie["sciezki"]
        assert s["wskazujeWybrana"]
        assert s["ariaZgodneZCss"]

    def test_brak_wyboru_czysci_wskaznik(self, zachowanie):
        assert zachowanie["sciezkiBezWyboru"]["brakWskaznika"]

    def test_powtorne_wywolanie_nie_zmienia_identyfikatorow(self, zachowanie):
        assert zachowanie["sciezkiIdempotencja"]["idStabilne"], (
            "niestabilne id psuje aria-activedescendant miedzy odswiezeniami"
        )


class TestWszystkieSciezkiZmianyWyboru:
    """Kontrakt musi powstawac wszedzie, gdzie zmienia sie wybor."""

    def test_lista_komend_synchronizuje_sie_w_trzech_miejscach(self):
        # pokazanie listy, nawigacja strzalkami, ukrycie listy (+ definicja)
        assert COMMANDS_JS.count("_syncCmdDropdownA11y(") >= 4, (
            "kontrakt musi byc odswiezany przy pokazaniu, nawigacji i ukryciu listy"
        )

    def test_podpowiedzi_sciezek_czyszcza_kontrakt_przy_zamknieciu(self):
        idx = PANELS_JS.find("function closeWorkspacePathSuggestions(")
        assert idx > 0
        assert "a11yActiveDescendantList" in PANELS_JS[idx:idx + 700], (
            "zamkniecie listy musi wyczyscic aria-activedescendant"
        )


class TestTlumaczenia:
    def test_nazwy_list_sa_we_wszystkich_locale(self):
        for klucz in ("slash_commands_list_aria", "workspace_path_suggestions_aria"):
            assert I18N_JS.count(klucz) >= 15, (
                f"{klucz}: {I18N_JS.count(klucz)} locale zamiast 15"
            )
