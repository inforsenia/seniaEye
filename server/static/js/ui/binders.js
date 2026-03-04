/**
 * Event Binders
 * Attaches event listeners to UI elements
 */

import * as dom from '../utils/dom.js';

/**
 * Bind agent card listeners
 * @param {HTMLElement} cardElement - Agent card DOM element
 * @param {object} handlers - {onSelect, onStart, onStop}
 */
export function bindAgentCardListeners(cardElement, handlers = {}) {
  if (!cardElement) return;

  // Select handler already attached in components.js
  // But can add more complex handlers here if needed

  cardElement.addEventListener('mouseover', () => {
    cardElement.style.borderColor = 'rgba(0,212,255,0.3)';
  });

  cardElement.addEventListener('mouseout', () => {
    cardElement.style.borderColor = '';
  });
}

/**
 * Bind toolbar listeners
 * @param {object} handlers - {onSearch, onClear, onToggleAuto}
 */
export function bindToolbarListeners(handlers = {}) {
  const searchInput = dom.qs('#search');
  if (searchInput && handlers.onSearch) {
    searchInput.addEventListener('input', (e) => {
      handlers.onSearch(e.target.value.toLowerCase());
    });
  }

  const clearBtn = dom.qs('button[onclick*="clearLogs"]');
  if (clearBtn && handlers.onClear) {
    clearBtn.removeAttribute('onclick');
    clearBtn.addEventListener('click', handlers.onClear);
  }

  const autoBtn = dom.qs('#btn-auto');
  if (autoBtn && handlers.onToggleAuto) {
    autoBtn.removeAttribute('onclick');
    autoBtn.addEventListener('click', handlers.onToggleAuto);
  }
}

/**
 * Bind command buttons
 * @param {object} handlers - {onStartAll, onStopAll, onToggleFilter}
 */
export function bindCommandButtons(handlers = {}) {
  const startAllBtn = dom.qs('.ctrl-btn.start-all');
  if (startAllBtn && handlers.onStartAll) {
    startAllBtn.removeAttribute('onclick');
    startAllBtn.addEventListener('click', handlers.onStartAll);
  }

  const stopAllBtn = dom.qs('.ctrl-btn.stop-all');
  if (stopAllBtn && handlers.onStopAll) {
    stopAllBtn.removeAttribute('onclick');
    stopAllBtn.addEventListener('click', handlers.onStopAll);
  }

  const filterBtn = dom.qs('#btn-filter');
  if (filterBtn && handlers.onToggleFilter) {
    filterBtn.removeAttribute('onclick');
    filterBtn.addEventListener('click', handlers.onToggleFilter);
  }
}

/**
 * Bind internet control buttons
 * @param {object} handlers - {onInternetOn, onInternetOff}
 */
export function bindInternetButtons(handlers = {}) {
  const btnOn = dom.qs('#btn-inet-on');
  if (btnOn && handlers.onInternetOn) {
    btnOn.removeAttribute('onclick');
    btnOn.addEventListener('click', handlers.onInternetOn);
  }

  const btnOff = dom.qs('#btn-inet-off');
  if (btnOff && handlers.onInternetOff) {
    btnOff.removeAttribute('onclick');
    btnOff.addEventListener('click', handlers.onInternetOff);
  }
}

/**
 * Bind all standard dashboard listeners
 * @param {object} handlers - Combined handler map
 */
export function bindAllDashboardListeners(handlers = {}) {
  bindToolbarListeners({
    onSearch: handlers.onSearch,
    onClear: handlers.onClear,
    onToggleAuto: handlers.onToggleAuto,
  });

  bindCommandButtons({
    onStartAll: handlers.onStartAll,
    onStopAll: handlers.onStopAll,
    onToggleFilter: handlers.onToggleFilter,
  });

  bindInternetButtons({
    onInternetOn: handlers.onInternetOn,
    onInternetOff: handlers.onInternetOff,
  });
}

/**
 * Bind scroll events
 * @param {HTMLElement} scrollContainer - Container to monitor
 * @param {function} onScroll - Callback(isAtTop)
 */
export function bindScrollListener(scrollContainer, onScroll) {
  if (!scrollContainer || !onScroll) return;

  scrollContainer.addEventListener('scroll', () => {
    const isAtTop = scrollContainer.scrollTop === 0;
    onScroll(isAtTop);
  });
}

/**
 * Bind keyboard shortcuts
 * @param {object} shortcuts - Map of {key: handler}
 * Examples: 'ctrl+s' for save, 'escape' for close, etc.
 */
export function bindShortcuts(shortcuts = {}) {
  document.addEventListener('keydown', (e) => {
    const key = buildKeyString(e);
    
    if (shortcuts[key]) {
      e.preventDefault();
      shortcuts[key](e);
    }
  });
}

/**
 * Build keyboard shortcut string
 * @private
 * @param {KeyboardEvent} e
 * @returns {string}
 */
function buildKeyString(e) {
  const parts = [];
  if (e.ctrlKey) parts.push('ctrl');
  if (e.altKey) parts.push('alt');
  if (e.shiftKey) parts.push('shift');
  
  const key = e.key.toLowerCase();
  if (!['control', 'alt', 'shift'].includes(key)) {
    parts.push(key);
  }

  return parts.join('+');
}

/**
 * Bind prevent accidental close
 * @param {string} message - Warning message
 */
export function bindBeforeUnload(message = 'Hay eventos sin guardar. ¿Estás seguro?') {
  window.addEventListener('beforeunload', (e) => {
    e.preventDefault();
    e.returnValue = message;
    return message;
  });
}

/**
 * Unbind prevent accidental close
 */
export function unbindBeforeUnload() {
  window.removeEventListener('beforeunload', (e) => {
    e.preventDefault();
  });
}
