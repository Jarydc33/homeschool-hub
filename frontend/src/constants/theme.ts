/**
 * Tally's colours, from the logo (the same as the Streamlit app's): navy,
 * orange, and a soft blue-grey. Light screens for everyday reading.
 */

export const Colors = {
  navy: '#1B2540',
  // The sidebar: a lighter navy for hover and the current page, and text
  // that reads on navy (the landing page's colours).
  navyRaised: '#26314F',
  navyLine: '#323D5C',
  onNavy: '#EEF1F6',
  onNavyMuted: '#B9C1D3',
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

/**
 * Inter, as on the landing page, loaded in the root layout. Each weight is
 * its own font, so set `fontFamily` from here instead of `fontWeight`:
 * a custom font ignores `fontWeight` on Android.
 */
export const Fonts = {
  regular: 'Inter_400Regular',
  medium: 'Inter_500Medium',
  semibold: 'Inter_600SemiBold',
  bold: 'Inter_700Bold',
  extrabold: 'Inter_800ExtraBold',
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

// Screens with two columns on a computer, such as the Dashboard.
export const WideContentWidth = 1120;
