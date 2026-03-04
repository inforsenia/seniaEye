/**
 * Constants for SèniaEye Dashboard
 * Centralized configuration for message types, commands, colors, and timeouts
 */

// ── WebSocket Message Types ──────────────────────────────────────────────
export const MESSAGE_TYPES = {
  SNAPSHOT: 'snapshot',
  AGENT_CONNECTED: 'agent_connected',
  AGENT_DISCONNECTED: 'agent_disconnected',
  AGENT_STATUS: 'agent_status',
  EVENT: 'event',
  COMMAND_ACK: 'command_ack',
  BROADCAST_ACK: 'broadcast_ack',
  DHCP_ALERT: 'dhcp_alert',
};

// ── Commands ─────────────────────────────────────────────────────────────
export const COMMANDS = {
  START_MONITORING: 'START_MONITORING',
  STOP_MONITORING: 'STOP_MONITORING',
};

// ── Agent Status ─────────────────────────────────────────────────────────
export const AGENT_STATUS = {
  WAITING: 'waiting',
  MONITORING: 'monitoring',
  OFFLINE: 'offline',
};

// ── Colors ──────────────────────────────────────────────────────────────
export const COLORS = {
  primary: '#00d4ff',      // Cyan
  green: '#00ff88',        // Green
  red: '#ff3e5e',          // Red
  yellow: '#ffd166',       // Yellow
  purple: '#c77dff',       // Purple
  orange: '#ff6b35',       // Orange
  teal: '#06d6a0',         // Teal
  crimson: '#8b1a1a',      // Dark red
  crimson2: '#b52020',     // Crimson
};

// ── Color Palette (for agent identification) ───────────────────────────
export const AGENT_COLORS = [
  '#00d4ff', '#ff6b35', '#00ff88', '#ffd166', '#c77dff',
  '#ff9f1c', '#06d6a0', '#ef476f', '#118ab2', '#f4a261',
  '#e9c46a', '#2a9d8f', '#e76f51', '#457b9d', '#a8dadc',
];

// ── Timeouts (milliseconds) ────────────────────────────────────────────
export const TIMEOUTS = {
  TOAST_DURATION: 3200,
  RECONNECT_DELAY: 3000,
  INTERNET_CHECK_INTERVAL: 30000,
  MAX_EVENTS: 2000,
  INET_TIMEOUT: 5000,
};

// ── API Endpoints ──────────────────────────────────────────────────────
export const API = {
  WS_DASHBOARD: '/ws/dashboard',
  INTERNET_STATUS: '/api/internet/status',
  INTERNET_ON: '/api/internet/1',
  INTERNET_OFF: '/api/internet/0',
  SESSIONS: '/api/sessions',
  BLOCK_LIST: '/api/block-list',
  PORT_RULES: '/api/port-rules',
};

// ── WebSocket Action Types (client → server) ────────────────────────────
export const ACTIONS = {
  SEND_COMMAND: 'send_command',
  BROADCAST_COMMAND: 'broadcast_command',
};
