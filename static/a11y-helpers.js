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
