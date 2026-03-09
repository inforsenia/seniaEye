/**
 * SèniaEye Dashboard - Main Coordinator
 * Orchestrates all modules and manages application flow
 */

import { WebSocketManager } from '../modules/websocket.js';
import { EventStore, AgentStore } from '../modules/storage.js';
import { CommandDispatcher } from '../modules/commands.js';
import { EventProcessor } from '../modules/events.js';
import { DashboardRenderer } from '../ui/renderer.js';
import * as binders from '../ui/binders.js';
import * as constants from '../config/constants.js';
import * as dom from '../utils/dom.js';

/**
 * Dashboard - Main application class
 */
class Dashboard {
  constructor() {
    // State management
    this.eventStore = new EventStore(constants.TIMEOUTS.MAX_EVENTS);
    this.agentStore = new AgentStore();
    this.agentStore.setColors(constants.AGENT_COLORS);

    // Communication
    this.ws = new WebSocketManager();
    this.commands = new CommandDispatcher(this.ws);
    this.eventProcessor = new EventProcessor();

    // UI
    this.renderer = new DashboardRenderer();

    // Application state
    this.selectedAgent = null;
    this.filterActive = false;
    this.autoScroll = true;
    this.inetBusy = false;
    this.internetCheckInterval = null;
  }

  /**
   * Initialize the dashboard
   */
  async init() {
    console.log('Initializing SèniaEye Dashboard...');

    try {
      // Setup UI
      this.renderer.detectElements();

      // Setup WebSocket
      await this.setupWebSocket();

      // Setup message handling
      this.setupMessageHandlers();

      // Setup UI listeners
      this.setupUIListeners();

      // Setup initial state
      this.checkInternetStatus();
      this.internetCheckInterval = setInterval(
        () => this.checkInternetStatus(),
        constants.TIMEOUTS.INTERNET_CHECK_INTERVAL
      );

      console.log('Dashboard initialized successfully');
    } catch (error) {
      console.error('Failed to initialize dashboard:', error);
      this.renderer.showToast('Error al inicializar dashboard', 'err');
    }
  }

  /**
   * Setup WebSocket connection
   * @private
   */
  async setupWebSocket() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${proto}://${location.host}${constants.API.WS_DASHBOARD}`;

    return this.ws.connect(url, {
      onOpen: () => this.handleWebSocketOpen(),
      onMessage: (msg) => this.handleWebSocketMessage(msg),
      onClose: () => this.handleWebSocketClose(),
      onError: (err) => this.handleWebSocketError(err),
    });
  }

  /**
   * WebSocket opened
   * @private
   */
  handleWebSocketOpen() {
    console.log('WebSocket connected');
    this.renderer.setWebSocketStatus('ok', 'CONECTADO');
    this.renderer.showToast('Dashboard conectado', 'ok');
  }

  /**
   * WebSocket closed
   * @private
   */
  handleWebSocketClose() {
    console.log('WebSocket disconnected');
    this.renderer.setWebSocketStatus('err', 'DESCONECTADO');
    this.renderer.showToast('Reconectando...', 'err');
  }

  /**
   * WebSocket error
   * @private
   */
  handleWebSocketError(error) {
    console.error('WebSocket error:', error);
    this.renderer.setWebSocketStatus('err', 'ERROR');
  }

  /**
   * Handle incoming WebSocket message
   * @private
   */
  handleWebSocketMessage(message) {
    this.eventProcessor.process(message);
  }

  /**
   * Setup message handlers for each message type
   * @private
   */
  setupMessageHandlers() {
    this.eventProcessor.onMultiple({
      [constants.MESSAGE_TYPES.SNAPSHOT]: (msg) => this.handleSnapshot(msg),
      [constants.MESSAGE_TYPES.AGENT_CONNECTED]: (msg) => this.handleAgentConnected(msg),
      [constants.MESSAGE_TYPES.AGENT_DISCONNECTED]: (msg) => this.handleAgentDisconnected(msg),
      [constants.MESSAGE_TYPES.AGENT_STATUS]: (msg) => this.handleAgentStatus(msg),
      [constants.MESSAGE_TYPES.EVENT]: (msg) => this.handleEvent(msg),
      [constants.MESSAGE_TYPES.COMMAND_ACK]: (msg) => this.handleCommandAck(msg),
      [constants.MESSAGE_TYPES.BROADCAST_ACK]: (msg) => this.handleBroadcastAck(msg),
      [constants.MESSAGE_TYPES.DHCP_ALERT]: (msg) => this.handleEvent(msg),
    });
  }

  /**
   * Handle snapshot (initial state + recent events)
   * @private
   */
  handleSnapshot(message) {
    console.log('Snapshot received');

    // Load agents
    if (message.agents) {
      Object.entries(message.agents).forEach(([id, agentData]) => {
        this.agentStore.register(id, {
          online: agentData.online,
          status: agentData.status,
        });
      });
    }

    // Load events
    if (message.events && Array.isArray(message.events)) {
      message.events.forEach(event => this.eventStore.add(event));
    }

    this.renderUI();
  }

  /**
   * Handle agent connected
   * @private
   */
  handleAgentConnected(message) {
    const { agent_id, status } = message;

    this.agentStore.register(agent_id, {
      online: true,
      status: status || 'waiting',
    });

    this.eventStore.add(message);
    this.renderUI();
    this.renderer.showToast(`Conectado: ${agent_id}`, 'ok');
  }

  /**
   * Handle agent disconnected
   * @private
   */
  handleAgentDisconnected(message) {
    const { agent_id } = message;

    this.agentStore.markOffline(agent_id);
    this.eventStore.add(message);
    this.renderUI();
    this.renderer.showToast(`Desconectado: ${agent_id}`, 'err');
  }

  /**
   * Handle agent status update
   * @private
   */
  handleAgentStatus(message) {
    const { agent_id, status } = message;

    this.agentStore.setStatus(agent_id, status);
    this.eventStore.add(message);
    this.renderUI();
  }

  /**
   * Handle event
   * @private
   */
  handleEvent(message) {
    this.agentStore.incrementCount(message.agent_id);
    this.eventStore.add(message);
    
    // Only add to UI if passes current filters
    if (this.passesFilter(message)) {
      this.renderer.prependEvent(message, this.getAgentColorMap());
      this.updateEventBadge();
    }

    if (this.autoScroll) {
      this.renderer.scrollLogsToTop();
    }

    this.renderer.updateStats(
      this.agentStore.getOnlineCount(),
      this.eventStore.getCount()
    );
  }

  /**
   * Handle command acknowledgment
   * @private
   */
  handleCommandAck(message) {
    const { command, success, agent_id } = message;
    const cmdLabel = command === constants.COMMANDS.START_MONITORING ? 'START' : 'STOP';
    const status = success ? 'ok' : 'err';
    const text = success
      ? `${cmdLabel} → ${agent_id}: OK`
      : `${cmdLabel} → ${agent_id}: sin agente`;

    this.renderer.showToast(text, status);
    this.eventStore.add(message);
  }

  /**
   * Handle broadcast acknowledgment
   * @private
   */
  handleBroadcastAck(message) {
    const { command, count } = message;
    const cmdLabel = command === constants.COMMANDS.START_MONITORING
      ? 'INICIAR'
      : 'DETENER';

    this.renderer.showToast(
      `${cmdLabel} TODOS: ${count} agentes`,
      'ok'
    );
    this.eventStore.add(message);
  }

  /**
   * Setup UI event listeners
   * @private
   */
  setupUIListeners() {
    binders.bindAllDashboardListeners({
      onSearch: (query) => this.handleSearch(query),
      onClear: () => this.handleClearLogs(),
      onToggleAuto: () => this.handleToggleAutoScroll(),
      onStartAll: () => this.handleStartAll(),
      onStopAll: () => this.handleStopAll(),
      onToggleFilter: () => this.handleToggleFilter(),
      onInternetOn: () => this.handleSetInternet(1),
      onInternetOff: () => this.handleSetInternet(0),
    });

    // Bind scroll listener
    const logScroll = dom.qs('#logs-scroll');
    if (logScroll) {
      binders.bindScrollListener(logScroll, (isAtTop) => {
        if (isAtTop && !this.autoScroll) {
          this.autoScroll = true;
          this.renderer.setAutoScrollActive(true);
        }
      });
    }
  }

  /**
   * Handle search input
   * @private
   */
  handleSearch(query) {
    const filtered = query
      ? this.eventStore.search(query)
      : this.filterBySelectedAgent();

    this.renderer.renderEvents(filtered, this.getAgentColorMap());
    this.updateEventBadge();
  }

  /**
   * Handle clear logs
   * @private
   */
  handleClearLogs() {
    this.eventStore.clear();
    this.agentStore.resetAllCounts();
    this.renderer.clearAllLogs();
    this.updateEventBadge();
    this.renderer.updateStats(
      this.agentStore.getOnlineCount(),
      this.eventStore.getCount()
    );
  }

  /**
   * Handle toggle auto-scroll
   * @private
   */
  handleToggleAutoScroll() {
    this.autoScroll = !this.autoScroll;
    this.renderer.setAutoScrollActive(this.autoScroll);
  }

  /**
   * Handle start all agents
   * @private
   */
  handleStartAll() {
    const hasOnline = this.agentStore.getAll().some(a => a.online);
    if (!hasOnline) {
      this.renderer.showToast('Sin agentes online', 'warn');
      return;
    }
    this.commands.startMonitoringAll();
  }

  /**
   * Handle stop all agents
   * @private
   */
  handleStopAll() {
    const hasOnline = this.agentStore.getAll().some(a => a.online);
    if (!hasOnline) {
      this.renderer.showToast('Sin agentes online', 'warn');
      return;
    }
    this.commands.stopMonitoringAll();
  }

  /**
   * Handle filter toggle
   * @private
   */
  handleToggleFilter() {
    if (!this.selectedAgent) {
      this.renderer.showToast('Selecciona primero un agente', 'warn');
      return;
    }

    this.filterActive = !this.filterActive;
    this.renderer.setFilterButtonActive(this.filterActive);
    this.applyFilters();
  }

  /**
   * Handle agent selection (from grid)
   * @private
   */
  handleSelectAgent(agentId) {
    this.selectedAgent = this.selectedAgent === agentId ? null : agentId;
    
    if (!this.selectedAgent) {
      this.filterActive = false;
      this.renderer.setFilterButtonActive(false);
    }

    this.renderAgentGrid();
    this.applyFilters();
  }

  /**
   * Handle start monitoring on agent
   * @private
   */
  handleStartAgent(agentId) {
    this.commands.startMonitoring(agentId);
  }

  /**
   * Handle stop monitoring on agent
   * @private
   */
  handleStopAgent(agentId) {
    this.commands.stopMonitoring(agentId);
  }

  /**
   * Handle internet toggle
   * @private
   */
  async handleSetInternet(value) {
    if (this.inetBusy) return;

    this.inetBusy = true;
    const status = value ? 'ACTIVANDO...' : 'CORTANDO...';
    this.renderer.setInternetStatus('checking', true, true);

    try {
      const url = value
        ? constants.API.INTERNET_ON
        : constants.API.INTERNET_OFF;
      
      const response = await fetch(url, { method: 'POST' });
      const data = await response.json();
      const isOn = data.status === 'on';

      this.renderer.setInternetStatus(isOn ? 'on' : 'off', false, false);
      this.renderer.showToast(
        isOn ? 'Internet activado' : 'Internet cortado',
        isOn ? 'ok' : 'warn'
      );
    } catch (error) {
      console.error('Failed to set internet:', error);
      this.renderer.showToast('Error al cambiar internet', 'err');
      this.checkInternetStatus();
    } finally {
      this.inetBusy = false;
    }
  }

  /**
   * Check internet status
   * @private
   */
  async checkInternetStatus() {
    try {
      const response = await fetch(constants.API.INTERNET_STATUS, {
        signal: AbortSignal.timeout(constants.TIMEOUTS.INET_TIMEOUT),
      });
      const data = await response.json();
      const isOn = data.status === 'on';
      this.renderer.setInternetStatus(isOn ? 'on' : 'off', false, false);
    } catch (error) {
      console.error('Failed to check internet:', error);
      this.renderer.setInternetStatus('off', false, false);
    }
  }

  /**
   * Apply current filters to events
   * @private
   */
  applyFilters() {
    const filtered = this.filterBySelectedAgent();
    this.renderer.renderEvents(filtered, this.getAgentColorMap());
    this.updateEventBadge();
  }

  /**
   * Filter by selected agent and DNS quality
   * @private
   */
  filterBySelectedAgent() {
    let events = this.filterActive && this.selectedAgent
      ? this.eventStore.getByAgent(this.selectedAgent)
      : this.eventStore.getAll();
    
    // Filter out DNS violations without resolved IPs
    events = events.filter(event => {
      if (event.type === 'dns_violation' && event.data) {
        const desc = typeof event.data === 'string' ? event.data : (event.data.description || '');
        // Only show if it has a resolved IP (not "unknown")
        return desc && desc.includes('Resolved to:') && !desc.includes('Resolved to: unknown');
      }
      return true; // Show non-DNS events
    });
    
    return events;
  }

  /**
   * Check if event passes current filters
   * @private
   */
  passesFilter(event) {
    if (this.filterActive && this.selectedAgent && event.agent_id !== this.selectedAgent) {
      return false;
    }
    return true;
  }

  /**
   * Get agent color map for rendering
   * @private
   */
  getAgentColorMap() {
    const map = {};
    this.agentStore.getAll().forEach(agent => {
      map[agent.id] = agent.color;
    });
    return map;
  }

  /**
   * Render agent grid with handlers
   * @private
   */
  renderAgentGrid() {
    this.renderer.renderAgents(
      this.agentStore.getAll(),
      this.selectedAgent,
      {
        onSelect: (id) => this.handleSelectAgent(id),
        onStart: (id) => this.handleStartAgent(id),
        onStop: (id) => this.handleStopAgent(id),
      }
    );
  }

  /**
   * Render events with handlers
   * @private
   */
  renderEventTable() {
    const filtered = this.filterBySelectedAgent();
    this.renderer.renderEvents(filtered, this.getAgentColorMap());
    this.updateEventBadge();
  }

  /**
   * Update event count badge
   * @private
   */
  updateEventBadge() {
    const filtered = this.filterBySelectedAgent();
    this.renderer.updateEventBadge(filtered.length, this.eventStore.getCount());
  }

  /**
   * Full UI render
   * @private
   */
  renderUI() {
    this.renderAgentGrid();
    this.renderEventTable();
    this.renderer.updateStats(
      this.agentStore.getOnlineCount(),
      this.eventStore.getCount()
    );
  }

  /**
   * Cleanup and shutdown
   */
  shutdown() {
    if (this.internetCheckInterval) {
      clearInterval(this.internetCheckInterval);
    }
    this.ws.close();
    console.log('Dashboard shutdown');
  }
}

// ── Initialize on DOM ready ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  const dashboard = new Dashboard();
  await dashboard.init();

  // Cleanup on page unload
  window.addEventListener('beforeunload', () => {
    dashboard.shutdown();
  });

  // Expose for debugging
  window.dashboard = dashboard;
});
