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

if (typeof window !== 'undefined') {
  window.a11yTrapFocus = a11yTrapFocus;
  window.a11ySyncPressedState = a11ySyncPressedState;
  window.a11yLabel = a11yLabel;
  window.a11yAnnounce = a11yAnnounce;
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
  '.msg-role', '.msg-tps-inline', '.msg-foot', '.msg-actions',
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
 * znaczniki to identyfikator tury na zywo, jawny data-live i kursor strumienia;
 * stan globalny biegu jest dodatkowa poszlaka, ale tylko dla OSTATNIEJ tury.
 */
function _a11yTurnIsLive(row){
  const liveTurn = document.getElementById('liveAssistantTurn');
  if (liveTurn && (liveTurn === row || row.contains(liveTurn) || liveTurn.contains(row))) return true;
  if (row.dataset && row.dataset.live === 'true') return true;
  if (row.querySelector('.stream-cursor, .typing-indicator, .msg-streaming')) return true;
  // Bieg trwa i to jest ostatnia tura asystenta w zapisie -> uznajemy za zywa.
  if (typeof a11yRunIsActive === 'function' && a11yRunIsActive()) {
    const all = document.querySelectorAll('#messages .msg-row.assistant-turn');
    if (all.length && all[all.length - 1] === row) return true;
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
function _a11yTurnHeadingText(row, ordinal){
  const label = _a11yRoleLabel(row);
  const isAssistant = (row.dataset && row.dataset.role === 'assistant')
    || row.classList.contains('assistant-turn');

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
      return `${ordinal}. ${label}, ${working}`;
    }
    return `${ordinal}. ${label}${hhmm ? ' ' + hhmm : ''}`;
  }

  const snippet = _a11ySnippet(row);
  return `${ordinal}. ${label}${snippet ? ': ' + snippet : ''}`;
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

function _a11yEnsureTurnHeading(row, ordinal){
  const text = _a11yTurnHeadingText(row, ordinal);

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
      _a11yEnsureTurnHeading(row, n);
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

function _a11yRefreshRunStatus(){
  if (!_a11yRunActive) return;
  const el = _a11yRunStatusHost();
  const label = (typeof t === 'function' && t('a11y_run_working')) || 'Hermes is working';
  const act = _a11yCurrentActivity();
  const elapsed = _a11yRunElapsedText();
  const text = `${label}${elapsed ? ' — ' + elapsed : ''}${act ? ' — ' + act : ''}`;
  if (el.textContent !== text) el.textContent = text;
}

function a11yRunStarted(){
  if (_a11yRunActive) return;
  _a11yRunActive = true;
  _a11yRunStartedAt = Date.now();
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
  const el = document.getElementById('a11yRunStatus');
  if (el) el.textContent = (typeof t === 'function' && t('a11y_run_idle')) || 'Idle';
  try { a11yDecorateConversationHeadings(); } catch (_e) {}
}

function a11yRunIsActive(){ return _a11yRunActive; }

if (typeof window !== 'undefined') {
  window.a11yRunStarted = a11yRunStarted;
  window.a11yRunFinished = a11yRunFinished;
  window.a11yRunIsActive = a11yRunIsActive;
}
