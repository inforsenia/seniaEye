/**
 * Dashboard Renderer
 * High-level rendering orchestration for dashboard UI
 */

import * as dom from '../utils/dom.js';
import * as components from './components.js';

/**
 * DashboardRenderer - Orchestrates all dashboard rendering
 */
export class DashboardRenderer {
  constructor(config = {}) {
    this.config = {
      agentsGrid: null,
      logContainer: null,
      logBody: null,
      countOnlineEl: null,
      countEventsEl: null,
      eventBadgeEl: null,
      inetStatusEl: null,
      wsStatusEl: null,
      ...config,
    };
  }

  /**
   * Render agent grid
   * @param {Array<Agent>} agents - Agent list
   * @param {string} selectedId - Selected agent ID or null
   * @param {object} handlers - Event handlers for cards
   */
  renderAgents(agents, selectedId = null, handlers = {}) {
    const grid = this.config.agentsGrid;
    if (!grid) {
      console.warn('agentsGrid container not configured');
      return;
    }

    dom.clear(grid);

    if (!agents || agents.length === 0) {
      grid.innerHTML = `<div style="grid-column:1/-1;display:flex;align-items:center;justify-content:center;
        height:100%;font-family:var(--mono);font-size:11px;color:var(--muted);letter-spacing:2px;">
        SIN AGENTES CONECTADOS</div>`;
      return;
    }

    agents.forEach(agent => {
      const card = components.createAgentCard(agent, handlers);
      
      // Add selected state
      if (agent.id === selectedId) {
        card.classList.add('selected');
      }
      
      // Add monitoring state
      if (agent.status === 'monitoring') {
        card.classList.add('monitoring');
      }

      grid.appendChild(card);
    });
  }

  /**
   * Render events table rows
   * @param {Array<Event>} events - Event list (newest first)
   * @param {object} agentColorMap - Map of agent ID to color
   * @param {boolean} clearFirst - Clear table before rendering
   */
  renderEvents(events, agentColorMap = {}, clearFirst = true) {
    const tbody = this.config.logBody;
    if (!tbody) {
      console.warn('logBody container not configured');
      return;
    }

    if (clearFirst) {
      dom.clear(tbody);
    }

    if (!events || events.length === 0) {
      const emptyRow = dom.createElement('tr', { id: 'empty-row' });
      const emptyCell = dom.createElement('td', { colSpan: '4' });
      emptyCell.appendChild(components.createEmptyState());
      emptyRow.appendChild(emptyCell);
      tbody.appendChild(emptyRow);
      return;
    }

    // Remove empty state if it exists
    const emptyRow = dom.qs('#empty-row', tbody);
    if (emptyRow) {
      emptyRow.remove();
    }

    events.forEach(event => {
      const row = components.createEventRow(event, agentColorMap);
      tbody.appendChild(row);
    });
  }

  /**
   * Prepend single event to table (for live updates)
   * @param {Event} event
   * @param {object} agentColorMap
   */
  prependEvent(event, agentColorMap = {}) {
    const tbody = this.config.logBody;
    const emptyRow = dom.qs('#empty-row', tbody);
    if (emptyRow) {
      emptyRow.remove();
    }

    const row = components.createEventRow(event, agentColorMap);
    const firstRow = tbody.firstChild;
    if (firstRow) {
      tbody.insertBefore(row, firstRow);
    } else {
      tbody.appendChild(row);
    }
  }

  /**
   * Update header statistics
   * @param {number} onlineCount - Number of online agents
   * @param {number} eventCount - Total event count
   */
  updateStats(onlineCount = 0, eventCount = 0) {
    if (this.config.countOnlineEl) {
      this.config.countOnlineEl.textContent = onlineCount;
    }
    if (this.config.countEventsEl) {
      this.config.countEventsEl.textContent = eventCount;
    }
  }

  /**
   * Update event badge
   * @param {number} shown - Shown events count
   * @param {number} total - Total events count
   */
  updateEventBadge(shown = 0, total = 0) {
    if (this.config.eventBadgeEl) {
      this.config.eventBadgeEl.textContent = `${shown} / ${total} eventos`;
    }
  }

  /**
   * Set internet status display
   * @param {string} status - 'on', 'off', 'checking'
   * @param {boolean} disableOn - Disable ON button
   * @param {boolean} disableOff - Disable OFF button
   */
  setInternetStatus(status, disableOn = false, disableOff = false) {
    if (this.config.inetStatusEl) {
      const statusMap = {
        'on': { class: 'on', text: 'HAY INTERNET' },
        'off': { class: 'off', text: 'NO HAY INTERNET' },
        'checking': { class: 'checking', text: 'COMPROBANDO...' },
      };

      const config = statusMap[status] || statusMap.off;
      this.config.inetStatusEl.className = `inet-status ${config.class}`;
      this.config.inetStatusEl.textContent = config.text;
    }

    // Update buttons if elements available
    const btnOn = dom.qs('#btn-inet-on');
    const btnOff = dom.qs('#btn-inet-off');
    if (btnOn) btnOn.disabled = disableOn;
    if (btnOff) btnOff.disabled = disableOff;
  }

  /**
   * Set WebSocket status
   * @param {string} status - 'ok', 'err', 'wait'
   * @param {string} text - Status text
   */
  setWebSocketStatus(status, text = '') {
    if (this.config.wsStatusEl) {
      const statusMap = {
        'ok': 'ok',
        'err': 'err',
        'wait': 'wait',
      };

      const cls = statusMap[status] || 'wait';
      this.config.wsStatusEl.className = `ws-pill ${cls}`;
      this.config.wsStatusEl.textContent = text;
    }
  }

  /**
   * Toggle filter button active state
   * @param {boolean} isActive
   */
  setFilterButtonActive(isActive) {
    const btn = dom.qs('#btn-filter');
    if (btn) {
      dom.toggleClass(btn, 'active', isActive);
    }
  }

  /**
   * Toggle auto-scroll button state
   * @param {boolean} isActive
   */
  setAutoScrollActive(isActive) {
    const btn = dom.qs('#btn-auto');
    if (btn) {
      btn.textContent = `AUTO ↑ ${isActive ? 'ON' : 'OFF'}`;
      dom.toggleClass(btn, 'on', isActive);
    }
  }

  /**
   * Scroll to top of logs
   */
  scrollLogsToTop() {
    const container = dom.qs('#logs-scroll');
    if (container) {
      container.scrollTop = 0;
    }
  }

  /**
   * Show toast notification
   * @param {string} message
   * @param {string} type - 'ok', 'err', 'warn'
   * @param {number} duration - Duration in ms
   */
  showToast(message, type = '', duration = 3200) {
    const toastContainer = dom.qs('#toasts');
    if (!toastContainer) return;

    const toast = components.createToast(message, type);
    toastContainer.appendChild(toast);

    setTimeout(() => {
      if (toast.parentElement) {
        toast.remove();
      }
    }, duration);
  }

  /**
   * Clear all logs and reset UI
   */
  clearAllLogs() {
    const tbody = this.config.logBody;
    if (tbody) {
      dom.clear(tbody);
      const emptyRow = dom.createElement('tr', { id: 'empty-row' });
      const emptyCell = dom.createElement('td', { colSpan: '4' });
      emptyCell.appendChild(components.createEmptyState());
      emptyRow.appendChild(emptyCell);
      tbody.appendChild(emptyRow);
    }
  }

  /**
   * Get search input value
   * @returns {string}
   */
  getSearchQuery() {
    const searchInput = dom.qs('#search');
    return searchInput ? searchInput.value.toLowerCase() : '';
  }

  /**
   * Set search input value
   * @param {string} value
   */
  setSearchQuery(value) {
    const searchInput = dom.qs('#search');
    if (searchInput) {
      searchInput.value = value;
    }
  }

  /**
   * Call this on page load to set all selectors if not already provided
   */
  detectElements() {
    if (!this.config.agentsGrid) this.config.agentsGrid = dom.qs('#agents-grid');
    if (!this.config.logBody) this.config.logBody = dom.qs('#log-body');
    if (!this.config.countOnlineEl) this.config.countOnlineEl = dom.qs('#cnt-online');
    if (!this.config.countEventsEl) this.config.countEventsEl = dom.qs('#cnt-events');
    if (!this.config.eventBadgeEl) this.config.eventBadgeEl = dom.qs('#ev-badge');
    if (!this.config.inetStatusEl) this.config.inetStatusEl = dom.qs('#inet-status');
    if (!this.config.wsStatusEl) this.config.wsStatusEl = dom.qs('#ws-status');
  }
}
