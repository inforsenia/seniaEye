/**
 * WebSocket Manager
 * Handles connection lifecycle and message handling
 */

import * as validation from '../utils/validation.js';

/**
 * WebSocketManager - Low-level WebSocket connection management
 */
export class WebSocketManager {
  constructor() {
    this.ws = null;
    this.url = '';
    this.handlers = {};
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.reconnectDelay = 3000;
    this.isIntentionallyClosed = false;
  }

  /**
   * Connect to WebSocket server
   * @param {string} url - WebSocket URL
   * @param {object} handlers - Event handlers {onOpen, onMessage, onClose, onError}
   * @returns {Promise<void>}
   */
  connect(url, handlers = {}) {
    return new Promise((resolve, reject) => {
      if (!validation.isString(url)) {
        reject(new Error('URL must be a string'));
        return;
      }

      this.url = url;
      this.handlers = handlers;
      this.isIntentionallyClosed = false;

      try {
        this.ws = new WebSocket(url);
        
        this.ws.onopen = () => {
          this.reconnectAttempts = 0;
          this.handlers.onOpen?.();
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            if (!validation.validateWebSocketMessage(message).valid) {
              console.warn('Invalid message received:', message);
              return;
            }
            this.handlers.onMessage?.(message);
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
          }
        };

        this.ws.onclose = () => {
          this.handlers.onClose?.();
          if (!this.isIntentionallyClosed) {
            this.attemptReconnect();
          }
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          this.handlers.onError?.(error);
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * Send message through WebSocket
   * @param {object} message - Message to send (will be JSON stringified)
   * @returns {boolean} Success status
   */
  send(message) {
    if (!this.isConnected()) {
      console.warn('WebSocket is not connected');
      return false;
    }

    if (!validation.isObject(message)) {
      console.warn('Message must be an object');
      return false;
    }

    try {
      this.ws.send(JSON.stringify(message));
      return true;
    } catch (error) {
      console.error('Failed to send WebSocket message:', error);
      return false;
    }
  }

  /**
   * Check if WebSocket is connected
   * @returns {boolean}
   */
  isConnected() {
    return this.ws && this.ws.readyState === WebSocket.OPEN;
  }

  /**
   * Gracefully close connection
   */
  close() {
    this.isIntentionallyClosed = true;
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /**
   * Attempt to reconnect to server
   * @private
   */
  attemptReconnect() {
    if (this.isIntentionallyClosed) {
      return;
    }

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      this.handlers.onMaxReconnectAttempts?.();
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * this.reconnectAttempts;
    
    console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts}) in ${delay}ms...`);
    
    setTimeout(() => {
      this.connect(this.url, this.handlers).catch(error => {
        console.error('Reconnection failed:', error);
        this.attemptReconnect();
      });
    }, delay);
  }

  /**
   * Get connection readyState
   * @returns {number} WebSocket.CONNECTING, OPEN, CLOSING, CLOSED
   */
  getReadyState() {
    return this.ws?.readyState ?? WebSocket.CLOSED;
  }

  /**
   * Get readyState as string
   * @returns {string}
   */
  getReadyStateString() {
    const states = {
      [WebSocket.CONNECTING]: 'CONNECTING',
      [WebSocket.OPEN]: 'OPEN',
      [WebSocket.CLOSING]: 'CLOSING',
      [WebSocket.CLOSED]: 'CLOSED',
    };
    return states[this.getReadyState()] || 'UNKNOWN';
  }
}
