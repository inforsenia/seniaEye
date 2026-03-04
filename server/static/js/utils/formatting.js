/**
 * Data Formatting Utilities
 * Format event data and other information for display
 */

/**
 * Format event data for display in log table
 * @param {object} event - Event object from server
 * @returns {string} Formatted display string
 */
export function formatEventData(event) {
  if (!event) return '—';
  
  switch (event.type) {
    case 'event':
      return formatData(event.data);
    
    case 'agent_status':
      return `estado → ${event.status}`;
    
    case 'command_ack':
      return `cmd:${event.command} | ok:${event.success}`;
    
    case 'broadcast_ack':
      return `cmd:${event.command} | alcanzados:${event.count}`;
    
    case 'dhcp_alert':
      return `⚠ ${event.data?.alert || ''} — ${event.data?.server_ip || ''}`;
    
    default:
      return formatData(event.data);
  }
}

/**
 * Format generic data object
 * @param {*} data - Data to format
 * @returns {string}
 */
export function formatData(data) {
  if (!data) return '—';
  if (typeof data === 'string') return data;
  if (typeof data === 'number') return String(data);
  if (typeof data === 'boolean') return data ? 'true' : 'false';
  if (data instanceof Date) return data.toISOString();
  
  // Try JSON stringify for objects
  try {
    return JSON.stringify(data);
  } catch {
    return String(data);
  }
}

/**
 * Format timestamp for display
 * @param {string} isoTimestamp - ISO 8601 timestamp
 * @returns {string} Formatted timestamp
 */
export function formatTimestamp(isoTimestamp) {
  if (!isoTimestamp) return '—';
  
  try {
    const date = new Date(isoTimestamp);
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    const ms = String(date.getMilliseconds()).padStart(3, '0');
    
    return `${hours}:${minutes}:${seconds}.${ms}`;
  } catch {
    return isoTimestamp;
  }
}

/**
 * Shorten IP address for display (show last 2 octets)
 * @param {string} ip - Full IP address
 * @returns {string} Shortened IP
 */
export function shortenIP(ip) {
  if (!ip || !ip.includes('.')) return ip;
  
  const parts = ip.split('.');
  if (parts.length >= 4) {
    return `${parts[2]}.${parts[3]}`;
  }
  return ip;
}

/**
 * Get human-readable status label
 * @param {string} status - Agent status
 * @returns {string}
 */
export function formatStatus(status) {
  const labels = {
    'waiting': 'ESPERANDO',
    'monitoring': 'MONITOREANDO',
    'offline': 'DESCONECTADO',
  };
  return labels[status] || status;
}

/**
 * Format byte size to human-readable
 * @param {number} bytes - Byte count
 * @returns {string}
 */
export function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Format duration in seconds to human-readable
 * @param {number} seconds - Duration in seconds
 * @returns {string}
 */
export function formatDuration(seconds) {
  if (!seconds) return '0s';
  
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  
  const parts = [];
  if (hours > 0) parts.push(`${hours}h`);
  if (minutes > 0) parts.push(`${minutes}m`);
  if (secs > 0 || parts.length === 0) parts.push(`${secs}s`);
  
  return parts.join(' ');
}

/**
 * Format count with suffix
 * @param {number} count - Count value
 * @param {string} singular - Singular label
 * @param {string} plural - Plural label (optional)
 * @returns {string}
 */
export function formatCount(count, singular, plural = null) {
  const label = count === 1 ? singular : (plural || singular + 's');
  return `${count} ${label}`;
}
