/**
 * Theme Configuration
 * References CSS custom properties used in the dashboard
 */

export const THEME = {
  // Background colors
  bg: 'var(--bg)',
  surface: 'var(--surface)',
  surface2: 'var(--surface2)',
  
  // Accent colors
  accent: 'var(--accent)',
  green: 'var(--green)',
  red: 'var(--red)',
  yellow: 'var(--yellow)',
  
  // Text and borders
  text: 'var(--text)',
  muted: 'var(--muted)',
  border: 'var(--border)',
  
  // Special colors
  crimson: 'var(--crimson)',
  crimson2: 'var(--crimson2)',
  
  // Fonts
  monoFont: "'Share Tech Mono', monospace",
  sansFont: "'Barlow', sans-serif",
  
  // Dimensions
  headerHeight: 'var(--header-h)',
  agentsHeight: 'var(--agents-h)',
};

/**
 * CSS variable names (for use with setProperty)
 * Useful when dynamically updating theme colors
 */
export const CSS_VARS = {
  BG: '--bg',
  SURFACE: '--surface',
  SURFACE2: '--surface2',
  BORDER: '--border',
  ACCENT: '--accent',
  GREEN: '--green',
  RED: '--red',
  YELLOW: '--yellow',
  TEXT: '--text',
  MUTED: '--muted',
  CRIMSON: '--crimson',
  CRIMSON2: '--crimson2',
};
