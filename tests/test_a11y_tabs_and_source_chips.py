"""Zakladki i plakietki zrodel musza mowic to samo, co pokazuja.

Dwa uchybienia zmierzone 18.08.2026 na dzialajacej aplikacji (Edge + CDP), oba
z tej samej rodziny: informacja istniala WYLACZNIE jako wyglad.

1. Pasek Settings > Extensions mial role="tablist" i trzy role="tab", ale ZERO
   aria-selected, ZERO aria-controls i tablist bez nazwy. Aktywna zakladka byla
   zakodowana tylko klasa CSS (extensions-tab-active), wiec czytnik ekranu mowil
   "zakladka Gallery" i nie mowil, KTORA jest biezaca. WCAG 4.1.2.
   Sasiedni pasek (workspace-panel-tabs) byl poprawny w HTML — czyli defekt to
   ROZJAZD DWOCH KOPII tego samego wzorca, nie brak wiedzy. Dlatego naprawa
   wprowadza wspolny helper a11yTablist zamiast dopisywac atrybuty w trzecim
   miejscu, i dodaje nawigacje strzalkami, ktora rola tab implikuje (ARIA APG).

2. Plakietki zrodla rozmowy (9px) mialy kontrast ponizej progu 4.5:1 dla
   KAZDEGO z czterech kolorow marek. Zmierzone na prawdziwym wierszu listy:
   telegram 2.92:1, discord 2.99:1, slack 1.10:1, claude_code 3.40:1.
   Slack przy 1.1:1 byl praktycznie nieodrozniany od tla. Naprawa rozjasnia
   odcien marki dokladnie tyle, ile ten odcien wymaga, zamiast splaszczac
   wszystko do szarosci — plakietka nadal czyta sie jako "niebieski Telegrama".

Dowody po naprawie (ta sama aparatura): kontrast 4.76 / 4.66 / 4.98 / 4.76,
pelny kontrakt zakladek od PIERWSZEGO wejscia w sekcje (bez klikania), strzalka
w prawo przenosi fokus Gallery -> Installed i przelacza panel, dokladnie jeden
tab ma aria-selected=true i dokladnie jeden jest w kolejnosci Tab.
"""

from pathlib import Path

import json
import re
import shutil
import subprocess

import pytest

REPO = Path(__file__).resolve().parent.parent
A11Y_JS = (REPO / "static" / "a11y-helpers.js").read_text(encoding="utf-8")
PANELS_JS = (REPO / "static" / "panels.js").read_text(encoding="utf-8")
STYLE_CSS = (REPO / "static" / "style.css").read_text(encoding="utf-8")
I18N_JS = (REPO / "static" / "i18n.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


HARNESS = r"""
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync(SRC, 'utf8');

function makeEl(tag){
  const el = {
    tagName: String(tag || 'div').toUpperCase(),
    _attrs: {}, _classes: new Set(), children: [], parentElement: null,
    id: '', textContent: '', hidden: false, _focused: false,
    _listeners: {},
    setAttribute(k, v){ this._attrs[k] = String(v); },
    getAttribute(k){ return k in this._attrs ? this._attrs[k] : null; },
    hasAttribute(k){ return k in this._attrs; },
    removeAttribute(k){ delete this._attrs[k]; },
    classList: null,
    appendChild(c){ c.parentElement = this; this.children.push(c); return c; },
    addEventListener(typ, fn){ (this._listeners[typ] = this._listeners[typ] || []).push(fn); },
    dispatch(typ, ev){ (this._listeners[typ] || []).forEach(fn => fn(ev)); },
    focus(){ ctx.document.activeElement = this; },
    click(){ this.dispatch('click', {}); if (this._onclick) this._onclick(); },
    querySelectorAll(sel){ return descendants(this).filter(e => matches(e, sel)); },
    querySelector(sel){ return this.querySelectorAll(sel)[0] || null; },
    closest(sel){ let e = this; while (e) { if (matches(e, sel)) return e; e = e.parentElement; } return null; },
    dataset: {},
  };
  el.classList = {
    add: c => el._classes.add(c), remove: c => el._classes.delete(c),
    contains: c => el._classes.has(c),
    toggle: (c, on) => { if (on) el._classes.add(c); else el._classes.delete(c); },
  };
  Object.defineProperty(el, 'className', {
    get(){ return Array.from(el._classes).join(' '); },
    set(v){ el._classes = new Set(String(v).split(/\s+/).filter(Boolean)); },
  });
  return el;
}
function descendants(root){
  const out = [];
  (function walk(n){ n.children.forEach(c => { out.push(c); walk(c); }); })(root);
  return out;
}
function matches(el, sel){
  return String(sel).split(',').map(s => s.trim()).some(one => {
    let m = one.match(/^\[role="([^"]+)"\]$/);
    if (m) return el.getAttribute('role') === m[1];
    m = one.match(/^\.([\w-]+)$/);
    if (m) return el._classes.has(m[1]);
    m = one.match(/^\[([\w-]+)="([^"]+)"\]$/);
    if (m) return el.getAttribute(m[1]) === m[2];
    m = one.match(/^\[([\w-]+)\]$/);
    if (m) return el.hasAttribute(m[1]);
    return el.tagName === one.toUpperCase();
  });
}
const root = makeEl('body');
const ctx = {
  console, Date, Math,
  setInterval(){ return 1; }, clearInterval(){}, setTimeout(){ return 1; }, clearTimeout(){},
  document: {
    body: root, activeElement: null, readyState: 'complete',
    getElementById(id){ return descendants(root).find(e => e.id === id) || null; },
    querySelector(sel){ return descendants(root).filter(e => matches(e, sel))[0] || null; },
    querySelectorAll(sel){ return descendants(root).filter(e => matches(e, sel)); },
    createElement(tag){ return makeEl(tag); },
    addEventListener(){},
  },
  window: { addEventListener(){} },
  location: { pathname: '/' },
  t(k){ return k; },
  fetch(){ return Promise.reject(new Error('no network')); },
  __makeEl: makeEl, __root: root,
};
ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(src, ctx);
const out = vm.runInContext(SCENARIO, ctx);
console.log(JSON.stringify(out));
"""


def _run_js(scenario):
    if not NODE:
        pytest.skip("node niedostepny")
    script = (
        HARNESS
        .replace("SRC", json.dumps(str(REPO / "static" / "a11y-helpers.js")))
        .replace("SCENARIO", json.dumps(scenario))
    )
    r = subprocess.run([NODE, "-e", script], capture_output=True, text=True)
    assert r.returncode == 0, f"node failed: {r.stderr[-2500:]}"
    return json.loads(r.stdout)


BUDOWA_PASKA = """
  const bar = __makeEl('div');
  bar.setAttribute('role', 'tablist');
  __root.appendChild(bar);
  const klucze = ['gallery', 'installed', 'diagnostics'];
  const panele = {};
  klucze.forEach(k => {
    const tab = __makeEl('button');
    tab.setAttribute('role', 'tab');
    tab.dataset.extensionsTab = k;
    tab.textContent = k;
    bar.appendChild(tab);
    const panel = __makeEl('div');
    panel.dataset.extensionsPane = k;
    __root.appendChild(panel);
    panele[k] = panel;
  });
  const opcje = (aktywny) => ({
    label: 'Extension views', activeKey: aktywny,
    keyOf: b => b.dataset.extensionsTab,
    panelFor: b => panele[b.dataset.extensionsTab],
  });
"""


class TestTablistHelperDeclaresTheWholeContract:

    def test_every_tab_declares_selected_state(self):
        """Bez aria-selected czytnik nie wie, ktora zakladka jest biezaca."""
        out = _run_js("(() => {" + BUDOWA_PASKA + """
          a11yTablist(bar, opcje('gallery'));
          const taby = bar.querySelectorAll('[role="tab"]');
          return {
            stany: taby.map(x => x.getAttribute('aria-selected')),
            nazwa: bar.getAttribute('aria-label'),
            controls: taby.map(x => x.getAttribute('aria-controls')),
            roleP: taby.map(x => document.getElementById(x.getAttribute('aria-controls')).getAttribute('role')),
          };
        })()""")
        assert out["stany"] == ["true", "false", "false"], (
            "Dokladnie jedna zakladka jest biezaca i KAZDA musi zadeklarowac swoj stan."
        )
        assert out["nazwa"], "tablist bez nazwy nie mowi, czym jest ten zestaw"
        assert all(out["controls"]), "kazdy tab musi wskazywac swoj panel"
        assert out["roleP"] == ["tabpanel"] * 3

    def test_roving_tabindex_keeps_one_stop_in_tab_order(self):
        """Uzytkownik klawiatury nie moze musiec przejsc przez KAZDA zakladke."""
        out = _run_js("(() => {" + BUDOWA_PASKA + """
          a11yTablist(bar, opcje('installed'));
          return {ti: bar.querySelectorAll('[role="tab"]').map(x => x.getAttribute('tabindex'))};
        })()""")
        assert out["ti"] == ["-1", "0", "-1"], (
            "Tylko zakladka biezaca jest w kolejnosci Tab; po zestawie chodzi sie strzalkami."
        )

    def test_arrow_keys_move_and_activate(self):
        """Strzalki sa czescia kontraktu roli tab (ARIA APG: Tabs)."""
        out = _run_js("(() => {" + BUDOWA_PASKA + """
          a11yTablist(bar, opcje('gallery'));
          const taby = bar.querySelectorAll('[role="tab"]');
          let klikniety = null;
          taby.forEach(x => x.addEventListener('click', () => { klikniety = x.dataset.extensionsTab; }));
          taby[0].focus();
          let zablokowane = false;
          bar.dispatch('keydown', {key: 'ArrowRight', preventDefault(){ zablokowane = true; }, stopPropagation(){}});
          const poPrawo = document.activeElement.dataset.extensionsTab;
          bar.dispatch('keydown', {key: 'Home', preventDefault(){}, stopPropagation(){}});
          const poHome = document.activeElement.dataset.extensionsTab;
          taby[0].focus();
          bar.dispatch('keydown', {key: 'ArrowLeft', preventDefault(){}, stopPropagation(){}});
          const poLewo = document.activeElement.dataset.extensionsTab;
          return {poPrawo, poHome, poLewo, klikniety, zablokowane};
        })()""")
        assert out["poPrawo"] == "installed", "strzalka w prawo przechodzi na nastepna zakladke"
        assert out["poLewo"] == "diagnostics", "z pierwszej w lewo wracamy na ostatnia (zawijanie)"
        assert out["poHome"] == "gallery"
        assert out["klikniety"], (
            "Przejscie strzalka musi PRZELACZYC panel — w tej aplikacji klik jest "
            "przelaczeniem, wiec sama zmiana fokusu zostawilaby ARIA i widok rozjechane."
        )
        assert out["zablokowane"] is True, (
            "Bez preventDefault strzalka przewija tez strone pod uzytkownikiem."
        )

    def test_helper_is_idempotent(self):
        """Wolane po kazdym przelaczeniu — nie moze mnozyc nasluchow ani atrybutow."""
        out = _run_js("(() => {" + BUDOWA_PASKA + """
          a11yTablist(bar, opcje('gallery'));
          a11yTablist(bar, opcje('gallery'));
          a11yTablist(bar, opcje('diagnostics'));
          const taby = bar.querySelectorAll('[role="tab"]');
          taby[0].focus();
          let ile = 0;
          taby.forEach(x => x.addEventListener('click', () => { ile++; }));
          bar.dispatch('keydown', {key: 'ArrowRight', preventDefault(){}, stopPropagation(){}});
          return {stany: taby.map(x => x.getAttribute('aria-selected')), klikniec: ile,
                  nasluchow: (bar._listeners.keydown || []).length};
        })()""")
        assert out["stany"] == ["false", "false", "true"], "stan wynika z activeKey, nie narasta"
        assert out["nasluchow"] == 1, "nasluch klawiatury zaklada sie DOKLADNIE raz"
        assert out["klikniec"] == 1, "jedno nacisniecie = jedno przelaczenie"

    def test_state_is_never_left_undeclared(self):
        """Fail closed: bez keyOf i bez isActive stan i tak MUSI byc zadeklarowany."""
        out = _run_js("(() => {" + BUDOWA_PASKA + """
          a11yTablist(bar, {label: 'x'});
          return {stany: bar.querySelectorAll('[role="tab"]').map(x => x.getAttribute('aria-selected'))};
        })()""")
        assert None not in out["stany"], (
            "Brak informacji o wyborze jest gorszy niz 'false' — czytnik milczy o stanie."
        )


class TestExtensionsTabsUseTheSharedMechanism:

    def test_aria_contract_is_declared_where_the_bar_becomes_visible(self):
        """Kontrakt zakladek nie moze zalezec od tego, czy ktorys panel sie wyrenderowal.

        Pierwsza wersja tej naprawy wolala helper w loadExtensionsPanel PO
        `if(!target) return;`, gdzie target to panel DIAGNOSTYKI — wiec wejscie na
        zakladke Gallery wychodzilo z funkcji przed ustawieniem atrybutow.
        Zmierzone na dzialajacej aplikacji: zakladki nadal bez aria-selected.

        Wlasciwe miejsce to switchSettingsSection, gdzie pasek staje sie widoczny,
        i to POZA galezia skipLazyLoad: nawigacja z wyszukiwarki ustawien pokazuje
        ten sam pasek, nie uruchamiajac loadera. Warunek widocznosci i warunek
        dostepnosci musza byc tym samym warunkiem.
        """
        idx = PANELS_JS.find("function switchSettingsSection(")
        assert idx > 0, "brak switchSettingsSection"
        koniec = PANELS_JS.find("\n}", idx)
        cialo = PANELS_JS[idx:koniec]
        kod = "\n".join(
            linia for linia in cialo.splitlines()
            if not linia.strip().startswith(("//", "*", "/*"))
        )
        assert "_extensionsSyncTabsA11y()" in kod, (
            "Kontrakt ARIA musi powstac tam, gdzie sekcja Extensions staje sie widoczna."
        )
        poz_sync = kod.find("_extensionsSyncTabsA11y()")
        poz_lazy = kod.find("if(!(opts&&opts.skipLazyLoad)){")
        poz_koniec_lazy = kod.find("}", kod.find("loadExtensionsPanel();"))
        assert poz_lazy > 0 and poz_koniec_lazy > poz_lazy
        assert poz_sync > poz_koniec_lazy, (
            "Wywolanie stoi w galezi skipLazyLoad — wejscie z wyszukiwarki ustawien "
            "pokazalo by pasek bez zadeklarowanego stanu."
        )

    def test_both_paths_use_one_entry_point(self):
        """Kontrakt nalozony na jednej drodze rozjezdza sie na drugiej."""
        assert "function _extensionsSyncTabsA11y()" in PANELS_JS
        idx = PANELS_JS.find("function switchExtensionsTab(")
        cialo = PANELS_JS[idx:PANELS_JS.find("\n}", idx)]
        assert "_extensionsSyncTabsA11y()" in cialo, (
            "Przelaczanie zakladek musi isc ta sama droga co pierwsze wyrysowanie."
        )
        # helper wolany z jednego miejsca w kazdej drodze, bez kopii atrybutow
        assert "setAttribute('aria-selected'" not in cialo, (
            "Kopia ustawiania atrybutow obok wspolnego helpera to zapowiedz rozjazdu."
        )

    def test_tablist_label_is_translated_everywhere(self):
        """Repo wymaga pokrycia klucza we wszystkich locale (nie tylko 'en')."""
        wystapienia = len(re.findall(r"settings_extensions_tabs_aria\s*:", I18N_JS))
        naglowki = len(re.findall(r"^\s{2}'?[A-Za-z-]+'?\s*:\s*\{", I18N_JS, re.M))
        assert wystapienia >= 15, (
            f"klucz jest w {wystapienia} locale, a plik ma {naglowki} sekcji jezykow — "
            "brakujace tlumaczenie to nasz dlug, nie autora."
        )


class TestSourceChipContrast:
    """Kolor marki nie zwalnia z progu czytelnosci (WCAG 1.4.3)."""

    def test_chip_colours_come_from_one_shared_rule(self):
        idx = STYLE_CSS.find(".session-source-chip[data-source-key]")
        assert idx > 0, "brak wspolnej reguly wyliczajacej kolor plakietki"
        blok = STYLE_CSS[idx:idx + 400]
        assert "color-mix" in blok and "var(--source-hue)" in blok, (
            "Kolor ma byc WYLICZANY z odcienia marki, nie wpisywany osobno per zrodlo."
        )

    def test_every_source_declares_its_hue(self):
        for zrodlo in ("telegram", "discord", "slack", "claude_code"):
            m = re.search(rf'\[data-source-key="{zrodlo}"\][^{{]*\{{([^}}]*)\}}', STYLE_CSS)
            assert m, f"brak deklaracji odcienia dla zrodla {zrodlo}"
            assert "--source-hue" in m.group(1), (
                f"{zrodlo} musi podac odcien przez zmienna, inaczej wypadnie ze wspolnej reguly"
            )

    def test_no_alpha_on_chip_text_colour(self):
        """Alfa na tekscie mnozy sie przez tlo i po cichu zjada kontrast.

        Wlasnie tak te plakietki zeszly do 1.1-3.4:1: kolory byly podane jako
        rgba(...,0.85) na polprzezroczystym tle, wiec zmierzony kontrast byl
        znacznie nizszy, niz sugerowala sama wartosc koloru.
        """
        for zrodlo in ("telegram", "discord", "slack", "claude_code"):
            m = re.search(rf'\[data-source-key="{zrodlo}"\][^{{]*\{{([^}}]*)\}}', STYLE_CSS)
            assert m, f"brak deklaracji odcienia dla zrodla {zrodlo}"
            hue = re.search(r"--source-hue:\s*([^;]+);", m.group(1))
            assert hue, f"{zrodlo}: brak --source-hue"
            assert "rgba" not in hue.group(1).lower(), (
                f"{zrodlo}: odcien z alfa — kontrast bedzie nizszy, niz wyglada"
            )

    def test_unknown_source_is_legible_by_default(self):
        """Nowe zrodlo ma byc czytelne PRZED pomiarem (fail safe)."""
        idx = STYLE_CSS.find(".session-source-chip[data-source-key]")
        blok = STYLE_CSS[idx:idx + 400]
        m = re.search(r"var\(--source-tint-keep,\s*(\d+)%\)", blok)
        assert m, "brak wartosci domyslnej dla --source-tint-keep"
        assert int(m.group(1)) <= 50, (
            "Domyslna wartosc musi odpowiadac NAJCIEMNIEJSZEMU odcieniowi (Slack, 50%), "
            "inaczej nowo dodane zrodlo moze byc nieczytelne, dopoki ktos tego nie zmierzy."
        )
