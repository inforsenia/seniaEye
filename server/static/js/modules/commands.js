/**
 * Command Dispatcher
 * Handles sending commands to agents via WebSocket
 */

import * as validation from '../utils/validation.js';
import { COMMANDS, ACTIONS } from '../config/constants.js';

/**
 * CommandDispatcher - Routes commands through WebSocket
 */
export class CommandDispatcher {
  constructor(webSocketManager) {
    this.ws = webSocketManager;
    this.pendingCommands = new Map();
    this.commandHistory = [];
  }

  /**
   * Send command to specific agent
   * @param {string} agentId - Target agent ID
   * @param {string} command - Command to send (START_MONITORING, STOP_MONITORING)
   * @returns {boolean} Whether send was successful
   */
  sendToAgent(agentId, command) {
    if (!validation.isString(agentId)) {
      console.warn('Agent ID must be a string');
      return false;
    }

    if (!validation.isString(command)) {
      console.warn('Command must be a string');
      return false;
    }

    if (!this.ws.isConnected()) {
      console.warn('WebSocket is not connected');
      return false;
    }

    const message = {
      action: ACTIONS.SEND_COMMAND,
      agent_id: agentId,
      command: command,
    };

    const success = this.ws.send(message);
    
    if (success) {
      this.recordCommand(agentId, command, 'individual');
    }

    return success;
  }

  /**
   * Send command to all agents
   * @param {string} command - Command to send
   * @returns {boolean} Whether send was successful
   */
  broadcastToAll(command) {
    if (!validation.isString(command)) {
      console.warn('Command must be a string');
      return false;
    }

    if (!this.ws.isConnected()) {
      console.warn('WebSocket is not connected');
      return false;
    }

    const message = {
      action: ACTIONS.BROADCAST_COMMAND,
      command: command,
    };

    const success = this.ws.send(message);
    
    if (success) {
      this.recordCommand('all', command, 'broadcast');
    }

    return success;
  }

  /**
   * Start monitoring on specific agent
   * @param {string} agentId
   * @returns {boolean}
   */
  startMonitoring(agentId) {
    return this.sendToAgent(agentId, COMMANDS.START_MONITORING);
  }

  /**
   * Stop monitoring on specific agent
   * @param {string} agentId
   * @returns {boolean}
   */
  stopMonitoring(agentId) {
    return this.sendToAgent(agentId, COMMANDS.STOP_MONITORING);
  }

  /**
   * Start monitoring on all agents
   * @returns {boolean}
   */
  startMonitoringAll() {
    return this.broadcastToAll(COMMANDS.START_MONITORING);
  }

  /**
   * Stop monitoring on all agents
   * @returns {boolean}
   */
  stopMonitoringAll() {
    return this.broadcastToAll(COMMANDS.STOP_MONITORING);
  }

  /**
   * Record command in history
   * @private
   */
  recordCommand(target, command, type) {
    const record = {
      timestamp: new Date().toISOString(),
      target,
      command,
      type, // 'individual' or 'broadcast'
    };
    
    this.commandHistory.push(record);
    
    // Keep only last 100 commands
    if (this.commandHistory.length > 100) {
      this.commandHistory.shift();
    }
  }

  /**
   * Get command history
   * @returns {Array<object>}
   */
  getHistory() {
    return [...this.commandHistory];
  }

  /**
   * Clear command history
   */
  clearHistory() {
    this.commandHistory = [];
  }
}
