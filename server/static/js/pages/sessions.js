/**
 * Sessions Page Coordinator
 * Main page logic for sessions history
 */

import { SessionStore } from '../modules/sessions.js';
import { DashboardRenderer } from '../ui/renderer.js';
import * as dom from '../utils/dom.js';
import * as fmt from '../utils/formatting.js';

/**
 * SessionsPage - Main coordinator for sessions page
 */
class SessionsPage {
  constructor() {
    this.store = new SessionStore();
    this.selectedSessionId = null;
    this.activeTypeFilter = null;
    this.sortOrder = 'desc'; // 'desc' = newest first, 'asc' = oldest first
    this.filteredSessions = [];
    this.filteredEvents = [];
    this.deleteTarget = null;
    this.autoRefreshInterval = null;
  }

  /**
   * Initialize the page
   */
  async init() {
    console.log('Initializing Sessions Page...');

    try {
      // Load initial sessions
      await this.loadSessions();

      // Setup event listeners
      this.setupListeners();

      // Setup auto-refresh (every 10 seconds)
      this.startAutoRefresh();

      console.log('Sessions page initialized');
    } catch (error) {
      console.error('Failed to initialize sessions page:', error);
      this.showError('Error al inicializar página de sesiones');
    }
  }

  /**
   * Load sessions list
   * @private
   */
  async loadSessions() {
    try {
      const sessionsList = dom.qs('#sessions-list');
      if (sessionsList) {
        sessionsList.innerHTML = '<div class="empty-list"><div class="spinner"></div></div>';
      }

      await this.store.fetchSessions();
      this.filteredSessions = this.store.getSessions();
      this.renderSessionList();
      this.updateSessionCount();
    } catch (error) {
      console.error('Failed to load sessions:', error);
      const sessionsList = dom.qs('#sessions-list');
      if (sessionsList) {
        sessionsList.innerHTML = '<div class="empty-list"><p>ERROR AL CARGAR</p></div>';
      }
    }
  }

  /**
   * Render session list
   * @private
   */
  renderSessionList() {
    const el = dom.qs('#sessions-list');
    if (!el) return;

    if (!this.filteredSessions.length) {
      el.innerHTML = '<div class="empty-list"><p>SIN SESIONES</p></div>';
      return;
    }

    el.innerHTML = this.filteredSessions.map(session => {
      const isOpen = !session.ended_at;
      const isActive = session.id === this.selectedSessionId;
      const duration = session.duration_s != null
        ? this.formatDuration(session.duration_s)
        : (isOpen ? 'EN CURSO' : '—');
      const [dateStr, timeStr] = session.started_at
        ? session.started_at.split(' ')
        : ['—', ''];

      return `
        <div class="session-item ${isActive ? 'active' : ''} ${isOpen ? 'open-session' : ''}"
             data-session-id="${session.id}">
          <div class="si-header">
            <span class="si-agent">${dom.escape(session.agent_id)}</span>
            <span class="si-id">#${session.id}</span>
          </div>
          <div class="si-meta">
            <span>📅 ${dateStr}</span>
            <span>🕐 ${timeStr}</span>
          </div>
          <div class="si-footer">
            <span class="si-evcount">${session.event_count} eventos</span>
            ${isOpen
              ? '<span class="si-status-open">● ACTIVA</span>'
              : `<span class="si-duration">⏱ ${duration}</span>`}
          </div>
          <button class="si-del-btn" title="Eliminar sesión">✕</button>
        </div>`;
    }).join('');

    // Attach event listeners to session items
    el.querySelectorAll('.session-item').forEach(item => {
      const sessionId = parseInt(item.dataset.sessionId);
      const agentId = item.querySelector('.si-agent').textContent;

      item.addEventListener('click', (e) => {
        if (!e.target.classList.contains('si-del-btn')) {
          this.loadSessionDetail(sessionId);
        }
      });

      const delBtn = item.querySelector('.si-del-btn');
      if (delBtn) {
        delBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          this.confirmDeleteOne(sessionId, agentId);
        });
      }
    });
  }

  /**
   * Load session detail
   * @private
   */
  async loadSessionDetail(sessionId) {
    this.selectedSessionId = sessionId;
    this.activeTypeFilter = null;
    this.sortOrder = 'desc';
    this.renderSessionList();

    const panel = dom.qs('#detail-panel');
    if (panel) {
      panel.innerHTML = '<div class="detail-placeholder"><div class="spinner"></div></div>';
    }

    try {
      const { session, events } = await this.store.fetchSessionDetails(sessionId);

      const isOpen = !session.ended_at;
      const duration = session.duration_s != null
        ? this.formatDuration(session.duration_s)
        : (isOpen ? 'EN CURSO' : '—');
      const types = this.store.getEventTypes();

      if (panel) {
        panel.innerHTML = `
          <div class="detail-header">
            <div>
              <div class="detail-title">Sesión #${session.id} — <span class="agent-hl">${dom.escape(session.agent_id)}</span></div>
              <div class="detail-meta">
                <div class="meta-chip">Inicio <span>${session.started_at}</span></div>
                <div class="meta-chip">Fin    <span>${session.ended_at || '—'}</span></div>
                <div class="meta-chip">Duración <span>${duration}</span></div>
                <div class="meta-chip">Eventos  <span>${session.event_count}</span></div>
              </div>
            </div>
            <button class="modal-btn confirm" data-delete="${session.id}" title="Eliminar esta sesión">✕ ELIMINAR</button>
          </div>
          <div class="events-toolbar">
            <input class="events-search" id="events-search" type="text"
                   placeholder="Buscar en eventos...">
            <div class="type-filter-btns" id="type-filters">
              ${types.map(t => `<button class="type-filter-btn" data-type="${t}">${t}</button>`).join('')}
            </div>
            <button class="sort-btn ${this.sortOrder === 'desc' ? 'active-sort' : ''}" id="btn-sort">
              ${this.sortOrder === 'desc' ? '↓ NUEVOS' : '↑ ANTIGUOS'}
            </button>
            <button class="scroll-btn" id="btn-scroll-top" title="Ir al principio">↑</button>
            <button class="scroll-btn" id="btn-scroll-bot" title="Ir al final">↓</button>
            <span class="ev-count" id="ev-count">${events.length} eventos</span>
          </div>
          <div class="events-wrap" id="events-wrap">
            <table>
              <thead><tr>
                <th class="sortable-ts">TIMESTAMP <span class="sort-arrow" id="sort-arrow">${this.sortOrder === 'desc' ? '▼' : '▲'}</span></th>
                <th>TIPO</th>
                <th>DATOS</th>
              </tr></thead>
              <tbody id="events-tbody"></tbody>
            </table>
          </div>`;
      }

      this.setupDetailListeners();
      this.renderDetailEvents();
    } catch (error) {
      console.error('Failed to load session detail:', error);
      if (panel) {
        panel.innerHTML = '<div class="detail-placeholder"><p>ERROR AL CARGAR</p></div>';
      }
    }
  }

  /**
   * Setup detail panel listeners
   * @private
   */
  setupDetailListeners() {
    const searchInput = dom.qs('#events-search');
    if (searchInput) {
      searchInput.addEventListener('input', () => this.filterDetailEvents());
    }

    const typeButtons = dom.qsa('.type-filter-btn');
    typeButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const type = btn.dataset.type;
        this.activeTypeFilter = this.activeTypeFilter === type ? null : type;
        
        // Update button states
        typeButtons.forEach(b => {
          b.classList.toggle('active', b.dataset.type === this.activeTypeFilter);
        });
        
        this.filterDetailEvents();
      });
    });

    const sortBtn = dom.qs('#btn-sort');
    if (sortBtn) {
      sortBtn.addEventListener('click', () => this.toggleSortOrder());
    }

    const scrollTopBtn = dom.qs('#btn-scroll-top');
    if (scrollTopBtn) {
      scrollTopBtn.addEventListener('click', () => this.scrollEventsTo('top'));
    }

    const scrollBotBtn = dom.qs('#btn-scroll-bot');
    if (scrollBotBtn) {
      scrollBotBtn.addEventListener('click', () => this.scrollEventsTo('bottom'));
    }

    const deleteBtn = dom.qs('[data-delete]');
    if (deleteBtn) {
      const sessionId = parseInt(deleteBtn.dataset.delete);
      const agentId = dom.qs('.agent-hl')?.textContent || '';
      deleteBtn.addEventListener('click', () => {
        this.confirmDeleteOne(sessionId, agentId);
      });
    }
  }

  /**
   * Filter and render detail events
   * @private
   */
  filterDetailEvents() {
    const query = (dom.qs('#events-search')?.value || '').toLowerCase();
    this.filteredEvents = this.store.filterEvents(this.activeTypeFilter, query);
    this.renderDetailEvents();
  }

  /**
   * Render detail events
   * @private
   */
  renderDetailEvents() {
    const tbody = dom.qs('#events-tbody');
    const evCount = dom.qs('#ev-count');

    if (evCount) {
      evCount.textContent = `${this.filteredEvents.length} / ${this.store.getCurrentEvents().length} eventos`;
    }

    if (!tbody) return;

    if (!this.filteredEvents.length) {
      tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;padding:30px;color:var(--muted);font-family:var(--mono);font-size:11px;letter-spacing:2px">SIN RESULTADOS</td></tr>';
      return;
    }

    const sorted = this.store.sortEvents(this.filteredEvents, this.sortOrder);
    tbody.innerHTML = sorted.map(event => {
      const dataStr = event.data
        ? (typeof event.data === 'string' ? event.data : JSON.stringify(event.data))
        : '—';

      return `
        <tr>
          <td class="col-ts">${event.timestamp}</td>
          <td class="col-type"><span class="type-badge type-${event.event_type}">${event.event_type}</span></td>
          <td class="col-data">${dom.escape(dataStr)}</td>
        </tr>`;
    }).join('');
  }

  /**
   * Toggle sort order
   * @private
   */
  toggleSortOrder() {
    this.sortOrder = this.sortOrder === 'desc' ? 'asc' : 'desc';

    const btn = dom.qs('#btn-sort');
    const arrow = dom.qs('#sort-arrow');

    if (btn) {
      btn.textContent = this.sortOrder === 'desc' ? '↓ NUEVOS' : '↑ ANTIGUOS';
      dom.toggleClass(btn, 'active-sort', this.sortOrder === 'desc');
    }

    if (arrow) {
      arrow.textContent = this.sortOrder === 'desc' ? '▼' : '▲';
    }

    this.renderDetailEvents();
  }

  /**
   * Scroll events to position
   * @private
   */
  scrollEventsTo(position) {
    const wrap = dom.qs('#events-wrap');
    if (wrap) {
      wrap.scrollTop = position === 'top' ? 0 : wrap.scrollHeight;
    }
  }

  /**
   * Setup page listeners
   * @private
   */
  setupListeners() {
    const searchSessions = dom.qs('#search-sessions');
    if (searchSessions) {
      searchSessions.addEventListener('input', () => this.filterSessions());
    }

    const delAllBtn = dom.qs('.del-all-btn');
    if (delAllBtn) {
      delAllBtn.addEventListener('click', () => this.confirmDeleteAll());
    }

    const modalOverlay = dom.qs('#modal-overlay');
    if (modalOverlay) {
      modalOverlay.addEventListener('click', (e) => {
        if (e.target === e.currentTarget) {
          this.closeModal();
        }
      });
    }

    const confirmBtn = dom.qs('#modal-confirm-btn');
    if (confirmBtn) {
      confirmBtn.addEventListener('click', () => this.executeDelete());
    }

    const cancelBtn = dom.qs('.modal-btn.cancel');
    if (cancelBtn) {
      cancelBtn.addEventListener('click', () => this.closeModal());
    }
  }

  /**
   * Filter sessions
   * @private
   */
  filterSessions() {
    const query = dom.qs('#search-sessions')?.value || '';
    this.filteredSessions = this.store.filterSessions(query);
    this.renderSessionList();
  }

  /**
   * Update session count display
   * @private
   */
  updateSessionCount() {
    const countEl = dom.qs('#session-count');
    if (countEl) {
      const count = this.store.getSessions().length;
      countEl.textContent = `${count} sesión${count !== 1 ? 'es' : ''}`;
    }
  }

  /**
   * Confirm delete one session
   * @private
   */
  confirmDeleteOne(sessionId, agentId) {
    this.deleteTarget = { type: 'one', id: sessionId };
    
    const titleEl = dom.qs('#modal-title');
    const bodyEl = dom.qs('#modal-body');
    const confirmBtn = dom.qs('.modal-btn.confirm[data-action="delete"]');

    if (titleEl) titleEl.textContent = 'ELIMINAR SESIÓN';
    if (bodyEl) {
      bodyEl.textContent = `¿Eliminar la sesión #${sessionId} del agente "${agentId}"? Se borrarán todos sus eventos. Esta acción no se puede deshacer.`;
    }
    if (confirmBtn) confirmBtn.dataset.action = 'delete';

    this.showModal();
  }

  /**
   * Confirm delete all sessions
   * @private
   */
  confirmDeleteAll() {
    const sessions = this.store.getSessions();
    if (!sessions.length) {
      this.showToast('No hay sesiones que eliminar');
      return;
    }

    this.deleteTarget = { type: 'all' };
    
    const titleEl = dom.qs('#modal-title');
    const bodyEl = dom.qs('#modal-body');

    if (titleEl) titleEl.textContent = 'ELIMINAR TODAS LAS SESIONES';
    if (bodyEl) {
      bodyEl.textContent = `¿Eliminar las ${sessions.length} sesiones y todos sus eventos? Esta acción no se puede deshacer.`;
    }

    this.showModal();
  }

  /**
   * Show modal
   * @private
   */
  showModal() {
    const overlay = dom.qs('#modal-overlay');
    if (overlay) {
      dom.toggleClass(overlay, 'show', true);
    }
  }

  /**
   * Close modal
   * @private
   */
  closeModal() {
    const overlay = dom.qs('#modal-overlay');
    if (overlay) {
      dom.toggleClass(overlay, 'show', false);
    }
    this.deleteTarget = null;
  }

  /**
   * Execute delete
   * @private
   */
  async executeDelete() {
    const target = this.deleteTarget;
    this.closeModal();

    if (!target) return;

    try {
      if (target.type === 'one') {
        await this.store.deleteSession(target.id);
        this.showToast(`Sesión #${target.id} eliminada`, 'success');
        
        if (this.selectedSessionId === target.id) {
          this.selectedSessionId = null;
          const detailPanel = dom.qs('#detail-panel');
          if (detailPanel) {
            detailPanel.innerHTML = '<div class="detail-placeholder"><div class="big-icon">◫</div><p>SELECCIONA UNA SESIÓN</p></div>';
          }
        }
      } else {
        const result = await this.store.deleteAllSessions();
        this.showToast(`${result.deleted_count} sesiones eliminadas`, 'success');
        this.selectedSessionId = null;
        const detailPanel = dom.qs('#detail-panel');
        if (detailPanel) {
          detailPanel.innerHTML = '<div class="detail-placeholder"><div class="big-icon">◫</div><p>SELECCIONA UNA SESIÓN</p></div>';
        }
      }

      // Reload sessions list
      await this.loadSessions();
    } catch (error) {
      console.error('Failed to delete:', error);
      this.showToast(`Error al eliminar: ${error.message}`, 'error');
    }
  }

  /**
   * Show toast notification
   * @private
   */
  showToast(message, type = '') {
    const container = dom.qs('#toast-container');
    if (!container) return;

    const toast = dom.createElement('div', {
      className: ['toast', type],
    });
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
      if (toast.parentElement) {
        toast.remove();
      }
    }, 3200);
  }

  /**
   * Show error message
   * @private
   */
  showError(message) {
    this.showToast(message, 'error');
  }

  /**
   * Format duration
   * @private
   */
  formatDuration(seconds) {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  }

  /**
   * Start auto-refresh interval
   * @private
   */
  startAutoRefresh() {
    if (this.autoRefreshInterval) {
      clearInterval(this.autoRefreshInterval);
    }

    this.autoRefreshInterval = setInterval(async () => {
      try {
        const prevCount = this.store.getSessions().length;
        await this.loadSessions();

        // If session is selected and open, reload its details
        if (this.selectedSessionId) {
          const sessions = this.store.getSessions();
          const session = sessions.find(s => s.id === this.selectedSessionId);
          if (session && !session.ended_at) {
            await this.loadSessionDetail(this.selectedSessionId);
          }
        }
      } catch (error) {
        console.error('Auto-refresh failed:', error);
      }
    }, 10000);
  }

  /**
   * Cleanup and shutdown
   */
  shutdown() {
    if (this.autoRefreshInterval) {
      clearInterval(this.autoRefreshInterval);
    }
    console.log('Sessions page shutdown');
  }
}

// ── Initialize on DOM ready ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  const page = new SessionsPage();
  await page.init();

  // Cleanup on page unload
  window.addEventListener('beforeunload', () => {
    page.shutdown();
  });

  // Expose for debugging
  window.sessionsPage = page;
});
