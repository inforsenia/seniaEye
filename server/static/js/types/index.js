/**
 * Type Definitions for SèniaEye Dashboard
 * JSDoc type annotations for better IDE support and documentation
 * These are not enforced at runtime but help with development
 */

/**
 * @typedef {Object} Agent
 * @property {string} id - Unique agent identifier (IP or hostname)
 * @property {boolean} online - Whether agent is currently connected
 * @property {string} status - Agent status (waiting, monitoring, offline)
 * @property {number} count - Number of events from this agent
 * @property {string} color - Assigned color for UI identification
 */

/**
 * @typedef {Object} Event
 * @property {string} type - Event type (event, agent_connected, agent_status, etc.)
 * @property {string} agent_id - Source agent ID
 * @property {string} timestamp - ISO 8601 timestamp
 * @property {*} data - Event-specific data (varies by type)
 * @property {string} [command] - For command_ack messages
 * @property {boolean} [success] - For command_ack messages
 * @property {number} [count] - For broadcast_ack messages
 * @property {string} [status] - For agent_status messages
 */

/**
 * @typedef {Object} WebSocketMessage
 * @property {string} type - Message type (snapshot, agent_connected, event, etc.)
 * @property {Object<string, Agent>} [agents] - For snapshot messages
 * @property {Array<Event>} [events] - For snapshot messages
 * @property {string} [agent_id] - For agent-specific messages
 * @property {string} [command] - For command/broadcast ack
 * @property {number} [count] - For broadcast ack
 * @property {*} [data] - Additional message data
 */

/**
 * @typedef {Object} InternetStatus
 * @property {string} status - 'on' or 'off'
 */

/**
 * @typedef {Object} SessionInfo
 * @property {string} id - Session ID
 * @property {string} agent_id - Agent ID
 * @property {string} started_at - ISO timestamp
 * @property {string} [ended_at] - ISO timestamp
 * @property {number} duration_s - Duration in seconds
 * @property {number} event_count - Number of events in session
 */

/**
 * @typedef {Object} AppState
 * @property {WebSocketManager} ws - WebSocket connection manager
 * @property {EventStore} events - Event storage
 * @property {AgentStore} agents - Agent storage
 * @property {string|null} selectedAgent - Currently selected agent ID
 * @property {boolean} filterActive - Whether agent filter is active
 * @property {string} searchQuery - Current search query
 * @property {boolean} autoScroll - Whether to auto-scroll logs
 * @property {boolean} inetBusy - Whether internet control is busy
 */

/**
 * @typedef {Object} UIConfig
 * @property {HTMLElement} agentsGrid - Container for agent cards
 * @property {HTMLElement} logBody - Container for log rows
 * @property {HTMLElement} logScroll - Scrollable container for logs
 * @property {HTMLElement} searchInput - Search input element
 * @property {HTMLElement} filterBtn - Filter toggle button
 * @property {HTMLElement} autoBtn - Auto-scroll toggle button
 */

// Export as empty to satisfy module requirement
export {};
