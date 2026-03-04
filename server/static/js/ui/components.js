/**
 * UI Components
 * Factory functions for creating reusable UI elements
 */

import * as dom from '../utils/dom.js';
import * as fmt from '../utils/formatting.js';
import { AGENT_STATUS, COLORS } from '../config/constants.js';

/**
 * Create agent card element (not inserted into DOM)
 * @param {Agent} agent - Agent data
 * @param {object} handlers - Click/button handlers {onSelect, onStart, onStop}
 * @returns {HTMLElement}
 */
export function createAgentCard(agent, handlers = {}) {
  const card = dom.createElement('div', {
    className: 'agent-card',
  });

  if (handlers.onSelect) {
    card.addEventListener('click', () => handlers.onSelect(agent.id));
  }

  // Top section with status dot and IP
  const top = dom.createElement('div', { className: 'ac-top' });
  
  const dot = dom.createElement('div', {
    className: ['ac-dot', agent.online ? 'on' : 'off'],
  });
  
  const ip = dom.createElement('span', {
    className: 'ac-ip',
    title: agent.id,
  });
  ip.textContent = agent.id;
  ip.style.color = agent.color;
  
  const count = dom.createElement('span', {
    className: 'ac-count',
  });
  count.textContent = agent.count;

  top.appendChild(dot);
  top.appendChild(ip);
  top.appendChild(count);
  card.appendChild(top);

  // Status badge
  const statusDiv = dom.createElement('div');
  const statusLabel = agent.online ? agent.status : AGENT_STATUS.OFFLINE;
  const statusBadge = dom.createElement('span', {
    className: ['ac-status', statusLabel],
  });
  statusBadge.textContent = statusLabel;
  statusDiv.appendChild(statusBadge);
  card.appendChild(statusDiv);

  // Control buttons
  const btnContainer = dom.createElement('div', { className: 'ac-btns' });
  
  const canStart = agent.online && agent.status !== AGENT_STATUS.MONITORING;
  const canStop = agent.online && agent.status === AGENT_STATUS.MONITORING;
  
  const btnStart = dom.createElement('button', {
    className: 'ac-btn s',
    disabled: !canStart,
  });
  btnStart.textContent = '▶';
  if (canStart && handlers.onStart) {
    btnStart.addEventListener('click', (e) => {
      e.stopPropagation();
      handlers.onStart(agent.id);
    });
  }
  
  const btnStop = dom.createElement('button', {
    className: 'ac-btn x',
    disabled: !canStop,
  });
  btnStop.textContent = '■';
  if (canStop && handlers.onStop) {
    btnStop.addEventListener('click', (e) => {
      e.stopPropagation();
      handlers.onStop(agent.id);
    });
  }

  btnContainer.appendChild(btnStart);
  btnContainer.appendChild(btnStop);
  card.appendChild(btnContainer);

  return card;
}

/**
 * Create event table row element
 * @param {Event} event - Event data
 * @param {object} agentLookup - Map of agent ID to agent color
 * @returns {HTMLElement}
 */
export function createEventRow(event, agentLookup = {}) {
  const tr = dom.createElement('tr');
  
  // Add animation class if needed
  tr.classList.add('new-ev');

  // Timestamp cell
  const tdTs = dom.createElement('td', { className: 'c-ts' });
  tdTs.textContent = event.timestamp ? fmt.formatTimestamp(event.timestamp) : '—';

  // Agent cell
  const tdAgent = dom.createElement('td', { className: 'c-agent' });
  const agentBadge = dom.createElement('span', { className: 'abadge' });
  const agentColor = agentLookup[event.agent_id] || COLORS.primary;
  agentBadge.style.color = agentColor;
  agentBadge.style.borderColor = agentColor + '28';
  agentBadge.style.background = agentColor + '10';
  agentBadge.textContent = event.agent_id || '—';
  tdAgent.appendChild(agentBadge);

  // Type cell
  const tdType = dom.createElement('td', { className: 'c-type' });
  const typeBadge = dom.createElement('span', {
    className: ['tbadge', `t-${event.type}`],
  });
  typeBadge.textContent = event.type;
  tdType.appendChild(typeBadge);

  // Data cell
  const tdData = dom.createElement('td', { className: 'c-data' });
  const dataText = fmt.formatEventData(event);
  tdData.textContent = dataText;

  tr.appendChild(tdTs);
  tr.appendChild(tdAgent);
  tr.appendChild(tdType);
  tr.appendChild(tdData);

  return tr;
}

/**
 * Create toast notification element
 * @param {string} message - Message to display
 * @param {string} type - Toast type (ok, err, warn, info)
 * @returns {HTMLElement}
 */
export function createToast(message, type = '') {
  const toast = dom.createElement('div', {
    className: ['toast', type],
  });
  toast.textContent = message;
  return toast;
}

/**
 * Create empty state message
 * @param {string} heading - Main heading
 * @param {string} subtext - Secondary text
 * @returns {HTMLElement}
 */
export function createEmptyState(heading = 'ESPERANDO EVENTOS', subtext = 'SèniaEye · Todo está siendo observado') {
  const container = dom.createElement('div', { className: 'empty-logs' });

  // Eye SVG
  const eye = dom.createElement('svg', {
    className: 'empty-eye',
    width: '100',
    height: '100',
    viewBox: '0 0 44 44',
  });
  eye.innerHTML = `
    <path fill="none" stroke="var(--crimson2)" stroke-width="1" d="M2,22 Q22,2 42,22 Q22,42 2,22 Z"/>
    <circle fill="none" stroke="var(--accent)" stroke-width="1" cx="22" cy="22" r="10"/>
    <circle fill="var(--accent)" cx="22" cy="22" r="4"/>
  `;

  const p = dom.createElement('p');
  p.textContent = heading;

  const small = dom.createElement('small');
  small.textContent = subtext;

  container.appendChild(eye);
  container.appendChild(p);
  container.appendChild(small);

  return container;
}

/**
 * Create internet status display
 * @param {string} status - 'on', 'off', or 'checking'
 * @returns {HTMLElement}
 */
export function createInetStatus(status) {
  const statusMap = {
    'on': { class: 'on', text: 'HAY INTERNET' },
    'off': { class: 'off', text: 'NO HAY INTERNET' },
    'checking': { class: 'checking', text: 'COMPROBANDO...' },
  };

  const config = statusMap[status] || statusMap.off;
  
  const el = dom.createElement('span', {
    className: ['inet-status', config.class],
    id: 'inet-status',
  });
  el.textContent = config.text;

  return el;
}

/**
 * Create stat chip (for header)
 * @param {string} label - Label text
 * @param {number} count - Count value
 * @param {string} dotClass - CSS class for dot (g or b)
 * @returns {HTMLElement}
 */
export function createStatChip(label, count = 0, dotClass = 'g') {
  const chip = dom.createElement('div', { className: 'stat-chip' });

  const dot = dom.createElement('div', {
    className: ['dot', dotClass],
  });

  const text = dom.createElement('span');
  text.innerHTML = `${count}&nbsp;${label}`;

  chip.appendChild(dot);
  chip.appendChild(text);

  return chip;
}

/**
 * Create section header
 * @param {string} title - Section title
 * @param {string} icon - Icon prefix
 * @returns {HTMLElement}
 */
export function createSectionHeader(title, icon = '◈') {
  const header = dom.createElement('div', { className: 'section-header' });
  const text = dom.createElement('span', { className: 'section-title' });
  text.textContent = `${icon} ${title}`;
  header.appendChild(text);
  return header;
}

/**
 * Create spinner/loading element
 * @returns {HTMLElement}
 */
export function createSpinner() {
  const spinner = dom.createElement('div', { className: 'spinner' });
  return spinner;
}

/**
 * Create badge for event count display
 * @param {number} shown - Shown count
 * @param {number} total - Total count
 * @returns {HTMLElement}
 */
export function createCountBadge(shown = 0, total = 0) {
  const badge = dom.createElement('span', { className: 'ev-badge' });
  badge.textContent = `${shown} / ${total} eventos`;
  return badge;
}
