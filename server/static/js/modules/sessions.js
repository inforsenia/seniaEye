/**
 * Sessions Module
 * API calls and state management for sessions history page
 */

import * as validation from '../utils/validation.js';

/**
 * SessionStore - Manages session and event data
 */
export class SessionStore {
  constructor() {
    this.sessions = [];
    this.currentSession = null;
    this.currentEvents = [];
  }

  /**
   * Fetch all sessions
   * @returns {Promise<Array>}
   */
  async fetchSessions() {
    try {
      const response = await fetch('/api/sessions');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      this.sessions = await response.json();
      return [...this.sessions];
    } catch (error) {
      console.error('Failed to fetch sessions:', error);
      throw error;
    }
  }

  /**
   * Fetch session details
   * @param {number} sessionId
   * @returns {Promise<{session, events}>}
   */
  async fetchSessionDetails(sessionId) {
    try {
      const response = await fetch(`/api/sessions/${sessionId}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      
      this.currentSession = data.session;
      this.currentEvents = data.events || [];
      
      return data;
    } catch (error) {
      console.error('Failed to fetch session details:', error);
      throw error;
    }
  }

  /**
   * Delete single session
   * @param {number} sessionId
   * @returns {Promise<object>}
   */
  async deleteSession(sessionId) {
    try {
      const response = await fetch(`/api/sessions/${sessionId}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Failed to delete session:', error);
      throw error;
    }
  }

  /**
   * Delete all sessions
   * @returns {Promise<object>}
   */
  async deleteAllSessions() {
    try {
      const response = await fetch('/api/sessions', {
        method: 'DELETE',
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Failed to delete all sessions:', error);
      throw error;
    }
  }

  /**
   * Get all sessions
   * @returns {Array}
   */
  getSessions() {
    return [...this.sessions];
  }

  /**
   * Filter sessions by agent ID
   * @param {string} query
   * @returns {Array}
   */
  filterSessions(query) {
    if (!query) return this.getSessions();
    
    const q = query.toLowerCase();
    return this.sessions.filter(s => 
      s.agent_id.toLowerCase().includes(q)
    );
  }

  /**
   * Get unique event types in current session
   * @returns {Array<string>}
   */
  getEventTypes() {
    if (!this.currentEvents) return [];
    return [...new Set(this.currentEvents.map(e => e.event_type))];
  }

  /**
   * Filter events by type and/or search query
   * @param {string} type - Event type filter (null for all)
   * @param {string} query - Text search query
   * @returns {Array}
   */
  filterEvents(type = null, query = '') {
    let filtered = [...this.currentEvents];
    
    if (type) {
      filtered = filtered.filter(ev => ev.event_type === type);
    }
    
    if (query) {
      const q = query.toLowerCase();
      filtered = filtered.filter(ev =>
        JSON.stringify(ev).toLowerCase().includes(q)
      );
    }
    
    return filtered;
  }

  /**
   * Sort events by timestamp
   * @param {Array} events - Events to sort
   * @param {string} order - 'asc' or 'desc'
   * @returns {Array}
   */
  sortEvents(events, order = 'desc') {
    const sorted = [...events];
    return sorted.sort((a, b) => {
      const timeA = new Date(a.timestamp).getTime();
      const timeB = new Date(b.timestamp).getTime();
      return order === 'desc' ? timeB - timeA : timeA - timeB;
    });
  }

  /**
   * Get current session
   * @returns {object|null}
   */
  getCurrentSession() {
    return this.currentSession;
  }

  /**
   * Get current events
   * @returns {Array}
   */
  getCurrentEvents() {
    return [...this.currentEvents];
  }

  /**
   * Clear current session data
   */
  clearCurrent() {
    this.currentSession = null;
    this.currentEvents = [];
  }
}
