/**
 * DOM Utilities
 * Helpers for DOM manipulation, escaping, and event handling
 */

/**
 * Escape HTML special characters
 * @param {string} text - Text to escape
 * @returns {string} Escaped text safe for HTML
 */
export function escape(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Create element with attributes and optional content
 * @param {string} tag - HTML tag name
 * @param {object} attrs - Attributes to set (className, id, etc.)
 * @param {string|HTMLElement} content - Optional text or element content
 * @returns {HTMLElement}
 */
export function createElement(tag, attrs = {}, content = '') {
  const el = document.createElement(tag);
  
  Object.entries(attrs).forEach(([key, value]) => {
    if (key === 'className') {
      el.className = value;
    } else if (key === 'classList') {
      value.forEach(cls => el.classList.add(cls));
    } else if (key.startsWith('on')) {
      // Event handlers like onClick, onInput
      const eventName = key.slice(2).toLowerCase();
      el.addEventListener(eventName, value);
    } else if (key === 'disabled') {
      // Handle boolean attributes properly
      if (value) {
        el.disabled = true;
      }
    } else if (value !== null && value !== undefined && value !== false) {
      el.setAttribute(key, value);
    }
  });
  
  if (content) {
    if (typeof content === 'string') {
      el.textContent = content;
    } else if (content instanceof HTMLElement) {
      el.appendChild(content);
    }
  }
  
  return el;
}

/**
 * Set or toggle CSS classes
 * @param {HTMLElement} el - Element to modify
 * @param {string|array} classes - Class(es) to toggle
 * @param {boolean} force - Force add (true) or remove (false)
 */
export function toggleClass(el, classes, force = undefined) {
  const classList = Array.isArray(classes) ? classes : [classes];
  classList.forEach(cls => {
    if (force === undefined) {
      el.classList.toggle(cls);
    } else {
      el.classList.toggle(cls, force);
    }
  });
}

/**
 * Query selector helper
 * @param {string} selector - CSS selector
 * @param {HTMLElement} parent - Optional parent element
 * @returns {HTMLElement|null}
 */
export function qs(selector, parent = document) {
  return parent.querySelector(selector);
}

/**
 * Query selector all helper
 * @param {string} selector - CSS selector
 * @param {HTMLElement} parent - Optional parent element
 * @returns {NodeList}
 */
export function qsa(selector, parent = document) {
  return parent.querySelectorAll(selector);
}

/**
 * Set multiple CSS properties
 * @param {HTMLElement} el - Element to modify
 * @param {object} styles - Style object
 */
export function setStyles(el, styles) {
  Object.assign(el.style, styles);
}

/**
 * Get computed style value
 * @param {HTMLElement} el - Element
 * @param {string} property - CSS property name
 * @returns {string}
 */
export function getStyle(el, property) {
  return window.getComputedStyle(el).getPropertyValue(property);
}

/**
 * Remove element from DOM
 * @param {HTMLElement} el - Element to remove
 */
export function remove(el) {
  el?.parentElement?.removeChild(el);
}

/**
 * Append child to parent
 * @param {HTMLElement} parent - Parent element
 * @param {HTMLElement|string} child - Child element or HTML string
 */
export function append(parent, child) {
  if (typeof child === 'string') {
    parent.insertAdjacentHTML('beforeend', child);
  } else {
    parent.appendChild(child);
  }
}

/**
 * Insert before sibling
 * @param {HTMLElement} newEl - Element to insert
 * @param {HTMLElement} refEl - Reference element
 */
export function insertBefore(newEl, refEl) {
  refEl.parentElement.insertBefore(newEl, refEl);
}

/**
 * Clear all children from element
 * @param {HTMLElement} el - Element to clear
 */
export function clear(el) {
  while (el.firstChild) {
    el.removeChild(el.firstChild);
  }
}

/**
 * Check if element matches selector
 * @param {HTMLElement} el - Element
 * @param {string} selector - CSS selector
 * @returns {boolean}
 */
export function matches(el, selector) {
  return el.matches(selector);
}

/**
 * Find closest ancestor matching selector
 * @param {HTMLElement} el - Starting element
 * @param {string} selector - CSS selector
 * @returns {HTMLElement|null}
 */
export function closest(el, selector) {
  return el.closest(selector);
}

/**
 * Debounce function calls
 * @param {function} fn - Function to debounce
 * @param {number} delay - Delay in milliseconds
 * @returns {function}
 */
export function debounce(fn, delay) {
  let timeoutId;
  return function(...args) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn.apply(this, args), delay);
  };
}

/**
 * Stop event propagation
 * @param {Event} event
 */
export function stopPropagation(event) {
  event.stopPropagation();
  event.preventDefault();
}
