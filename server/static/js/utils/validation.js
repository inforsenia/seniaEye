/**
 * Validation Utilities
 * Type checking and contract validation
 */

/**
 * Check if value is defined and not null
 * @param {*} value - Value to check
 * @returns {boolean}
 */
export function isDefined(value) {
  return value !== undefined && value !== null;
}

/**
 * Check if value is a string
 * @param {*} value
 * @returns {boolean}
 */
export function isString(value) {
  return typeof value === 'string';
}

/**
 * Check if value is a number
 * @param {*} value
 * @returns {boolean}
 */
export function isNumber(value) {
  return typeof value === 'number' && !isNaN(value);
}

/**
 * Check if value is a boolean
 * @param {*} value
 * @returns {boolean}
 */
export function isBoolean(value) {
  return typeof value === 'boolean';
}

/**
 * Check if value is an object (but not array or null)
 * @param {*} value
 * @returns {boolean}
 */
export function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

/**
 * Check if value is an array
 * @param {*} value
 * @returns {boolean}
 */
export function isArray(value) {
  return Array.isArray(value);
}

/**
 * Check if value is a function
 * @param {*} value
 * @returns {boolean}
 */
export function isFunction(value) {
  return typeof value === 'function';
}

/**
 * Validate WebSocket message structure
 * @param {object} message - Message to validate
 * @returns {{valid: boolean, error?: string}}
 */
export function validateWebSocketMessage(message) {
  if (!isObject(message)) {
    return { valid: false, error: 'Message must be an object' };
  }
  
  if (!isDefined(message.type)) {
    return { valid: false, error: 'Message must have a type' };
  }
  
  if (!isString(message.type)) {
    return { valid: false, error: 'Message type must be a string' };
  }
  
  return { valid: true };
}

/**
 * Validate agent structure
 * @param {object} agent - Agent object to validate
 * @returns {{valid: boolean, error?: string}}
 */
export function validateAgent(agent) {
  if (!isObject(agent)) {
    return { valid: false, error: 'Agent must be an object' };
  }
  
  if (!isString(agent.id)) {
    return { valid: false, error: 'Agent must have an id (string)' };
  }
  
  return { valid: true };
}

/**
 * Validate event structure
 * @param {object} event - Event object to validate
 * @returns {{valid: boolean, error?: string}}
 */
export function validateEvent(event) {
  if (!isObject(event)) {
    return { valid: false, error: 'Event must be an object' };
  }
  
  if (!isString(event.type)) {
    return { valid: false, error: 'Event must have a type (string)' };
  }
  
  if (!isString(event.agent_id)) {
    return { valid: false, error: 'Event must have an agent_id (string)' };
  }
  
  return { valid: true };
}

/**
 * Validate command structure
 * @param {object} command - Command object to validate
 * @returns {{valid: boolean, error?: string}}
 */
export function validateCommand(command) {
  if (!isObject(command)) {
    return { valid: false, error: 'Command must be an object' };
  }
  
  if (!isDefined(command.action)) {
    return { valid: false, error: 'Command must have an action' };
  }
  
  return { valid: true };
}

/**
 * Validate IP address format (basic)
 * @param {string} ip - IP address to validate
 * @returns {boolean}
 */
export function isValidIP(ip) {
  if (!isString(ip)) return false;
  
  const parts = ip.split('.');
  if (parts.length !== 4) return false;
  
  return parts.every(part => {
    const num = parseInt(part, 10);
    return !isNaN(num) && num >= 0 && num <= 255;
  });
}

/**
 * Validate port number
 * @param {number} port - Port number to validate
 * @returns {boolean}
 */
export function isValidPort(port) {
  return isNumber(port) && port > 0 && port <= 65535;
}

/**
 * Check if URL is valid
 * @param {string} urlString - URL string to validate
 * @returns {boolean}
 */
export function isValidURL(urlString) {
  try {
    new URL(urlString);
    return true;
  } catch {
    return false;
  }
}

/**
 * Check if email is valid (basic)
 * @param {string} email - Email to validate
 * @returns {boolean}
 */
export function isValidEmail(email) {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return isString(email) && emailRegex.test(email);
}

/**
 * Ensure value fits within bounds
 * @param {number} value - Value to clamp
 * @param {number} min - Minimum (inclusive)
 * @param {number} max - Maximum (inclusive)
 * @returns {number}
 */
export function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

/**
 * Deep clone an object
 * @param {*} obj - Object to clone
 * @returns {*}
 */
export function deepClone(obj) {
  if (obj === null || typeof obj !== 'object') return obj;
  if (obj instanceof Date) return new Date(obj);
  if (obj instanceof Array) return obj.map(deepClone);
  if (obj instanceof Object) {
    const cloned = {};
    for (const key in obj) {
      if (obj.hasOwnProperty(key)) {
        cloned[key] = deepClone(obj[key]);
      }
    }
    return cloned;
  }
}
