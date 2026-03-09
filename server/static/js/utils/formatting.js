/**
 * Data Formatting Utilities
 * Format event data and other information for display
 */

/**
 * Extract only values from event data, removing keys
 * Useful for displaying event data without field names
 * @param {*} data - Data to extract values from
 * @returns {string} Formatted values only
 */
export function extractValuesOnly(data) {
  if (!data) return '—';
  
  if (typeof data === 'string') return data;
  if (typeof data === 'number') return String(data);
  if (typeof data === 'boolean') return data ? 'true' : 'false';
  if (data instanceof Date) return data.toISOString();
  
  // If it's an object or array, extract only the values
  if (typeof data === 'object') {
    try {
      if (Array.isArray(data)) {
        // For arrays, join the values with commas
        return data.map(v => extractValuesOnly(v)).join(', ');
      } else {
        // For objects, extract values and join them
        const values = Object.values(data)
          .filter(v => v !== null && v !== undefined && v !== '')
          .map(v => {
            if (typeof v === 'object') {
              return extractValuesOnly(v);
            }
            return String(v);
          });
        return values.join(' · ');
      }
    } catch {
      return String(data);
    }
  }
  
  return String(data);
}

/**
 * Format event data for display in log table
 * @param {object} event - Event object from server
 * @returns {string} Formatted display string
 */
export function formatEventData(event) {
  if (!event) return '—';
  
  switch (event.type) {
    case 'event':
      return cleanEventData(event.data);
    
    case 'agent_status':
      return `${extractValuesOnly(event.status)}`;
    
    case 'command_ack':
      return `${event.command} → ${event.success ? '✓' : '✗'}`;
    
    case 'broadcast_ack':
      return `${event.command} · ${event.count} alcanzados`;
    
    case 'dhcp_alert':
      return `⚠ ${event.data?.alert || ''} — ${event.data?.server_ip || ''}`;
    
    default:
      return cleanEventData(event.data);
  }
}

/**
 * Clean event data by removing timestamp field
 * @param {*} data - Data to clean
 * @returns {string} Cleaned data string
 */
function cleanEventData(data) {
  if (!data) return '—';
  if (typeof data === 'string') return data;
  if (typeof data === 'object') {
    const cleaned = { ...data };
    delete cleaned.timestamp;
    return extractValuesOnly(cleaned);
  }
  return extractValuesOnly(data);
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
 * @returns {string} Formatted timestamp (DD/MM/YYYY HH:mm:ss)
 */
export function formatTimestamp(isoTimestamp) {
  if (!isoTimestamp) return '—';
  
  try {
    const date = new Date(isoTimestamp);
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    
    return `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`;
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
