// Harness pomiarowy dla tests/test_a11y_file_tree.py
// Wykonuje PRAWDZIWY kod z static/a11y-helpers.js na atrapie DOM i wypisuje
// zmierzone zachowanie jako JSON w ostatniej linii stdout.
//
// PULAPKA (zmierzona 18.08.2026, trzy razy tego dnia): atrapa, ktora nie zna
// selektora albo metody, powoduje ciche padniecie DZIALAJACEGO kodu - kod
// produkcyjny ma `catch` wokol dekoracji. Dlatego matches() RZUCA na nieznanym
// selektorze, a firstElementChild jest WYLICZANE, nie zapamietane.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const A11Y = path.join(__dirname, '..', 'static', 'a11y-helpers.js');

function mkEl(tag, klasy) {
  return {
    tagName: (tag || 'div').toUpperCase(),
    children: [], attrs: {}, classes: new Set(klasy || []), dataset: {}, id: '',
    style: {}, textContent: '', innerHTML: '', parentNode: null, parentElement: null,
    setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; },
    hasAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k); },
    removeAttribute(k) { delete this.attrs[k]; },
    appendChild(c) { c.parentNode = this; c.parentElement = this; this.children.push(c); return c; },
    insertBefore(c) { c.parentNode = this; c.parentElement = this; this.children.unshift(c); return c; },
    get firstElementChild() { return this.children[0] || null; },
    get firstChild() { return this.children[0] || null; },
    set className(v) { for (const c of String(v || '').split(/\s+/)) if (c) this.classes.add(c); },
    get className() { return Array.from(this.classes).join(' '); },
    addEventListener(t, fn) { (this.listeners = this.listeners || {}); (this.listeners[t] = this.listeners[t] || []).push(fn); },
    getClientRects() { return [{}]; },
    get classList() {
      const s = this.classes;
      return { add: (c) => s.add(c), remove: (c) => s.delete(c), contains: (c) => s.has(c),
               toggle: (c, on) => { if (on) s.add(c); else s.delete(c); } };
    },
    descendants() { let o = []; for (const c of this.children) { o.push(c); o = o.concat(c.descendants()); } return o; },
    matches(sel) {
      if (sel === '[role="treeitem"]') return this.getAttribute('role') === 'treeitem';
      if (sel === '.file-item') return this.classes.has('file-item');
      throw new Error('atrapa nie zna selektora: ' + sel);
    },
    querySelectorAll(sel) { return this.descendants().filter((d) => d.matches(sel)); },
    querySelector(sel) { return this.querySelectorAll(sel)[0] || null; },
    closest() { return null; },
    focus() { ctx.document.activeElement = this; },
    click() { if (this._onclick) this._onclick(); },
  };
}

const rejestr = {};
const ctx = {
  window: {},
  document: { activeElement: null, readyState: 'complete',
              createElement: (t) => mkEl(t),
              getElementById: (id) => rejestr[id] || null,
              querySelector: () => null, querySelectorAll: () => [],
              addEventListener: () => {}, body: mkEl('body') },
  console, Math, JSON, String, Number, Boolean, Array, Object, Date, RegExp, Set, Map,
  requestAnimationFrame: (fn) => fn(),
  setTimeout: () => 0, clearTimeout: () => {}, setInterval: () => 0, clearInterval: () => {},
  MutationObserver: function () { return { observe() {}, disconnect() {} }; },
  location: { href: 'http://127.0.0.1/', search: '' },
};
ctx.window.document = ctx.document;
vm.createContext(ctx);
vm.runInContext('function t(k){return null;}', ctx);
vm.runInContext(fs.readFileSync(A11Y, 'utf8'), ctx);

const out = {};

let row = mkEl('div', ['file-item']);
ctx.a11yTreeRow(row, {level: 1, expandable: true, expanded: false, label: 'folder .cache', focusable: true});
out.katalogZwiniety = {role: row.getAttribute('role'), expanded: row.getAttribute('aria-expanded'),
                       level: row.getAttribute('aria-level'), label: row.getAttribute('aria-label'),
                       tabindex: row.getAttribute('tabindex')};

row = mkEl('div', ['file-item']);
ctx.a11yTreeRow(row, {level: 3, expandable: true, expanded: true, label: 'folder src', focusable: false});
out.katalogRozwiniety = {expanded: row.getAttribute('aria-expanded'),
                         level: row.getAttribute('aria-level'),
                         tabindex: row.getAttribute('tabindex')};

row = mkEl('div', ['file-item']);
ctx.a11yTreeRow(row, {level: 2, expandable: false, label: 'file notes.md', focusable: false});
out.plik = {role: row.getAttribute('role'), maExpanded: row.hasAttribute('aria-expanded'),
            label: row.getAttribute('aria-label')};

const box = mkEl('div');
box.id = 'fileTree';
rejestr['fileTree'] = box;
const wiersze = [];
for (let i = 0; i < 4; i++) {
  const r = mkEl('div', ['file-item']);
  const katalog = i < 2;
  ctx.a11yTreeRow(r, {level: katalog ? 1 : 2, expandable: katalog, expanded: false,
                      label: (katalog ? 'folder k' : 'file p') + i, focusable: i === 0});
  r._onclick = () => { r._klikniety = (r._klikniety || 0) + 1; };
  box.appendChild(r);
  wiersze.push(r);
}
ctx.a11yTree(box, {label: 'Workspace files'});
ctx.a11yTree(box, {label: 'Workspace files'});
ctx.a11yTree(box, {label: 'Workspace files'});
out.kontener = {role: box.getAttribute('role'),
                maNazwe: !!(box.getAttribute('aria-label') || box.getAttribute('aria-labelledby')),
                nasluchowPoTrzechWywolaniach: (box.listeners && box.listeners.keydown || []).length};

const keydown = box.listeners.keydown[0];
const ev = (key) => ({key, preventDefault(){}, stopPropagation(){}});
const nav = {};
ctx.document.activeElement = wiersze[0];
keydown(ev('ArrowDown'));
nav.dolNaDrugi = ctx.document.activeElement === wiersze[1];
nav.rovingPrzeszedl = wiersze[1].getAttribute('tabindex') === '0'
                   && wiersze[0].getAttribute('tabindex') === '-1';
keydown(ev('ArrowUp'));
nav.goraWraca = ctx.document.activeElement === wiersze[0];
keydown(ev('End'));
nav.endNaOstatni = ctx.document.activeElement === wiersze[3];
keydown(ev('Home'));
nav.homeNaPierwszy = ctx.document.activeElement === wiersze[0];
ctx.document.activeElement = wiersze[0];
keydown(ev('ArrowRight'));
nav.prawoRozwija = wiersze[0]._klikniety === 1;
wiersze[0].setAttribute('aria-expanded', 'true');
ctx.document.activeElement = wiersze[0];
keydown(ev('ArrowLeft'));
nav.lewoZwija = wiersze[0]._klikniety === 2;
ctx.document.activeElement = wiersze[3];
keydown(ev('ArrowLeft'));
nav.lewoDoRodzica = ctx.document.activeElement === wiersze[1];
ctx.document.activeElement = wiersze[2];
const przed = wiersze[2]._klikniety || 0;
keydown(ev('Enter'));
nav.enterAktywuje = (wiersze[2]._klikniety || 0) === przed + 1;
out.nawigacja = nav;

const odp = {};
try { ctx.a11yTreeRow(null, {}); ctx.a11yTree(null, {}); odp.nullOk = true; }
catch (e) { odp.nullOk = false; }
const bezOpcji = mkEl('div');
ctx.a11yTreeRow(bezOpcji, {});
odp.bezOpcjiRole = bezOpcji.getAttribute('role');
odp.bezPoziomuMaLevel = bezOpcji.hasAttribute('aria-level');
out.odpornosc = odp;

console.log(JSON.stringify(out));
