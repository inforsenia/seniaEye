/**
 * Event Processor
 * Routes and processes WebSocket messages
 */

import { MESSAGE_TYPES } from '../config/constants.js';

/**
 * EventProcessor - Routes messages to appropriate handlers
 */
export class EventProcessor {
  constructor() {
    this.handlers = {};
    this.middleware = [];
    this.setupDefaultHandlers();
  }

  /**
   * Setup default message handlers (can be overridden)
   * @private
   */
  setupDefaultHandlers() {
    // Default handlers do nothing but log
    Object.values(MESSAGE_TYPES).forEach(type => {
      this.handlers[type] = (message) => {
        console.debug(`[${type}]`, message);
      };
    });
  }

  /**
   * Register handler for message type
   * @param {string} messageType - Type of message to handle
   * @param {function} handler - Handler function(message)
   */
  on(messageType, handler) {
    if (typeof handler !== 'function') {
      console.warn('Handler must be a function');
      return;
    }
    this.handlers[messageType] = handler;
  }

  /**
   * Register multiple handlers
   * @param {object} handlers - Map of {type: handler}
   */
  onMultiple(handlers) {
    if (typeof handlers !== 'object') {
      console.warn('Handlers must be an object');
      return;
    }
    Object.entries(handlers).forEach(([type, handler]) => {
      this.on(type, handler);
    });
  }

  /**
   * Add middleware that processes all messages
   * @param {function} middleware - Middleware function(message) -> possibly modified message
   */
  use(middleware) {
    if (typeof middleware !== 'function') {
      console.warn('Middleware must be a function');
      return;
    }
    this.middleware.push(middleware);
  }

  /**
   * Process incoming message
   * @param {object} message - Message from server
   */
  process(message) {
    if (!message || typeof message !== 'object') {
      console.warn('Invalid message:', message);
      return;
    }

    // Apply middleware
    let processedMessage = message;
    for (const mw of this.middleware) {
      try {
        processedMessage = mw(processedMessage) || processedMessage;
      } catch (error) {
        console.error('Middleware error:', error);
      }
    }

    // Route to handler
    const type = processedMessage.type;
    if (type && this.handlers[type]) {
      try {
        this.handlers[type](processedMessage);
      } catch (error) {
        console.error(`Error in handler for ${type}:`, error);
      }
    } else {
      console.warn(`No handler for message type: ${type}`);
    }
  }

  /**
   * Process multiple messages
   * @param {Array<object>} messages
   */
  processMultiple(messages) {
    if (!Array.isArray(messages)) {
      console.warn('Messages must be an array');
      return;
    }
    messages.forEach(msg => this.process(msg));
  }

  /**
   * Get all registered handlers
   * @returns {object} Map of {type: handler}
   */
  getHandlers() {
    return { ...this.handlers };
  }

  /**
   * Check if handler exists for type
   * @param {string} type
   * @returns {boolean}
   */
  hasHandler(type) {
    return type in this.handlers;
  }

  /**
   * Remove handler for type (resets to default)
   * @param {string} type
   */
  removeHandler(type) {
    if (type in this.handlers) {
      this.handlers[type] = (message) => {
        console.debug(`[${type}]`, message);
      };
    }
  }

  /**
   * Clear all middleware
   */
  clearMiddleware() {
    this.middleware = [];
  }

  /**
   * Get middleware count
   * @returns {number}
   */
  getMiddlewareCount() {
    return this.middleware.length;
  }
}
