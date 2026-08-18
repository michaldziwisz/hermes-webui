"""Numery wypowiedzi musza byc GLOBALNE, nie liczone od pierwszego wiersza w DOM.

Zgloszenie (18.08.2026): "w dlugiej sesji numerki sa 1, 2, 3, mimo ze sesja ma
kilkadziesiat wiadomosci; wolalbym, zeby wyliczaly sie globalnie - uzytkownik ma
miec jasny oglad, ze sesja sie rozwija".

WebUI wczytuje tylko ogon rozmowy (wstecz doladowuje sie przyciskiem), a
numeracja naglowkow liczyla od pierwszego wiersza W DOM. Skutki byly dwa i oba
psuja orientacje uzytkownika czytnika ekranu:
 * "1." przy wypowiedzi numer 576 nie mowilo NIC o miejscu w rozmowie,
 * ta sama wypowiedz zmieniala numer po kazdym doladowaniu okna.

ZMIERZONA PULAPKA WSPOLRZEDNYCH: nie wolno tu uzyc surowego
``_messages_offset``, bo on liczy wiersze magazynowe, a numeracja dotyczy
WIDOCZNYCH wypowiedzi. Na zywej sesji: offset 978 dla okna, w ktorym bylo 100
wypowiedzi na 194 wiersze (reszta to wiersze narzedzi zwijane w karty).
Serwer liczy wiec przesuniecie tym SAMYM predykatem
``_message_counts_as_renderable_for_window``, ktory wycial okno.

Zmierzone wlasnosci odpowiedzi serwera (krok130, sesja 576 wypowiedzi):
    okno 10  -> before 566, w oknie 10,  total 576
    okno 30  -> before 546, w oknie 30,  total 576
    okno 100 -> before 476, w oknie 100, total 576
    okno 300 -> before 276, w oknie 300, total 576
czyli numer ostatniej wypowiedzi to 576 NIEZALEZNIE od rozmiaru okna - to jest
sedno zgloszenia.
"""

from pathlib import Path
import json
import shutil
import subprocess

import pytest

REPO = Path(__file__).resolve().parent.parent
A11Y_JS = (REPO / "static" / "a11y-helpers.js").read_text(encoding="utf-8")
ROUTES_PY = (REPO / "api" / "routes.py").read_text(encoding="utf-8")
NODE = shutil.which("node")

# --- czesc serwerowa: liczenie przesuniecia w przestrzeni WIDOCZNYCH wierszy ---

import sys
sys.path.insert(0, str(REPO))


def _wiersze(*role):
    """Buduje liste wierszy: 'u'/'a' = wypowiedz, 't' = wiersz narzedzia."""
    out = []
    for r in role:
        if r == "u":
            out.append({"role": "user", "content": "pytanie"})
        elif r == "a":
            out.append({"role": "assistant", "content": "odpowiedz"})
        else:
            out.append({"role": "tool", "content": "{}", "tool_call_id": "x"})
    return out


class TestLiczeniePrzesunieciaNaSerwerze:
    """``_renderable_count_before`` musi liczyc WYPOWIEDZI, nie wiersze."""

    def test_pomija_wiersze_narzedzi(self):
        from api.routes import _renderable_count_before
        # 10 wierszy, z czego 4 to wypowiedzi
        wiersze = _wiersze("u", "a", "t", "t", "u", "a", "t", "t", "t", "t")
        assert _renderable_count_before(wiersze, 10) == 4, (
            "liczenie surowych wierszy dawaloby 10 i numery rozjechalyby sie "
            "o liczbe wierszy narzedzi"
        )

    def test_zero_i_brak_offsetu(self):
        from api.routes import _renderable_count_before
        wiersze = _wiersze("u", "a")
        assert _renderable_count_before(wiersze, 0) == 0
        assert _renderable_count_before(wiersze, None) == 0

    def test_offset_wiekszy_niz_lista(self):
        from api.routes import _renderable_count_before
        wiersze = _wiersze("u", "a", "t")
        assert _renderable_count_before(wiersze, 999) == 2

    def test_bledne_dane_nie_wywracaja(self):
        from api.routes import _renderable_count_before
        assert _renderable_count_before(None, 5) == 0
        assert _renderable_count_before(_wiersze("u"), "abc") == 0
        assert _renderable_count_before(_wiersze("u"), -3) == 0

    def test_api_session_wystawia_wspolrzedne(self):
        assert '"_visible_turns_before"' in ROUTES_PY
        assert '"_visible_turns_total"' in ROUTES_PY
        idx = ROUTES_PY.find('raw["_visible_turns_before"]')
        assert idx > 0
        assert "_renderable_count_before" in ROUTES_PY[:idx], (
            "przesuniecie musi byc policzone predykatem widocznosci"
        )


# --- czesc przegladarkowa: numeracja naglowkow ---

HARNESS = r"""
const fs = require('fs');
const vm = require('vm');

function mkEl(tag, klasy) {
  const el = {
    tagName: (tag || 'div').toUpperCase(),
    children: [], attrs: {}, classes: new Set(klasy || []), dataset: {}, id: '',
    style: {}, textContent: '', innerHTML: '', parentNode: null, parentElement: null,
    setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; },
    removeAttribute(k) { delete this.attrs[k]; },
    appendChild(c) { c.parentNode = this; c.parentElement = this; this.children.push(c); return c; },
    insertBefore(c) { c.parentNode = this; c.parentElement = this; this.children.unshift(c); return c; },
    // firstElementChild/firstChild MUSZA byc wyliczane: kod wstawia naglowek na
    // poczatek, a zapamietane pole pokazywaloby stale podpis roli.
    get firstElementChild() { return this.children[0] || null; },
    get firstChild() { return this.children[0] || null; },
    set className(v) { for (const c of String(v || '').split(/\s+/)) if (c) this.classes.add(c); },
    get className() { return Array.from(this.classes).join(' '); },
    addEventListener() {}, getClientRects() { return [{}]; },
    get classList() {
      const s = this.classes;
      return { add: (c) => s.add(c), remove: (c) => s.delete(c), contains: (c) => s.has(c),
               toggle: (c, on) => { if (on) s.add(c); else s.delete(c); } };
    },
    descendants() { let o = []; for (const c of this.children) { o.push(c); o = o.concat(c.descendants()); } return o; },
    matches(sel) {
      if (sel === '.msg-row') return this.classes.has('msg-row');
      if (sel === '.msg-role') return this.classes.has('msg-role');
      return false;
    },
    querySelectorAll(sel) { return this.descendants().filter((d) => d.matches(sel)); },
    querySelector(sel) { return this.querySelectorAll(sel)[0] || null; },
    closest() { return null; },
    cloneNode() {
      const k = mkEl(this.tagName, Array.from(this.classes));
      k.textContent = this.textContent;
      k.attrs = Object.assign({}, this.attrs);
      k.dataset = Object.assign({}, this.dataset);
      for (const c of this.children) k.appendChild(c.cloneNode(true));
      return k;
    },
    remove() {
      const p = this.parentNode;
      if (p) p.children = p.children.filter((c) => c !== this);
    },
  };
  return el;
}

const messages = mkEl('div');
messages.id = 'messages';
const rejestr = { messages };
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
  setTimeout: () => 0, clearTimeout: () => {}, setInterval: () => 0, clearInterval: () => {},
  MutationObserver: function () { return { observe() {}, disconnect() {} }; },
  location: { href: 'http://127.0.0.1/', search: '' },
  fetch: async () => ({ ok: false }),
};
ctx.window.document = ctx.document;
vm.createContext(ctx);
vm.runInContext("function t(k){return null;}", ctx);
vm.runInContext(fs.readFileSync(A11Y_PATH, 'utf8'), ctx);

function zbudujOkno(n) {
  messages.children.length = 0;
  for (let i = 0; i < n; i++) {
    const row = mkEl('div', ['msg-row']);
    row.dataset.role = (i % 2 === 0) ? 'user' : 'assistant';
    if (i % 2 === 1) row.classes.add('assistant-turn');
    const rola = mkEl('span', ['msg-role']);
    rola.setAttribute('title', '18.08.2026, 09:15:25');
    rola.textContent = row.dataset.role === 'user' ? 'You' : 'Hermes';
    row.appendChild(rola);
    messages.appendChild(row);
  }
}

function numery() {
  return messages.children
    .map((r) => (r.firstElementChild && r.firstElementChild.textContent) || '')
    .filter((s) => s);
}

const out = {};

zbudujOkno(3);
ctx.a11ySetTurnNumbering(0, 3);
out.krotka = numery();

zbudujOkno(3);
ctx.a11ySetTurnNumbering(573, 576);
out.dluga = numery();

zbudujOkno(6);
ctx.a11ySetTurnNumbering(570, 576);
out.poDoladowaniu = numery();

zbudujOkno(2);
ctx.a11ySetTurnNumbering(0, 2);
out.przedZmiana = numery();
ctx.a11ySetTurnNumbering(100, 102);
out.poZmianie = numery();
const a = numery().join('|');
ctx.a11ySetTurnNumbering(100, 102);
out.idempotentne = (a === numery().join('|'));

zbudujOkno(2);
ctx.a11ySetTurnNumbering(undefined, undefined);
out.brakDanych = numery();
ctx.a11ySetTurnNumbering(-5, -1);
out.ujemne = numery();
ctx.a11ySetTurnNumbering('abc', 'xyz');
out.tekst = numery();
ctx.a11ySetTurnNumbering(10.7, 20.2);
out.niecalkowite = numery();

zbudujOkno(1);
ctx.a11ySetTurnNumbering(42, 60);
const h = messages.children[0].firstElementChild;
out.naglowek = { tag: h && h.tagName, tekst: h && h.textContent };

console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def zachowanie(tmp_path_factory):
    if not NODE:
        pytest.skip("node niedostepny - nie da sie zmierzyc zachowania")
    skrypt = tmp_path_factory.mktemp("num") / "harness.js"
    skrypt.write_text(
        f"const A11Y_PATH = {json.dumps(str(REPO / 'static' / 'a11y-helpers.js'))};\n"
        + HARNESS,
        encoding="utf-8",
    )
    proc = subprocess.run([NODE, str(skrypt)], capture_output=True, text=True, timeout=90)
    assert proc.returncode == 0, f"harness padl: {proc.stderr[-2000:]}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


class TestNumeracjaGlobalna:
    def test_dluga_sesja_nie_zaczyna_od_jednego(self, zachowanie):
        """Sedno zgloszenia: okno 3 wypowiedzi, 573 ukryte -> numery 574-576."""
        d = zachowanie["dluga"]
        assert d[0].startswith("574"), f"pierwszy naglowek: {d[0]}"
        assert d[-1].startswith("576"), f"ostatni naglowek: {d[-1]}"

    def test_krotka_sesja_numeruje_od_jednego(self, zachowanie):
        assert zachowanie["krotka"][0].startswith("1")

    def test_pierwszy_naglowek_podaje_ile_jest_razem(self, zachowanie):
        """Uzytkownik ma widziec, ze sesja sie rozwija."""
        assert "/576" in zachowanie["dluga"][0]

    def test_pozostale_naglowki_nie_powtarzaja_sumy(self, zachowanie):
        """Suma przy kazdym naglowku byla gadatliwa przy skakaniu po naglowkach."""
        for n in zachowanie["dluga"][1:]:
            assert "/576" not in n, f"naglowek powtarza sume: {n}"


class TestDoladowanieWstecz:
    def test_numery_starszych_wypowiedzi_nie_skacza(self, zachowanie):
        """Ta sama wypowiedz musi miec ten sam numer po doladowaniu."""
        assert zachowanie["poDoladowaniu"][-1].startswith("576"), (
            f"ostatni po doladowaniu: {zachowanie['poDoladowaniu'][-1]}"
        )

    def test_nowo_odsloniete_maja_nizsze_numery(self, zachowanie):
        assert zachowanie["poDoladowaniu"][0].startswith("571")

    def test_suma_sie_nie_zmienia(self, zachowanie):
        assert "/576" in zachowanie["poDoladowaniu"][0]

    def test_zmiana_przesuniecia_przelicza_istniejace_naglowki(self, zachowanie):
        """Bez przeliczenia doladowanie zostawiloby stare numery."""
        assert zachowanie["przedZmiana"][0] != zachowanie["poZmianie"][0]
        assert zachowanie["poZmianie"][0].startswith("101")

    def test_powtorne_ustawienie_nic_nie_zmienia(self, zachowanie):
        assert zachowanie["idempotentne"] is True


class TestOdpornoscNaBledneDane:
    """Brak lub zle dane nie moga zepsuc numeracji - lepiej lokalna niz zadna."""

    def test_brak_danych_daje_numeracje_lokalna(self, zachowanie):
        assert zachowanie["brakDanych"][0].startswith("1")

    def test_liczby_ujemne_odrzucone(self, zachowanie):
        assert zachowanie["ujemne"][0].startswith("1")

    def test_tekst_zamiast_liczby_odrzucony(self, zachowanie):
        assert zachowanie["tekst"][0].startswith("1")

    def test_liczby_niecalkowite_obcinane(self, zachowanie):
        assert zachowanie["niecalkowite"][0].startswith("11")


class TestNaglowekJestCzytelnyDlaCzytnika:
    def test_naglowek_to_h2(self, zachowanie):
        assert zachowanie["naglowek"]["tag"] == "H2"

    def test_naglowek_zawiera_globalny_numer(self, zachowanie):
        assert zachowanie["naglowek"]["tekst"].startswith("43")


class TestWszystkieSciezkiWczytaniaOkna:
    """Numeracja musi byc ustawiana wszedzie, gdzie zmienia sie okno."""

    def test_wszystkie_miejsca_ustawiaja_numeracje(self):
        trafienia = 0
        for nazwa in ("messages.js", "sessions.js", "ui.js"):
            trafienia += (REPO / "static" / nazwa).read_text(
                encoding="utf-8").count("a11ySetTurnNumbering(")
        assert trafienia >= 4, (
            f"tylko {trafienia} wpiec - okno zmienia sie w czterech miejscach "
            "(pelne wczytanie, doladowanie wstecz, odswiezenie, przelaczenie sesji)"
        )

    def test_doladowanie_wstecz_ma_wpiecie(self):
        sessions = (REPO / "static" / "sessions.js").read_text(encoding="utf-8")
        idx = sessions.find("_oldestIdx = responseSession._messages_offset")
        assert idx > 0
        assert "a11ySetTurnNumbering" in sessions[idx:idx + 600], (
            "bez tego doladowanie starszych wiadomosci zostawiloby stare numery"
        )
