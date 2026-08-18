/* Wspolne narzedzia dostepnosci (a11y).
 *
 * Powstalo przy naprawie ustalen audytu dostepnosci (WCAG 2.2 / EN 301 549).
 * Celowo jeden modul, zeby ten sam wzorzec nie byl kopiowany w kilku miejscach
 * — zdublowany wzorzec byl przyczyna czesci defektow (jedno okno mialo
 * przytrzymanie fokusu, blizniacze nie).
 */

/* Przytrzymanie fokusu w oknie modalnym + odizolowanie tla od czytnikow ekranu.
 *
 * Zwraca funkcje sprzatajaca: odpina nasluch, przywraca tlo i oddaje fokus
 * elementowi, ktory mial go przed otwarciem okna (WCAG 2.4.3).
 */
function a11yTrapFocus(modalEl, opts){
  if (!modalEl) return () => {};
  const options = opts || {};
  const previouslyFocused = (document.activeElement instanceof HTMLElement)
    ? document.activeElement
    : null;

  const selector = 'a[href], button, textarea, input, select, summary, [tabindex]:not([tabindex="-1"])';
  const collect = () => Array.from(modalEl.querySelectorAll(selector)).filter((el) => {
    if (el.disabled || el.hidden) return false;
    const style = getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') return false;
    return el.tabIndex >= 0;
  });

  // Tlo poza oknem: inert wyjmuje je z kolejnosci tabulacji I z drzewa dostepnosci.
  const isolated = [];
  if (options.isolateBackground !== false) {
    Array.from(document.body.children).forEach((el) => {
      if (el === modalEl || el.contains(modalEl)) return;
      if (el.tagName === 'SCRIPT' || el.tagName === 'STYLE' || el.tagName === 'TEMPLATE') return;
      if (el.hasAttribute('inert')) return;
      el.setAttribute('inert', '');
      el.setAttribute('data-a11y-inert', '1');
      isolated.push(el);
    });
  }

  const onKeyDown = (ev) => {
    if (ev.key !== 'Tab') return;
    const focusableEls = collect();
    if (!focusableEls.length) { ev.preventDefault(); return; }
    const current = document.activeElement;
    let idx = focusableEls.indexOf(current);
    if (idx === -1) {
      ev.preventDefault();
      focusableEls[0].focus();
      return;
    }
    idx = ev.shiftKey ? idx - 1 : idx + 1;
    idx = (idx + focusableEls.length) % focusableEls.length;
    ev.preventDefault();
    focusableEls[idx].focus();
  };
  modalEl.addEventListener('keydown', onKeyDown);

  // Fokus startowy: wskazany element, pierwsze pole, albo pierwsza kontrolka.
  if (options.autofocus !== false) {
    setTimeout(() => {
      let target = null;
      if (options.initialFocus) {
        target = (typeof options.initialFocus === 'string')
          ? modalEl.querySelector(options.initialFocus)
          : options.initialFocus;
      }
      if (!target) target = collect()[0] || null;
      if (target && typeof target.focus === 'function') target.focus();
    }, 0);
  }

  return () => {
    modalEl.removeEventListener('keydown', onKeyDown);
    isolated.forEach((el) => {
      el.removeAttribute('inert');
      el.removeAttribute('data-a11y-inert');
    });
    if (options.restoreFocus !== false && previouslyFocused
        && document.contains(previouslyFocused)
        && typeof previouslyFocused.focus === 'function') {
      try { previouslyFocused.focus(); } catch (_e) { /* element zniknal */ }
    }
  };
}

/* Stan wybrania w grupie przyciskow, ktora wizualnie oznacza wybor klasa CSS.
 *
 * Naprawia wzorzec "stan tylko klasa CSS" — dla czytnika ekranu klasa nie
 * istnieje, wiec bez aria-pressed uzytkownik nie wie, ktora opcja jest aktywna.
 */
function a11ySyncPressedState(container, itemSelector, activeClass){
  if (!container) return;
  const cls = activeClass || 'active';
  const items = Array.from(container.querySelectorAll(itemSelector || 'button'));
  items.forEach((el) => {
    el.setAttribute('aria-pressed', el.classList.contains(cls) ? 'true' : 'false');
  });
}

/* Nazwa dostepna dla pola formularza, ktore ma opis wylacznie obok (w div),
 * albo tylko tekst zastepczy. Nie zmienia wygladu.
 */
function a11yLabel(el, text){
  if (!el || !text) return;
  const clean = String(text).replace(/\s+/g, ' ').trim();
  if (!clean) return;
  if (!el.getAttribute('aria-label') && !el.getAttribute('aria-labelledby')) {
    el.setAttribute('aria-label', clean);
  }
}

/* Jednorazowy komunikat dla czytnika ekranu (obszar aktywny #a11yAnnouncer). */
function a11yAnnounce(text){
  const region = document.getElementById('a11yAnnouncer');
  if (!region || !text) return;
  region.textContent = '';
  setTimeout(() => { region.textContent = String(text); }, 50);
}

/* Element klikalny, ktory NIE jest kontrolka — nadaj mu role i klawiature.
 *
 * Wzorzec "div/span z onclick" nie mowi czytnikowi ekranu nic: uzytkownik nie
 * wie, ze cokolwiek da sie tu zrobic, i nie dojdzie tam tabulacja (WCAG 4.1.2
 * nazwa/rola/wartosc oraz 2.1.1 dostep z klawiatury).
 *
 * Celowo JEDEN helper na caly panel: obsluga Enter/Spacji rozpisana osobno przy
 * kazdym elemencie rozjezdza sie od pierwszej poprawki (czesc dostaje tylko
 * Enter, czesc nic), a to wlasnie rozjazd kopii byl zrodlem defektow.
 */
function a11yAsButton(el, opts){
  if (!el || typeof el.setAttribute !== 'function') return el;
  const options = opts || {};
  el.setAttribute('role', 'button');
  if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '0');
  if (options.label) a11yLabel(el, options.label);
  if (options.expanded !== undefined && options.expanded !== null) {
    el.setAttribute('aria-expanded', options.expanded ? 'true' : 'false');
  }
  if (options.pressed !== undefined && options.pressed !== null) {
    el.setAttribute('aria-pressed', options.pressed ? 'true' : 'false');
  }
  if (el.dataset && el.dataset.a11yKeyActivated === '1') return el;
  if (el.dataset) el.dataset.a11yKeyActivated = '1';
  el.addEventListener('keydown', (ev) => {
    if (ev.key !== 'Enter' && ev.key !== ' ' && ev.key !== 'Spacebar') return;
    // Spacja na elemencie zastepczym przewija strone — to trzeba wstrzymac,
    // inaczej aktywacja z klawiatury przesuwa widok pod uzytkownikiem.
    ev.preventDefault();
    ev.stopPropagation();
    if (typeof options.onActivate === 'function') { options.onActivate(ev); return; }
    if (typeof el.click === 'function') el.click();
  });
  return el;
}

/* Wiersz, ktory PRZENOSI do innego widoku (rozmowa, dokument) — prawdziwy link.
 *
 * Rola "link" zamiast "button" jest tu istotna: czytnik ekranu ma osobna
 * nawigacje po linkach (K w NVDA, lista linkow), a uzytkownik slyszy, ze to
 * przejscie, nie akcja na miejscu. Warunek: `href` musi byc adresem, ktory
 * REALNIE otwiera ten widok, inaczej link jest atrapa — otwarcie w nowej karcie
 * i menu kontekstowe przegladarki musza dawac ten sam docelowy ekran.
 *
 * Dostajemy przy tym gratis wzorce, ktorych aplikacja nie musi kodowac:
 * Ctrl+klik / srodkowy przycisk (nowa karta) i "kopiuj adres odnosnika".
 */
function a11yAsLink(el, href, opts){
  if (!el || typeof el.setAttribute !== 'function') return el;
  const options = opts || {};
  el.setAttribute('role', 'link');
  if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '0');
  if (href) el.setAttribute('data-href', href);
  if (options.label) a11yLabel(el, options.label);
  if (options.current) el.setAttribute('aria-current', 'page');
  else if (el.hasAttribute('aria-current')) el.removeAttribute('aria-current');
  if (el.dataset && el.dataset.a11yKeyActivated === '1') return el;
  if (el.dataset) el.dataset.a11yKeyActivated = '1';
  el.addEventListener('keydown', (ev) => {
    // Link reaguje na Enter; Spacja nalezy do przycisku i tu jej nie przechwytujemy,
    // zeby zachowanie zgadzalo sie z natywnym <a href>.
    if (ev.key !== 'Enter') return;
    ev.preventDefault();
    ev.stopPropagation();
    if (typeof options.onActivate === 'function') { options.onActivate(ev); return; }
    if (typeof el.click === 'function') el.click();
  });
  return el;
}

/* Zestaw zakladek (tablist) — JEDEN mechanizm dla wszystkich pasków zakladek.
 *
 * Zmierzony defekt (18.08.2026): pasek Settings > Extensions mial role="tablist"
 * i trzy role="tab", ale ZERO aria-selected, ZERO aria-controls i tablist bez
 * nazwy. Czytnik mowil wiec "zakladka Gallery" i NIE MOWIL, ktora jest aktywna —
 * a stan aktywnosci istnial tylko jako klasa CSS (extensions-tab-active), czyli
 * informacja dostepna wylacznie dla osoby widzacej. WCAG 4.1.2.
 *
 * Sasiedni pasek (workspace-panel-tabs) byl zrobiony poprawnie w HTML, wiec to
 * jest rozjazd DWOCH KOPII tego samego wzorca — dokladnie ta klasa bledu, ktora
 * naprawialismy juz przy klikalnych elementach panelu. Zamiast dopisac brakujace
 * atrybuty w trzecim miejscu, wprowadzamy wspolny helper: kazdy pasek dostaje
 * nazwe, kazdy tab aria-selected/aria-controls, panele role="tabpanel", a caly
 * zestaw nawigacje strzalkami z jednym tabem w kolejnosci Tab (roving tabindex).
 *
 * Strzalki sa czescia KONTRAKTU roli tab: skoro mowimy czytnikowi "to zakladki",
 * uzytkownik probuje strzalek i bez nich zostaje w pulapce (ARIA APG: Tabs).
 *
 * Wywolanie jest IDEMPOTENTNE — mozna je powtarzac po kazdym przelaczeniu, bo
 * stan wynika z przekazanego `activeKey`, a nasluch klawiatury zaklada sie raz.
 */
function a11yTablist(tablist, opts){
  if (!tablist || typeof tablist.querySelectorAll !== 'function') return tablist;
  const options = opts || {};
  const taby = Array.from(tablist.querySelectorAll('[role="tab"]'));
  if (!taby.length) return tablist;
  if (options.label) a11yLabel(tablist, options.label);
  if (!tablist.getAttribute('role')) tablist.setAttribute('role', 'tablist');

  const kluczTabu = (el) => (typeof options.keyOf === 'function' ? options.keyOf(el) : null);
  const aktywny = options.activeKey;

  taby.forEach((tab) => {
    const klucz = kluczTabu(tab);
    // Gdy wolajacy nie umie podac klucza, opieramy sie na klasie aktywnosci —
    // ale NIGDY nie zostawiamy aria-selected niezadeklarowanego.
    const czyAktywny = (klucz !== null && aktywny !== undefined)
      ? String(klucz) === String(aktywny)
      : (typeof options.isActive === 'function' ? !!options.isActive(tab) : false);
    tab.setAttribute('aria-selected', czyAktywny ? 'true' : 'false');
    // Roving tabindex: tylko aktywny tab jest w kolejnosci Tab, po zestawie
    // chodzi sie strzalkami. Bez tego uzytkownik klawiatury musi przejsc przez
    // KAZDA zakladke, zeby wyjsc z paska.
    tab.setAttribute('tabindex', czyAktywny ? '0' : '-1');
    const panel = (typeof options.panelFor === 'function') ? options.panelFor(tab) : null;
    if (panel) {
      if (!panel.id) panel.id = `a11yTabPanel_${Math.random().toString(36).slice(2, 9)}`;
      tab.setAttribute('aria-controls', panel.id);
      if (!panel.getAttribute('role')) panel.setAttribute('role', 'tabpanel');
      if (!tab.id) tab.id = `a11yTab_${Math.random().toString(36).slice(2, 9)}`;
      // Panel bierze nazwe od AKTYWNEJ zakladki. Ma to znaczenie, gdy kilka
      // zakladek przelacza zawartosc JEDNEGO kontenera (tak dziala pasek
      // Full/Output w kartach narzedzi: tryb "output" tylko ukrywa argumenty
      // w tym samym elemencie). Gdybysmy zostawili nazwe pierwszej zakladki,
      // czytnik po przejsciu na "Output" nadal mowilby "Full" — czyli panel
      // klamalby o tym, co pokazuje. Przy osobnych panelach zachowanie jest
      // takie jak dotad: kazdy panel nazywa sie swoja zakladka.
      if (czyAktywny || !panel.hasAttribute('aria-labelledby')) {
        panel.setAttribute('aria-labelledby', tab.id);
      }
    }
  });

  if (tablist.dataset && tablist.dataset.a11yTablistKeys === '1') return tablist;
  if (tablist.dataset) tablist.dataset.a11yTablistKeys = '1';
  tablist.addEventListener('keydown', (ev) => {
    const kolejnosc = Array.from(tablist.querySelectorAll('[role="tab"]'));
    const teraz = kolejnosc.indexOf(document.activeElement);
    if (teraz < 0) return;
    let cel = null;
    if (ev.key === 'ArrowRight' || ev.key === 'ArrowDown') cel = (teraz + 1) % kolejnosc.length;
    else if (ev.key === 'ArrowLeft' || ev.key === 'ArrowUp') cel = (teraz - 1 + kolejnosc.length) % kolejnosc.length;
    else if (ev.key === 'Home') cel = 0;
    else if (ev.key === 'End') cel = kolejnosc.length - 1;
    else return;
    ev.preventDefault();
    ev.stopPropagation();
    const docelowy = kolejnosc[cel];
    if (!docelowy) return;
    // Wzorzec "automatic activation": przejscie strzalka OD RAZU przelacza panel,
    // bo tak dziala reszta zakladek w tej aplikacji (klik = przelaczenie).
    docelowy.setAttribute('tabindex', '0');
    if (typeof docelowy.focus === 'function') docelowy.focus();
    if (typeof docelowy.click === 'function') docelowy.click();
  });
  return tablist;
}

/* Lista wyboru sterowana strzalkami (combobox + listbox).
 *
 * Zmierzony defekt (18.08.2026): podpowiedzi komend /slash i podpowiedzi
 * katalogow roboczych maja pelna nawigacje strzalkami, ale wybrana pozycja jest
 * oznaczona WYLACZNIE klasa CSS. Czytnik ekranu nie oglasza wiec niczego przy
 * przechodzeniu po liscie — uzytkownik slyszy cisze i nie wie, co zatwierdzi
 * Enterem. WCAG 4.1.2.
 *
 * To kolejny wariant tej samej klasy bledu (po zakladkach i plakietkach zrodel),
 * a repo ma juz jego poprawne rozwiazanie dla listy modeli (ui.js, _highlightRow:
 * role="option" + aria-selected + aria-activedescendant na polu). Zamiast
 * czwartej kopii tamtej logiki, wystawiamy ja jako wspolny helper.
 *
 * Kontrakt jest calosciowy — sama aria-selected nie wystarczy, bo bez
 * role="listbox"/"option" czytnik nie traktuje tego jak listy wyboru, a bez
 * aria-activedescendant nie oglosi ruchu, skoro fokus zostaje w polu tekstowym.
 *
 * Idempotentny: wolaj po kazdej zmianie wyboru.
 */
function a11yActiveDescendantList(pole, lista, elementy, wybranyIndeks, opts){
  if (!lista || !elementy || !elementy.length) {
    // Lista zwinieta: pole nie moze wskazywac na nieistniejacy element.
    if (pole && typeof pole.removeAttribute === 'function') {
      pole.removeAttribute('aria-activedescendant');
      pole.setAttribute('aria-expanded', 'false');
    }
    return;
  }
  const options = opts || {};
  const prefiks = options.idPrefix || 'a11yOpt';
  if (!lista.getAttribute('role')) lista.setAttribute('role', 'listbox');
  if (options.label) a11yLabel(lista, options.label);

  let wybrany = null;
  for (let i = 0; i < elementy.length; i++) {
    const el = elementy[i];
    if (!el || typeof el.setAttribute !== 'function') continue;
    if (!el.getAttribute('role')) el.setAttribute('role', 'option');
    if (!el.id) el.id = `${prefiks}_${i}_${Math.random().toString(36).slice(2, 7)}`;
    const czyWybrany = i === wybranyIndeks;
    el.setAttribute('aria-selected', czyWybrany ? 'true' : 'false');
    if (czyWybrany) wybrany = el;
  }

  if (!pole || typeof pole.setAttribute !== 'function') return;
  if (!pole.getAttribute('role')) pole.setAttribute('role', 'combobox');
  pole.setAttribute('aria-expanded', 'true');
  pole.setAttribute('aria-autocomplete', 'list');
  if (!lista.id) lista.id = `${prefiks}_lista_${Math.random().toString(36).slice(2, 7)}`;
  pole.setAttribute('aria-controls', lista.id);
  if (wybrany) pole.setAttribute('aria-activedescendant', wybrany.id);
  else pole.removeAttribute('aria-activedescendant');
}

if (typeof window !== 'undefined') {
  window.a11yTrapFocus = a11yTrapFocus;
  window.a11ySyncPressedState = a11ySyncPressedState;
  window.a11yLabel = a11yLabel;
  window.a11yAnnounce = a11yAnnounce;
  window.a11yAsButton = a11yAsButton;
  window.a11yAsLink = a11yAsLink;
  window.a11yTablist = a11yTablist;
  window.a11yActiveDescendantList = a11yActiveDescendantList;
}

/* ── Nawigacja po naglowkach w zapisie rozmowy ────────────────────────────
 *
 * Problem: w dlugiej rozmowie nie da sie szybko przeskakiwac miedzy kolejnymi
 * wypowiedziami. Czytnik ekranu ma do tego gotowe narzedzie — skok po
 * naglowkach (H w NVDA, 2/3 po poziomach) — ale zapis rozmowy nie mial ani
 * jednego naglowka.
 *
 * Rozwiazanie: KAZDA wypowiedz dostaje <h2>, a elementy wewnatrz tury
 * asystenta (rozumowanie, dziennik narzedzi) <h3>. Naglowki sa niewidoczne
 * wizualnie (klasa sr-only) — uklad graficzny nie zmienia sie ani o piksel,
 * bo role sa juz pokazane ikona i podpisem.
 *
 * Dlaczego przez MutationObserver, a nie w funkcjach renderujacych:
 * wiadomosci powstaja kilkoma sciezkami (render ustalony, strumien na zywo,
 * odzysk wierszy z puli, przywracanie tury po przelaczeniu sesji). Dekorowanie
 * w jednym miejscu po fakcie obejmuje wszystkie te sciezki i nie moze sie
 * z zadna rozjechac. To tez powod, dla ktorego nie ruszamy
 * _setLatestAssistantTurnLandmark — jego kontrakt pilnuje test w repozytorium
 * (tests/test_a11y_transcript_landmarks.py): tura nie moze zawierac naglowka
 * dodanego TAM ani byc fokusowalna.
 */

const A11Y_HEAD_MARK = 'a11yHeading';       // dataset marker on our headings
const A11Y_HEAD_DONE = 'a11yHeadingFor';    // signature of what we labelled

/* Elementy, ktore NIE naleza do wypowiedzi i nie moga trafic do wycinka:
 * podpis roli (ikona + nazwa), licznik czasu, przyciski akcji, nasze wlasne
 * naglowki oraz caly dziennik aktywnosci. Bez tego naglowek tury na zywo
 * brzmial "HHermes Processed 1sProcessed 2s" — czyli litera z ikony, nazwa
 * i liczniki sekund, zamiast pierwszych slow odpowiedzi (zmierzone). */
const A11Y_SNIPPET_SKIP = [
  // Podpis roli i jego czesci skladowe. `.role-icon` i `.msg-role-name` sa
  // wymienione OSOBNO, mimo ze normalnie leza w `.msg-role`: ikona roli to
  // pierwsza LITERA nazwy asystenta ("H"), wiec gdy trafi do wycinka poza
  // kontenerem `.msg-role`, naglowek czyta sie "HHermes" — dokladnie taki objaw
  // zglosil uzytkownik. Filtrowanie samego rodzica bylo zalozeniem o strukturze;
  // wymienienie dzieci jest odporne na kazdy uklad znacznikow.
  '.msg-role', '.role-icon', '.msg-role-name',
  '.msg-tps-inline', '.msg-foot', '.msg-actions',
  '.agent-activity-group', '.tool-call-group', '.tool-worklog',
  '.thinking-card', '.msg-files', '[data-a11y-heading]',
];

function _a11ySnippet(row, limit){
  // Prefer the message body; for assistant turns take the rendered blocks but
  // drop the activity log, which is not part of the spoken answer.
  const body = row.querySelector('.msg-body')
    || row.querySelector('.assistant-turn-blocks')
    || row;
  const clone = body.cloneNode(true);
  for (const sel of A11Y_SNIPPET_SKIP) {
    for (const el of Array.from(clone.querySelectorAll(sel))) el.remove();
  }
  const text = (clone.textContent || '').replace(/\s+/g, ' ').trim();
  const max = limit || 70;
  return text.length > max ? text.slice(0, max).replace(/\s+\S*$/, '') + '…' : text;
}

function _a11yRoleLabel(row){
  const role = (row.dataset && row.dataset.role) || '';
  if (role === 'user') {
    return (typeof t === 'function' && t('a11y_turn_you')) || 'You';
  }
  if (role === 'assistant' || row.classList.contains('assistant-turn')) {
    if (typeof assistantDisplayName === 'function') {
      try { return assistantDisplayName(); } catch (_e) { /* fall through */ }
    }
    return 'Hermes';
  }
  return (typeof t === 'function' && t('a11y_turn_system')) || 'System';
}

/* One <h2> per turn: "<n>. <role>: <opening words>".
 * The number and the opening words are what make the heading list usable —
 * a list of twenty identical "Hermes" entries would navigate no better than
 * no headings at all. */
/* Czy ta tura wlasnie powstaje.
 *
 * Pulapka zmierzona: pierwsza wersja pytala o `.thinking-card:not(.done)`, a
 * karty rozumowania w turach ZAKONCZONYCH tez nie maja klasy `done` (5 z 5
 * w zamknietej turze). Kazda tura wygladala wiec na trwajaca. Wiarygodne
 * znaczniki to identyfikator tury na zywo, jawny data-live i kursor strumienia —
 * wszystkie sa wlasnoscia TEJ tury. Globalny stan biegu byl tu kiedys dodatkowa
 * poszlaka dla ostatniej tury i okazal sie szkodliwy (patrz cialo funkcji).
 */
function _a11yTurnIsLive(row){
  const liveTurn = document.getElementById('liveAssistantTurn');
  if (liveTurn && (liveTurn === row || row.contains(liveTurn) || liveTurn.contains(row))) return true;
  if (row.dataset && row.dataset.live === 'true') return true;
  if (row.querySelector('.stream-cursor, .typing-indicator, .msg-streaming')) return true;
  // CELOWO NIE pytamy tu o globalny stan biegu (a11yRunIsActive) jako o dowod,
  // ze ostatnia tura jest zywa. Byla to poszlaka, ktora zamieniala JEDEN
  // pominiety sygnal konca w trwale zawieszenie widoku: uzytkownik zglosil
  // "model skonczy pisac, a widze 5. Hermes, working ... a po odswiezeniu mam
  // wypowiedz". Gdy stan biegu nie zostal zdjety, kazde kolejne przejscie
  // dekoratora uznawalo zamknieta ture za trwajaca, wiec naglowek czytal
  // "working", a _a11yReorderTurn nie przestawial blokow i tresc odpowiedzi
  // zostawala ZA dziennikiem aktywnosci.
  // Znaczniki powyzej sa wlasnoscia TEJ tury i znikaja razem z nia, wiec nie
  // moga sie rozjechac ze stanem globalnym. Jesli zaden z nich nie wystepuje,
  // tura jest zakonczona — nawet gdy licznik biegu zostal gdzies otwarty.
  //
  // WYJATEK, ktory NIE cierpi na ten sam problem: sesja prowadzona z zewnatrz
  // (TUI/Telegram). Nie ma wtedy w dokumencie zadnej tury na zywo — praca dzieje
  // sie w innym procesie — a uzytkownik ma prawo wiedziec, ze cos trwa
  // (zgloszenie: "sesja zyje, ja nie mam informacji, ze zyje"). Roznica wobec
  // usunietej poszlaki jest zasadnicza: `_a11yForeignOwnsRun` NIE zalezy od
  // sygnalu, ktory mozna przeoczyc — watchdog sam go gasi, gdy zmierzy brak
  // przyrostu (A11Y_FOREIGN_DONE_AFTER_MS). Stan nie moze wiec zawisnac.
  // Straz na `typeof`: `_a11yForeignOwnsRun` jest deklarowane przez `let` DALEJ
  // w tym pliku (strefa martwa czasowa). W praktyce ta funkcja rusza dopiero po
  // wczytaniu calego skryptu, ale gole odwolanie rzucaloby ReferenceError, gdyby
  // dekorator zostal kiedys wywolany wczesniej — a wtedy padlby caly render.
  if (typeof _a11yForeignOwnsRun !== 'undefined' && _a11yForeignOwnsRun && !liveTurn) {
    const wszystkie = document.querySelectorAll('#messages .msg-row.assistant-turn');
    if (wszystkie.length && wszystkie[wszystkie.length - 1] === row) return true;
  }
  return false;
}

/* Tekst naglowka tury.
 *
 * Rozne zasady dla obu stron rozmowy, i to jest celowe:
 *
 * - WYPOWIEDZ UZYTKOWNIKA dostaje fragment tresci. Sluzy do orientacji
 *   "gdzie o co pytalem", a polecenia sa krotkie, wiec skrot nie przeszkadza.
 *
 * - ODPOWIEDZ ASYSTENTA dostaje tylko role i godzine. Skracanie dlugiej
 *   odpowiedzi do 70 znakow bylo irytujace: uzytkownik slyszal poszatkowany
 *   poczatek zdania, a potem to samo zdanie jeszcze raz w tresci. Naglowek ma
 *   byc punktem zaczepienia do skoku, nie streszczeniem. Tresc czyta sie
 *   ZARAZ POD naglowkiem (patrz _a11yReorderTurn).
 */
function _a11yTurnHeadingText(row, ordinal, total){
  const label = _a11yRoleLabel(row);
  const isAssistant = (row.dataset && row.dataset.role === 'assistant')
    || row.classList.contains('assistant-turn');

  // "N z M" tylko dla PIERWSZEJ wypowiedzi w oknie, nie dla kazdej.
  //
  // Numer globalny sam mowi, ze rozmowa jest dluga (43. zamiast 1.), ale nie
  // mowi, ILE jest przed nami. Doklejanie "z 576" do KAZDEGO naglowka byloby
  // jednak gadatliwe: przy skakaniu po naglowkach czytnik powtarzalby te sama
  // liczbe kilkadziesiat razy. Uzytkownik potrzebuje jej RAZ, na wejsciu w okno
  // — dalej wystarcza rosnacy numer.
  const numer = (Number(total) > 0 && Number(ordinal) === _a11yTurnOffset + 1)
    ? `${ordinal}/${total}`
    : `${ordinal}`;

  if (isAssistant) {
    // Godzina z atrybutu title podpisu roli ("17.08.2026, 11:15:25").
    const roleEl = row.querySelector('.msg-role');
    const stamp = roleEl ? (roleEl.getAttribute('title') || '') : '';
    const hhmm = (stamp.match(/(\d{1,2}:\d{2})/) || [])[1] || '';
    // Tura W TOKU mowi wprost, ze trwa. Bez tego po skoku na naglowek nie bylo
    // zadnej roznicy miedzy odpowiedzia gotowa a wciaz powstajaca — a to byla
    // dokladnie skarga uzytkownika ("nie wiem, czy sie zacial").
    const live = _a11yTurnIsLive(row);
    if (live) {
      const working = (typeof t === 'function' && t('a11y_turn_working')) || 'working';
      return `${numer}. ${label}, ${working}`;
    }
    return `${numer}. ${label}${hhmm ? ' ' + hhmm : ''}`;
  }

  const snippet = _a11ySnippet(row);
  return `${numer}. ${label}${snippet ? ': ' + snippet : ''}`;
}

/* Kolejnosc w turze asystenta: ODPOWIEDZ NAJPIERW, dziennik i przyciski potem.
 *
 * Problem zmierzony w sesji na 1152 wiadomosci: w kodzie strony dziennik
 * aktywnosci ("Processed") lezy PRZED trescia odpowiedzi (indeksy 5 vs 346).
 * Skok na naglowek wypowiedzi ladowal wiec na dzienniku, a nie na odpowiedzi —
 * do tresci trzeba bylo dopiero dojechac.
 *
 * Rozwiazanie: .assistant-turn-blocks jest flexem w kolumnie (zmierzone:
 * display:flex, flex-direction:column), a flexbox pozwala zmienic kolejnosc
 * atrybutem order — i, co tu najwazniejsze, DLA CZYTNIKA EKRANU TEZ, bo
 * przegladarki ustawiaja kolejnosc w drzewie dostepnosci zgodnie z ukladem
 * flex. Nie przenosimy wiec wezlow w DOM (co zerwaloby recykling wierszy,
 * pomiary wysokosci i zakotwiczenia przewijania), tylko nadajemy order.
 *
 * WYJATEK: tura NA ZYWO zostaje bez zmian. Dziennik jest wtedy jedyna
 * informacja o postepie i musi byc na gorze; przestawianie go w trakcie
 * odpowiedzi przeskakiwaloby uklad pod palcami uzytkownika.
 */
function _a11yReorderTurn(row){
  if (!row.classList.contains('assistant-turn')) return;
  const blocks = row.querySelector('.assistant-turn-blocks');
  if (!blocks) return;

  // Tura w toku: nie ruszamy jej kolejnosci. Dziennik jest wtedy jedyna
  // informacja o postepie i musi zostac na gorze; przestawianie w trakcie
  // przeskakiwaloby uklad pod palcami uzytkownika.
  const live = _a11yTurnIsLive(row);

  const kids = Array.from(blocks.children);
  const hasProse = kids.some(el => el.classList.contains('assistant-segment')
    && el.getClientRects().length > 0);
  if (live || !hasProse) {
    // wycofaj ewentualne wczesniejsze przestawienie
    for (const el of kids) {
      if (el.dataset && el.dataset.a11yOrdered) {
        el.style.order = '';
        delete el.dataset.a11yOrdered;
      }
    }
    return;
  }

  for (const el of kids) {
    const isLog = el.classList.contains('agent-activity-group')
      || el.classList.contains('tool-call-group')
      || el.classList.contains('tool-worklog')
      || el.classList.contains('thinking-card');
    if (!isLog) continue;
    // ZMIERZONE: sam CSS `order` NIE wystarcza. Po ustawieniu order=2/1 uklad
    // wizualny zmienil sie poprawnie (tresc nad dziennikiem), ale w drzewie
    // dostepnosci dziennik NADAL byl przed trescia (pozycje 1731 vs 1734) —
    // a czytnik ekranu czyta wlasnie to drzewo, nie uklad wizualny.
    // Dlatego przenosimy wezel na koniec kontenera. Robimy to tylko dla tur
    // ZAKONCZONYCH, wiec nie kolidujemy ze strumieniowaniem.
    if (el.nextElementSibling) blocks.appendChild(el);
    if (el.style.order) el.style.order = '';
    if (el.dataset) el.dataset.a11yOrdered = '1';
  }
}

function _a11yEnsureTurnHeading(row, ordinal, total){
  const text = _a11yTurnHeadingText(row, ordinal, total);

  let h = row.firstElementChild;
  if (!(h && h.dataset && h.dataset[A11Y_HEAD_MARK] === 'turn')) {
    h = document.createElement('h2');
    h.className = 'sr-only';
    h.dataset[A11Y_HEAD_MARK] = 'turn';
    row.insertBefore(h, row.firstChild);
  }
  if (h.dataset[A11Y_HEAD_DONE] !== text) {
    h.textContent = text;
    h.dataset[A11Y_HEAD_DONE] = text;
  }
}

/* <h3> for the collapsible blocks inside an assistant turn.  These are the
 * parts users skip past most often, so being able to jump over them at level 3
 * (and land on the next turn at level 2) is the point.
 *
 * Measured lesson: the first attempt put the <h3> inside .thinking-card, but
 * those cards live inside the COLLAPSED activity log (display:none), so no
 * screen reader ever saw them — NVDA's heading list showed h2 only.  The
 * heading has to sit on the element the user can actually reach: the visible
 * summary button that expands the log.  We label the wrapper, not the card. */
const A11Y_SUBHEADS = [
  // Measured against the live DOM, not guessed from class names elsewhere in
  // the code: the visible wrapper around the activity summary button is
  // .agent-activity-group (.tool-call-group is only the collapsed body).
  ['.agent-activity-group', 'a11y_block_activity', 'Tool activity'],
  ['.tool-call-group', 'a11y_block_activity', 'Tool activity'],
  ['.tool-worklog', 'a11y_block_worklog', 'Work log'],
];

/* Heading text for a collapsible block: prefer the block's own summary text
 * ("Processed", "Reading files", …) so the heading list is informative rather
 * than nine identical entries. */
function _a11yBlockLabel(block, fallbackKey, fallbackText){
  const summary = block.querySelector(
    '.tool-call-group-summary, .tool-worklog-summary, .tool-group-head, [aria-expanded]');
  const own = summary ? (summary.textContent || '').replace(/\s+/g, ' ').trim() : '';
  if (own) return own.length > 60 ? own.slice(0, 60).replace(/\s+\S*$/, '') + '…' : own;
  return (typeof t === 'function' && t(fallbackKey)) || fallbackText;
}

function _a11yEnsureBlockHeadings(row){
  for (const [sel, key, fallback] of A11Y_SUBHEADS) {
    for (const block of Array.from(row.querySelectorAll(sel))) {
      // Only decorate blocks the user can actually reach.  A heading buried in
      // a display:none subtree is invisible to assistive tech and just noise.
      if (!block.getClientRects().length) continue;
      const text = _a11yBlockLabel(block, key, fallback);
      let h = block.firstElementChild;
      if (!(h && h.dataset && h.dataset[A11Y_HEAD_MARK] === 'block')) {
        h = document.createElement('h3');
        h.className = 'sr-only';
        h.dataset[A11Y_HEAD_MARK] = 'block';
        block.insertBefore(h, block.firstChild);
      }
      if (h.dataset[A11Y_HEAD_DONE] !== text) {
        h.textContent = text;
        h.dataset[A11Y_HEAD_DONE] = text;
      }
    }
  }
}

let _a11yHeadingObserver = null;
let _a11yHeadingPending = false;

/* Przesuniecie numeracji: ile wypowiedzi jest UKRYTYCH powyzej wczytanego okna.
 *
 * Zgloszenie Michala (18.08.2026): "w dlugiej sesji numerki sa 1, 2, 3, mimo ze
 * sesja ma kilkadziesiat wiadomosci; wolalbym, zeby wyliczaly sie globalnie -
 * uzytkownik ma miec jasny oglad, ze sesja sie rozwija".
 *
 * WebUI wczytuje tylko ogon rozmowy (wstecz doladowuje sie przyciskiem), a
 * numeracja liczyla od pierwszego wiersza W DOM. Ta sama wypowiedz miala wiec
 * inny numer w zaleznosci od tego, ile okna doladowano, a "1." przy 576.
 * wypowiedzi nie mowilo NIC o miejscu w rozmowie.
 *
 * Serwer podaje teraz _visible_turns_before / _visible_turns_total w tej samej
 * przestrzeni co widoczne wiersze (surowy _messages_offset by nie wystarczyl:
 * zmierzone 978 wierszy magazynowych na 100 wypowiedzi w oknie). */
let _a11yTurnOffset = 0;
let _a11yTurnTotal = 0;

/* Wolane po kazdym wczytaniu/doladowaniu okna rozmowy. */
function a11ySetTurnNumbering(before, total){
  const b = Number(before);
  const t = Number(total);
  const nowyOffset = Number.isFinite(b) && b >= 0 ? Math.floor(b) : 0;
  const nowyTotal = Number.isFinite(t) && t >= 0 ? Math.floor(t) : 0;
  const zmiana = (nowyOffset !== _a11yTurnOffset) || (nowyTotal !== _a11yTurnTotal);
  _a11yTurnOffset = nowyOffset;
  _a11yTurnTotal = nowyTotal;
  // Numery sa już w tekstach naglowkow, wiec po zmianie przesuniecia trzeba je
  // przeliczyc — inaczej doladowanie starszych wiadomosci zostawiloby stare.
  if (zmiana) { try { a11yDecorateConversationHeadings(); } catch (_e) {} }
  return zmiana;
}

function a11yTurnNumberingOffset(){ return _a11yTurnOffset; }

function a11yDecorateConversationHeadings(container){
  const root = container || document.getElementById('messages');
  if (!root) return 0;
  // Visual order is DOM order here, so a straight walk numbers turns the way
  // they are read.  Live/streaming turns are included: the heading text is
  // refreshed on every pass, so a turn that starts empty gains its opening
  // words as soon as they arrive.
  const rows = Array.from(root.querySelectorAll('.msg-row'));
  let n = 0;
  for (const row of rows) {
    if (row.classList.contains('msg-row-spacer')) continue;
    n += 1;
    try {
      // Numer GLOBALNY: pozycja w calej rozmowie, nie w wczytanym oknie.
      _a11yEnsureTurnHeading(row, _a11yTurnOffset + n, _a11yTurnTotal);
      _a11yReorderTurn(row);
      _a11yEnsureBlockHeadings(row);
    } catch (_e) { /* never let decoration break rendering */ }
  }
  return n;
}

function a11yInstallConversationHeadings(){
  const root = document.getElementById('messages');
  if (!root || _a11yHeadingObserver) return;
  const run = () => {
    _a11yHeadingPending = false;
    // Detach while we mutate, or our own <h2> insertions retrigger the observer.
    _a11yHeadingObserver.disconnect();
    try { a11yDecorateConversationHeadings(root); }
    finally {
      _a11yHeadingObserver.observe(root, {childList: true, subtree: true, characterData: true});
    }
  };
  _a11yHeadingObserver = new MutationObserver(() => {
    if (_a11yHeadingPending) return;
    _a11yHeadingPending = true;
    // Coalesce a streaming burst into one pass; 250ms keeps the heading list
    // fresh without re-walking the transcript on every token.
    setTimeout(run, 250);
  });
  _a11yHeadingObserver.observe(root, {childList: true, subtree: true, characterData: true});
  a11yDecorateConversationHeadings(root);
}

if (typeof window !== 'undefined') {
  window.a11yDecorateConversationHeadings = a11yDecorateConversationHeadings;
  window.a11ySetTurnNumbering = a11ySetTurnNumbering;
  window.a11yTurnNumberingOffset = a11yTurnNumberingOffset;
  window.a11yInstallConversationHeadings = a11yInstallConversationHeadings;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', a11yInstallConversationHeadings);
  } else {
    setTimeout(a11yInstallConversationHeadings, 0);
  }
}

/* ── Dostepny wskaznik "Hermes pracuje" ────────────────────────────────────
 *
 * Zgloszenie uzytkownika: "sesja wyglada jakby wisiala i nie wiem, czy Hermes
 * sie zacial, czy cos sie wysypalo, nic nie wiem".
 *
 * Zmierzona przyczyna: aplikacja WIE, ze trwa praca (przycisk wysylania jest
 * zablokowany, karta "Thinking" jest widoczna), ale zaden z tych sygnalow nie
 * dociera do czytnika ekranu:
 *   - #liveRunStatus     nie ma aria-live, a w trybie zwartym dziennika jest
 *                        w ogole ukrywany (el.hidden=true),
 *   - przycisku Stop     nie ma w dokumencie,
 *   - wskaznika pisania  nie ma,
 *   - blokada przycisku  jest wylacznie wizualna.
 * Efekt: cisza nieodroznialna od awarii. WCAG 4.1.3.
 *
 * Rozwiazanie w trzech warstwach, celowo oszczedne w mowie:
 *  1. JEDNORAZOWE ogloszenie "Hermes pracuje" na starcie i "gotowe" na koncu
 *     (obszar aktywny #a11yAnnouncer, tryb polite),
 *  2. CICHY stan do sprawdzenia na zadanie: rola status z aria-live=off, wiec
 *     czytnik go NIE czyta sam, ale uzytkownik moze tam wejsc nawigacja i
 *     odczytac biezaca czynnosc oraz czas trwania,
 *  3. NAGLOWEK tury na zywo mowi ", pracuje", zeby po skoku bylo od razu
 *     jasne, ze to jeszcze nie koniec odpowiedzi.
 *
 * Czego swiadomie NIE robimy: nie wlaczamy aria-live na strumieniu tresci ani
 * na dzienniku. Zalanie czytnika komunikatami co kilkaset milisekund jest
 * gorsze niz cisza, a kontrakt "zapis rozmowy nie jest obszarem aktywnym"
 * pilnuje test tests/test_a11y_transcript_landmarks.py.
 */

let _a11yRunActive = false;
let _a11yRunStartedAt = null;
let _a11yRunPollTimer = null;

function _a11yRunStatusHost(){
  let el = document.getElementById('a11yRunStatus');
  if (el) return el;
  el = document.createElement('div');
  el.id = 'a11yRunStatus';
  el.className = 'sr-only';
  el.setAttribute('role', 'status');
  // aria-live="off": czytnik NIE czyta tego sam. Uzytkownik siega tu, gdy chce
  // wiedziec, co sie dzieje — bez zalewania go komunikatami.
  el.setAttribute('aria-live', 'off');
  const anchor = document.getElementById('a11yAnnouncer');
  if (anchor && anchor.parentElement) anchor.parentElement.insertBefore(el, anchor.nextSibling);
  else document.body.appendChild(el);
  return el;
}

/* Nazwa biezacej czynnosci, czytana z tego, co produkt juz pokazuje na ekranie
 * (karta rozumowania / dziennik) — zeby nie wymyslac wlasnego slownika stanow. */
function _a11yCurrentActivity(){
  const live = document.getElementById('liveAssistantTurn');
  const scope = live || document.getElementById('messages');
  if (!scope) return '';
  const card = scope.querySelector('.thinking-card, .agent-activity-group, .tool-call-group');
  if (!card) return '';
  const head = card.querySelector(
    '.thinking-card-header, .tool-call-group-summary, .tool-worklog-summary, [aria-expanded]');
  const raw = (head ? head.textContent : card.textContent) || '';
  const text = raw.replace(/\s+/g, ' ').trim();
  return text.length > 80 ? text.slice(0, 80).replace(/\s+\S*$/, '') + '…' : text;
}

function _a11yRunElapsedText(){
  if (!_a11yRunStartedAt) return '';
  const s = Math.max(0, Math.round((Date.now() - _a11yRunStartedAt) / 1000));
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  return `${m} min ${String(s % 60).padStart(2, '0')} s`;
}

/* Prog ciszy: po tylu milisekundach BEZ ZADNEGO przyrostu uznajemy, ze model
 * chwilowo nic nie robi. 12 s, bo licznik odswieza sie co 5 s — krotszy prog
 * migalby "Idle" miedzy zwyklymi porcjami strumienia. */
const A11Y_RUN_IDLE_AFTER_MS = 12000;
let _a11yRunLastFingerprint = null;
let _a11yRunLastChangeAt = null;

/* Odcisk POSTEPU biegu: dlugosc prozy odpowiedzi + tekst biezacej czynnosci.
 * Zmiana odcisku = cos przyroslo. Brak zmiany przez A11Y_RUN_IDLE_AFTER_MS =
 * chwilowa cisza.
 *
 * Dlaczego odcisk, a nie "czy karta aktywnosci jest na ekranie": karta WISI na
 * ekranie takze wtedy, gdy model milczy (zmierzone — sonda pokazywala
 * "Processed 0s" i status uparcie raportowal prace, choc nic nie przyrastalo).
 * Obecnosc elementu nie jest dowodem postepu; dowodem jest ZMIANA. */
function _a11yRunProgressFingerprint(){
  const live = document.getElementById('liveAssistantTurn');
  const proza = live ? ((live.querySelector('.assistant-segment') || {}).textContent || '') : '';
  return `${proza.trim().length}|${_a11yCurrentActivity()}`;
}

function _a11yRunSilenceMs(){
  const teraz = Date.now();
  const odcisk = _a11yRunProgressFingerprint();
  if (odcisk !== _a11yRunLastFingerprint) {
    _a11yRunLastFingerprint = odcisk;
    _a11yRunLastChangeAt = teraz;
    return 0;
  }
  if (_a11yRunLastChangeAt === null) {
    _a11yRunLastChangeAt = teraz;
    return 0;
  }
  return teraz - _a11yRunLastChangeAt;
}

/* Baza pomiaru ciszy NALEZY DO BIEGU, nie do strony.
 *
 * Zmierzony defekt (18.08.2026): cichy status pokazywal "Idle — 0 s" — komunikat
 * SPRZECZNY WEWNETRZNIE, bo licznik biegu mowil 0 s (bieg dopiero wstal), a slowo
 * "Idle" wymaga A11Y_RUN_IDLE_AFTER_MS = 12 s BEZ zmiany odcisku. Oba nie moga
 * byc prawda naraz.
 *
 * PRZYCZYNA: `_a11yRunLastFingerprint` / `_a11yRunLastChangeAt` sa modulowe i
 * zerowane TYLKO przy ZMIANIE odcisku. Gdy uzytkownik po prostu patrzy na
 * otwarta rozmowe, odcisk stoi (np. "0|") i znacznik starzeje sie bez konca.
 * Nowy bieg dziedziczyl wiec cisze sprzed siebie i PIERWSZE odswiezenie stanu
 * przekraczalo prog -> uzytkownik czytnika dostawal "Idle" o pracy, ktora
 * wlasnie sie ZACZELA.
 *
 * To ta sama klasa bledu, ktora naprawialismy juz dwa razy w tym pliku: stan
 * mierzony globalnie, choc opisuje wlasnosc JEDNEGO biegu. Cisza w toku biegu
 * moze byc liczona najwczesniej od momentu, w ktorym bieg sie zaczal — dlatego
 * baze zeruje JEDEN wspolny helper wolany na KAZDYM przejsciu granicy biegu
 * (start i koniec), a nie kopia warunku w kazdym miejscu zapalajacym stan. */
function _a11yResetSilenceBaseline(){
  _a11yRunLastFingerprint = _a11yRunProgressFingerprint();
  _a11yRunLastChangeAt = Date.now();
}

function _a11yRefreshRunStatus(){
  if (!_a11yRunActive) return;
  const el = _a11yRunStatusHost();
  const label = (typeof t === 'function' && t('a11y_run_working')) || 'Hermes is working';
  const act = _a11yCurrentActivity();
  const elapsed = _a11yRunElapsedText();
  // Bieg trwa, ale NIC nie przyroslo od dluzszej chwili -> to PRZERWA w toku,
  // nie praca. Wtedy mowimy "Idle", zgodnie z rozroznieniem uzytkownika:
  // puste = koniec, "Idle" = chwilowa cisza, gdy zaraz ma sie jeszcze cos
  // pojawic. Mierzymy BRAK ZMIANY, a nie brak elementu na ekranie.
  if (_a11yRunSilenceMs() >= A11Y_RUN_IDLE_AFTER_MS) { a11yRunIdlePause(); return; }
  const text = `${label}${elapsed ? ' — ' + elapsed : ''}${act ? ' — ' + act : ''}`;
  if (el.textContent !== text) el.textContent = text;
}

/* BIEG SPOZA TEJ PRZEGLADARKI (CLI/TUI, inna karta, bramka).
 *
 * Zgloszenie Michala (18.08.2026): ta sama sesja otwarta w terminalu i w WebUI.
 * W terminalu widac, ze praca trwa; w przegladarce wyglada, jakby Hermes
 * skonczyl. Zmierzone: /api/session zwracalo is_streaming=false i
 * active_stream_id=null DLA SESJI, W KTOREJ AGENT WLASNIE PISAL - serwer sledzi
 * tylko strumienie wlasne, a tura z CLI jest dla niego niewidoczna.
 *
 * Nasz stan biegu (a11yRunStarted/Finished) jest tu SLUSZNIE wygaszony: ta karta
 * niczego nie wysylala. Brakowalo INFORMACJI, ze pracuje ktos inny. Serwer podaje
 * ja teraz w polach last_activity_at / last_activity_description (pisze je sam
 * agent: "receiving stream response", "executing tool: terminal",
 * "terminal command running (60s elapsed)").
 *
 * Dlaczego prog jest tak luzny: zmierzony rozklad odswiezen tego sygnalu podczas
 * realnej pracy pokazal przerwy do ~58 s (sygnal aktualizuje sie przy ZMIANIE
 * ETAPU, nie co sekunde). Prog krotszy niz to sprawialby, ze komunikat MIGA w
 * trakcie jednego dlugiego wywolania modelu - a migajacy stan jest dla uzytkownika
 * czytnika gorszy niz brak stanu. Dlatego 90 s: z zapasem powyzej najdluzszej
 * zmierzonej przerwy.
 *
 * Sygnal jest tylko UZUPELNIENIEM: gdy ta karta sama prowadzi bieg, pierwszenstwo
 * ma stan lokalny (dokladniejszy, odswiezany co 5 s). */
const A11Y_FOREIGN_RUN_FRESH_MS = 90000;
let _a11yForeignRunActive = false;

/* Czy dane sesji mowia, ze KTOS INNY wlasnie pracuje.
 * Zwraca opis czynnosci albo '' (brak obcego biegu). */
function a11yForeignRunActivity(sesja){
  if (!sesja || typeof sesja !== 'object') return '';
  // Sesja zakonczona nie pracuje, choćby znacznik byl swiezy.
  if (sesja.ended_at) return '';
  const znacznik = Number(sesja.last_activity_at || 0);
  if (!znacznik) return '';
  // Znacznik jest w sekundach epoki (tak zapisuje go agent).
  const wiekMs = Date.now() - znacznik * 1000;
  if (!(wiekMs >= 0) || wiekMs > A11Y_FOREIGN_RUN_FRESH_MS) return '';
  const opis = String(sesja.last_activity_description || '').replace(/\s+/g, ' ').trim();
  // Bez opisu nie zgadujemy: "cos sie dzieje" bez tresci to szum.
  if (!opis) return '';
  return opis.length > 80 ? opis.slice(0, 80).replace(/\s+\S*$/, '') + '…' : opis;
}

/* Wolane po kazdym odswiezeniu danych sesji. Idempotentne.
 *
 * UWAGA: to NIE jest drugi mechanizm obok watchdoga ponizej. Watchdog decyduje,
 * CZY obcy bieg trwa (na podstawie przyrostu znacznika), a ta funkcja dokleja
 * CZYNNOSC do cichego stanu, gdy bieg nie nalezy do tej karty. */
function a11ySyncForeignRunState(sesja){
  const opis = a11yForeignRunActivity(sesja);
  // Bieg prowadzony przez TA karte jest dokladniejszy - nie nadpisujemy go.
  if (_a11yRunActive) { _a11yForeignRunActive = false; return false; }
  const el = _a11yRunStatusHost();
  if (opis) {
    const label = (typeof t === 'function' && t('a11y_run_working_elsewhere'))
      || 'Hermes is working in another session';
    const text = `${label} — ${opis}`;
    if (el.textContent !== text) el.textContent = text;
    if (!_a11yForeignRunActive) {
      _a11yForeignRunActive = true;
      // Jednorazowo, tryb polite: uzytkownik ma wiedziec, ze nie patrzy na
      // skonczona rozmowe. Kolejne odswiezenia sa CICHE.
      if (typeof a11yAnnounce === 'function') a11yAnnounce(label);
    }
    return true;
  }
  if (_a11yForeignRunActive) {
    _a11yForeignRunActive = false;
    if (el.textContent) el.textContent = '';
  }
  return false;
}

function a11yRunStarted(){
  if (_a11yRunActive) return;
  _a11yRunActive = true;
  _a11yRunStartedAt = Date.now();
  // Cisza liczy sie OD TEGO MOMENTU. Bez tego nowy bieg dziedziczyl znacznik
  // sprzed siebie i pierwsze odswiezenie wypisywalo "Idle — 0 s".
  _a11yResetSilenceBaseline();
  _a11yRefreshRunStatus();
  if (typeof a11yAnnounce === 'function') {
    a11yAnnounce((typeof t === 'function' && t('a11y_run_started')) || 'Hermes is working');
  }
  if (_a11yRunPollTimer) clearInterval(_a11yRunPollTimer);
  // 5 s: doslownie tylko odswieza CICHY tekst stanu, nic nie mowi.
  _a11yRunPollTimer = setInterval(_a11yRefreshRunStatus, 5000);
  try { a11yDecorateConversationHeadings(); } catch (_e) {}
}

function a11yRunFinished(){
  if (_a11yRunPollTimer) { clearInterval(_a11yRunPollTimer); _a11yRunPollTimer = null; }
  if (!_a11yRunActive) return;
  _a11yRunActive = false;
  _a11yRunStartedAt = null;
  // Praca SKONCZONA -> pole zostaje PUSTE, a nie "Idle".
  // Decyzja uzytkownika (czytnik ekranu): "jesli faktycznie nic nie robi, to
  // niech jest puste; jesli czekamy i zaraz ma sie jeszcze cos pojawic, a
  // chwilowo model nic nie robi, no to Idle".
  // Czyli slowo "Idle" znaczy PRZERWA W TOKU pracy, a nie koniec tury —
  // inaczej po kazdej odpowiedzi uzytkownik zastawal tam mylacy komunikat
  // sugerujacy, ze cos jeszcze sie dzieje.
  const el = document.getElementById('a11yRunStatus');
  if (el) el.textContent = '';
  // Zwalniamy tez baze pomiaru ciszy: nalezala do TEGO biegu. Zostawiony
  // znacznik jest dokladnie tym, co dawalo "Idle — 0 s" nastepnemu biegowi.
  _a11yResetSilenceBaseline();
  try { a11yDecorateConversationHeadings(); } catch (_e) {}
}

/* Przerwa W TOKU pracy: model chwilowo nic nie robi, ale bieg trwa i zaraz
 * pojawi sie kolejny etap. Tu "Idle" jest na miejscu — informuje, ze nie ma
 * awarii, tylko cisza w trakcie. Wolane tylko przy AKTYWNYM biegu; po jego
 * zakonczeniu pole czysci a11yRunFinished(). */
function a11yRunIdlePause(){
  if (!_a11yRunActive) return;
  const el = _a11yRunStatusHost();
  const label = (typeof t === 'function' && t('a11y_run_idle')) || 'Idle';
  const elapsed = _a11yRunElapsedText();
  const text = `${label}${elapsed ? ' — ' + elapsed : ''}`;
  if (el.textContent !== text) el.textContent = text;
}

function a11yRunIsActive(){ return _a11yRunActive; }

/* ── Obca sesja, ktora WCIAZ PRACUJE ─────────────────────────────────────
 *
 * Zgloszenie uzytkownika: "jesli otworze dzialajaca z webui sesje, ktora
 * zaczalem z innego miejsca, to jesli tam sie dzieje cos, to tez chce o tym
 * wiedziec i zeby lecial timer - sesja zyje, ja nie mam informacji, ze zyje".
 *
 * ZMIERZONA PRZYCZYNA: sesja z TUI/Telegrama nie ma `active_stream_id` ani
 * `is_streaming` — webui ustawia te pola TYLKO dla tur, ktore sam rozpoczal.
 * Dla sesji 20260817_192840_e7fa2f serwer zwracal active_stream_id=null,
 * is_streaming=false, mimo ze w state.db ostatnia wiadomosc miala znacznik
 * 4 SEKUNDY wczesniej (praca trwala w tej sekundzie). Zaden z czterech kanalow
 * informacji nie byl wiec wlaczony: wskaznik ukryty, cichy status nieutworzony,
 * stan biegu wylaczony, naglowek bez "working".
 *
 * WIARYGODNY SYGNAL to `last_message_at` z /api/sessions — jedyne pole, ktore
 * ROSNIE niezaleznie od tego, kto prowadzi ture. Pytamy o PRZYROST, nie o
 * obecnosc flagi: przyrost jest dowodem pracy, flaga jest tylko deklaracja
 * wlasciciela strumienia.
 */
const A11Y_FOREIGN_POLL_MS = 5000;
/* Drugi przyrost musi przyjsc w tym oknie, zeby uznac prace za TRWAJACA.
 * Jeden przyrost to takze naturalny koniec tury (dochodzi ostatnia wiadomosc),
 * wiec bez potwierdzenia zapalalibysmy "working" po KAZDEJ odpowiedzi. */
const A11Y_FOREIGN_CONFIRM_MS = 12000;
/* Po tylu ms bez przyrostu uznajemy obca ture za zakonczona. Krotko, bo to jest
 * czas, przez ktory uzytkownik widzi "working" juz PO zakonczeniu pracy —
 * a wlasnie na to bylo zgloszenie. Prog ciszy (A11Y_RUN_IDLE_AFTER_MS = 12 s)
 * jest krotszy, wiec zdazymy jeszcze pokazac "Idle" przed wygaszeniem. */
const A11Y_FOREIGN_DONE_AFTER_MS = 20000;
let _a11yForeignTimer = null;
let _a11yForeignSid = null;
let _a11yForeignLastStamp = null;
let _a11yForeignLastGrowthAt = null;
let _a11yForeignOwnsRun = false;

function _a11ySidFromLocation(){
  const m = String(location.pathname || '').match(/\/session\/([^/?#]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}

/* Czy ture prowadzi TA karta. Wtedy nie dotykamy stanu biegu — wlascicielem
 * jest zwykla sciezka strumienia (showLiveRunStatus/hideLiveRunStatus). */
function _a11yThisTabOwnsTurn(){
  try {
    if (typeof S === 'undefined' || !S) return false;
    return !!(S.busy || S.activeStreamId || (S.session && S.session.active_stream_id));
  } catch (_e) { return false; }
}

async function _a11yForeignPoll(){
  const sid = _a11ySidFromLocation();
  if (sid !== _a11yForeignSid) {
    // Przelaczono rozmowe — pomiar zaczyna sie od nowa.
    _a11yForeignSid = sid;
    _a11yForeignLastStamp = null;
    _a11yForeignLastGrowthAt = null;
    // Stan biegu gasimy BEZWARUNKOWO, nie tylko gdy nalezal do watchdoga.
    // Zmierzony objaw (17.08.2026): po klikniecu innej rozmowy cichy status
    // dalej mowil "Hermes is working — 5 s", bo stan zapalila INNA droga
    // (wlasna tura), a warunek na _a11yForeignOwnsRun go nie ruszal. To ta sama
    // klasa bledu, ktora naprawialismy w hideLiveRunStatus: stan przypisany do
    // JEDNEGO wlasciciela zostaje zapalony, gdy gasi go kto inny. Praca z
    // poprzedniej rozmowy nie dotyczy tej, ktora uzytkownik wlasnie otworzyl.
    _a11yForeignOwnsRun = false;
    if (typeof a11yRunIsActive === 'function' && a11yRunIsActive()) a11yRunFinished();
  }
  if (!sid) return;
  if (_a11yThisTabOwnsTurn()) {
    // Ture prowadzi TA karta — wlascicielem stanu jest zwykla sciezka strumienia.
    // Zerujemy baze pomiaru, zeby po ZAKONCZENIU wlasnej tury watchdog nie
    // zobaczyl "przyrostu" wzgledem znacznika sprzed tury i nie zapalil stanu
    // ponownie. Po wyzerowaniu pierwszy odczyt tylko ustala baze (nie zapala).
    _a11yForeignLastStamp = null;
    _a11yForeignLastGrowthAt = null;
    return;
  }
  let stamp = null;
  let sesja = null;
  try {
    const r = await fetch(`/api/session?session_id=${encodeURIComponent(sid)}&messages=0&resolve_model=0`,
                          {credentials: 'same-origin'});
    if (!r.ok) return;
    const d = await r.json();
    const s = (d && d.session) || d || {};
    sesja = s;
    // Dwa niezalezne dowody postepu, brane RAZEM.
    //
    // Zmierzony defekt (18.08.2026, zgloszenie Michala: "w terminalu widze, ze
    // sie dzieje, w WebUI wyglada jakby Hermes skonczyl"): tura z CLI potrafi
    // pracowac DZIESIATKI SEKUND bez ani jednej nowej wiadomosci — probkowanie
    // 22x co 4 s pokazalo licznik stojacy na 1442 przez cale 88 s, mimo ze agent
    // pracowal. Sam `last_message_at` daje wiec martwe okna, w ktorych watchdog
    // gasi stan w srodku pracy.
    //
    // `last_activity_at` pisze SAM AGENT przy kazdej zmianie etapu (nowe
    // wywolanie narzedzia, nowy strumien), wiec tyka takze wtedy, gdy nic jeszcze
    // nie doszlo do zapisu rozmowy. Maksimum z obu jest monotoniczne, wiec cala
    // logika "przyrost = postep" ponizej zostaje bez zmian.
    stamp = Math.max(
      Number(s.last_message_at || s.updated_at || 0) || 0,
      Number(s.last_activity_at || 0) || 0,
    ) || null;
  } catch (_e) { return; }   // brak sieci nie jest dowodem konca pracy
  if (stamp === null) return;
  const teraz = Date.now();
  if (_a11yForeignLastStamp === null) {
    // PIERWSZY ODCZYT USTALA TYLKO BAZE — NIGDY nie zapala stanu.
    //
    // Byla tu heurystyka "jesli ostatnia wiadomosc jest swiezsza niz 30 s, to
    // sesja niemal pewnie pracuje" i to byl BLAD, zgloszony przez uzytkownika:
    // "jestem w sesji w ktorej mi wlasnie odpowiadasz i mam Hermes is working,
    // a juz przeciez nie pracuje". Zaraz po zakonczeniu tury last_message_at
    // JEST swiezy — bo wlasnie doszla odpowiedz — wiec warunek zapalal stan
    // dokladnie w momencie, w ktorym praca sie skonczyla.
    //
    // SWIEZOSC NIE JEST DOWODEM TRWANIA. Dowodem jest wylacznie PRZYROST miedzy
    // dwoma odczytami: znacznik, ktory sie NIE zmienil, znaczy "nic nie doszlo",
    // niezaleznie od tego, jak jest swiezy. Kosztem jest do 5 s zwloki przy
    // wejsciu na trwajaca obca sesje — swiadomie, bo cisza przez chwile jest
    // znacznie mniej szkodliwa niz komunikat o pracy, ktorej nie ma.
    _a11yForeignLastStamp = stamp;
    _a11yForeignLastGrowthAt = teraz;
    return;
  }
  if (stamp > _a11yForeignLastStamp) {
    // Przyrost. UWAGA: JEDEN przyrost NIE dowodzi, ze praca TRWA — dowodzi, ze
    // COS doszlo. Zakonczona tura tez konczy sie przyrostem (dochodzi ostatnia
    // wiadomosc), wiec zapalanie stanu po pierwszym przyroscie dawalo "working"
    // przez caly A11Y_FOREIGN_DONE_AFTER_MS po KAZDEJ zakonczonej odpowiedzi.
    // Dlatego wymagamy DRUGIEGO przyrostu w krotkim okienku: praca w toku sypie
    // wiadomosciami po kolei, zakonczona tura ma dokladnie jeden.
    const poprzedni = _a11yForeignLastGrowthAt;
    _a11yForeignLastStamp = stamp;
    _a11yForeignLastGrowthAt = teraz;
    if (_a11yRunActive) {
      if (_a11yForeignOwnsRun) _a11yRefreshRunStatus();
      return;
    }
    const odstep = poprzedni ? (teraz - poprzedni) : Infinity;
    if (odstep <= A11Y_FOREIGN_CONFIRM_MS) {
      _a11yForeignOwnsRun = true;
      a11yRunStarted();
    }
    // Czynnosc podana przez agenta ("executing tool: terminal") jest
    // dokladniejsza niz cokolwiek, co da sie odczytac z DOM obcej sesji —
    // ta karta nie renderuje jej tury na zywo.
    a11ySyncForeignRunState(sesja);
    return;
  }
  // brak przyrostu
  if (_a11yForeignOwnsRun) {
    if (teraz - (_a11yForeignLastGrowthAt || teraz) >= A11Y_FOREIGN_DONE_AFTER_MS) {
      _a11yForeignOwnsRun = false;
      a11yRunFinished();
      a11ySyncForeignRunState(sesja);
    } else {
      _a11yRefreshRunStatus();   // po progu ciszy samo przejdzie w "Idle"
    }
  } else {
    // Stan nie nalezy do tej karty i nie ma przyrostu: jesli agent nadal
    // raportuje swieza czynnosc (CLI potrafi milczec dziesiatki sekund),
    // pokazujemy JA, zamiast udawac, ze rozmowa sie skonczyla.
    a11ySyncForeignRunState(sesja);
  }
}

function a11yWatchForeignRun(){
  if (_a11yForeignTimer) return;
  _a11yForeignSid = _a11ySidFromLocation();
  _a11yForeignTimer = setInterval(() => { void _a11yForeignPoll(); }, A11Y_FOREIGN_POLL_MS);
  void _a11yForeignPoll();
}

if (typeof window !== 'undefined') {
  window.a11yWatchForeignRun = a11yWatchForeignRun;
  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => a11yWatchForeignRun());
    } else {
      a11yWatchForeignRun();
    }
  }
}

if (typeof window !== 'undefined') {
  window.a11yRunStarted = a11yRunStarted;
  window.a11yRunFinished = a11yRunFinished;
  window.a11yRunIdlePause = a11yRunIdlePause;
  window.a11yForeignRunActivity = a11yForeignRunActivity;
  window.a11ySyncForeignRunState = a11ySyncForeignRunState;
  window.a11yRunIsActive = a11yRunIsActive;
}
