/**
 * Storage Modules for SèniaEye
 * EventStore and AgentStore manage application state
 */

import * as validation from '../utils/validation.js';

/**
 * EventStore - Manages all events with filtering and searching
 */
export class EventStore {
  constructor(maxSize = 2000) {
    this.events = [];
    this.maxSize = maxSize;
  }

  /**
   * Add event to store (newest first)
   * @param {Event} event
   */
  add(event) {
    if (!validation.validateEvent(event).valid) {
      console.warn('Invalid event:', event);
      return;
    }
    
    this.events.unshift(event);
    
    // Trim to max size if needed
    if (this.events.length > this.maxSize) {
      this.events.length = this.maxSize;
    }
  }

  /**
   * Get all events
   * @returns {Array<Event>}
   */
  getAll() {
    return [...this.events];
  }

  /**
   * Get events matching predicate
   * @param {function} predicate - Filter function
   * @returns {Array<Event>}
   */
  filter(predicate) {
    if (!validation.isFunction(predicate)) {
      console.warn('Filter predicate must be a function');
      return [];
    }
    return this.events.filter(predicate);
  }

  /**
   * Search events by query string
   * @param {string} query - Search term
   * @returns {Array<Event>}
   */
  search(query) {
    if (!query || !validation.isString(query)) return this.events;
    
    const lowerQuery = query.toLowerCase();
    return this.events.filter(event => 
      JSON.stringify(event).toLowerCase().includes(lowerQuery)
    );
  }

  /**
   * Get events by agent ID
   * @param {string} agentId
   * @returns {Array<Event>}
   */
  getByAgent(agentId) {
    return this.events.filter(ev => ev.agent_id === agentId);
  }

  /**
   * Filter by type
   * @param {string} type
   * @returns {Array<Event>}
   */
  getByType(type) {
    return this.events.filter(ev => ev.type === type);
  }

  /**
   * Clear all events
   */
  clear() {
    this.events = [];
  }

  /**
   * Get total count
   * @returns {number}
   */
  getCount() {
    return this.events.length;
  }

  /**
   * Get last N events
   * @param {number} n
   * @returns {Array<Event>}
   */
  getTail(n = 10) {
    return this.events.slice(0, n);
  }
}

/**
 * AgentStore - Manages agent state and metadata
 */
export class AgentStore {
  constructor() {
    this.agents = {};
    this.colors = [];
    this.colorIndex = 0;
  }

  /**
   * Set available colors for agents
   * @param {Array<string>} colors - Hex color codes
   */
  setColors(colors) {
    if (!validation.isArray(colors)) {
      console.warn('Colors must be an array');
      return;
    }
    this.colors = colors;
  }

  /**
   * Get next color from palette
   * @returns {string} Hex color code
   */
  getNextColor() {
    if (!this.colors.length) return '#888';
    const color = this.colors[this.colorIndex % this.colors.length];
    this.colorIndex++;
    return color;
  }

  /**
   * Register or update agent
   * @param {string} id - Agent ID
   * @param {object} initial - Initial properties (online, status, etc.)
   * @returns {Agent}
   */
  register(id, initial = {}) {
    if (!validation.isString(id)) {
      console.warn('Agent ID must be a string');
      return null;
    }

    if (!this.agents[id]) {
      this.agents[id] = {
        id,
        online: initial.online ?? false,
        status: initial.status ?? 'offline',
        count: 0,
        color: initial.color ?? this.getNextColor(),
      };
    } else {
      // Update existing agent
      Object.assign(this.agents[id], initial);
    }

    return this.agents[id];
  }

  /**
   * Get agent by ID
   * @param {string} id
   * @returns {Agent|null}
   */
  getById(id) {
    return this.agents[id] || null;
  }

  /**
   * Get all agents
   * @returns {Array<Agent>}
   */
  getAll() {
    return Object.values(this.agents);
  }

  /**
   * Update agent status
   * @param {string} id
   * @param {string} status
   */
  setStatus(id, status) {
    if (this.agents[id]) {
      this.agents[id].status = status;
    }
  }

  /**
   * Mark agent as online
   * @param {string} id
   */
  markOnline(id) {
    if (this.agents[id]) {
      this.agents[id].online = true;
    }
  }

  /**
   * Mark agent as offline
   * @param {string} id
   */
  markOffline(id) {
    if (this.agents[id]) {
      this.agents[id].online = false;
      this.agents[id].status = 'offline';
    }
  }

  /**
   * Increment event count for agent
   * @param {string} id
   */
  incrementCount(id) {
    if (this.agents[id]) {
      this.agents[id].count++;
    }
  }

  /**
   * Reset event count for agent
   * @param {string} id
   */
  resetCount(id) {
    if (this.agents[id]) {
      this.agents[id].count = 0;
    }
  }

  /**
   * Reset all counts
   */
  resetAllCounts() {
    Object.values(this.agents).forEach(agent => {
      agent.count = 0;
    });
  }

  /**
   * Get count of online agents
   * @returns {number}
   */
  getOnlineCount() {
    return Object.values(this.agents).filter(a => a.online).length;
  }

  /**
   * Check if agent exists
   * @param {string} id
   * @returns {boolean}
   */
  has(id) {
    return id in this.agents;
  }

  /**
   * Remove agent
   * @param {string} id
   */
  remove(id) {
    delete this.agents[id];
  }

  /**
   * Clear all agents
   */
  clear() {
    this.agents = {};
  }
}
