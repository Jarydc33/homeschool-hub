/**
 * Tally's colours, from the logo (the same as the Streamlit app's): navy,
 * orange, and a soft blue-grey. Light screens for everyday reading.
 */

export const Colors = {
  navy: '#1B2540',
  orange: '#E2672F',
  // Darker orange, readable as small text on white.
  orangeText: '#B84E1C',
  blueGrey: '#C9CFDC',
  background: '#FFFFFF',
  surface: '#F2F4F8',
  border: '#DDE1EA',
  text: '#1B2540',
  textMuted: '#5A6378',
  done: '#2E7D4F',
  danger: '#B3261E',
} as const;

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
} as const;

export const Radius = 10;

// Keeps screens readable on wide desktop windows.
export const MaxContentWidth = 720;
