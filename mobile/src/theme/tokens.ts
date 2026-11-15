/**
 * Warm Editorial Minimalism — Mobile Design Tokens
 * Conforming strictly to design.md
 */

export const colors = {
  // Canvas & Surfaces
  canvas: {
    primary: '#E8E4D3', // Warm Ivory canvas
    alternate: '#DFDBCA', // Slightly deeper warm ivory tone
    surface: '#FFFFFF', // Clean white paper sheet
    elevated: '#F4F1E6', // Elevated panel surface
    input: '#FFFFFF',
    dark: '#031211',
  },

  // Typography
  text: {
    primary: '#031211', // Ink Black
    secondary: '#5C584E', // Charcoal
    muted: '#9E988A', // Muted / Hint
    onAccent: '#FFFFFF',
    inverse: '#F7F5F0',
  },

  // Accents (Electric Teal)
  accent: {
    primary: '#00AEBB', // Electric Teal
    hover: '#0095A0',
    subtle: 'rgba(0, 174, 187, 0.12)',
    border: '#00AEBB',
  },

  // Semantic Status
  status: {
    success: '#10B981', // Emerald (Normal / Connected / Approved)
    successSubtle: 'rgba(16, 185, 129, 0.12)',
    warning: '#F59E0B', // Amber (Pending / Threshold Alert)
    warningSubtle: 'rgba(245, 158, 11, 0.12)',
    danger: '#EF4444', // Coral / Critical Red (Quarantine / Breach)
    dangerSubtle: 'rgba(239, 68, 68, 0.12)',
    info: '#0284C7',
    infoSubtle: 'rgba(2, 132, 199, 0.12)',
  },

  // Structural 1px Borders
  border: {
    default: '#D8D3C3',
    subtle: '#E0DCCC',
    emphasis: 'rgba(3, 18, 17, 0.20)',
    focus: '#00AEBB',
  },
};

export const typography = {
  // Editorial Typographic Hierarchy
  fontSize: {
    display: 32,
    h1: 26,
    h2: 20,
    title: 17,
    body: 14,
    caption: 12,
    micro: 10,
  },
  fontWeight: {
    regular: '400' as const,
    medium: '500' as const,
    semibold: '600' as const,
    bold: '700' as const,
    black: '900' as const,
  },
  lineHeight: {
    tight: 1.2,
    normal: 1.45,
    relaxed: 1.6,
  },
  letterSpacing: {
    tight: -0.5,
    normal: 0,
    wide: 0.8,
    widest: 1.5, // Uppercase UI labels
  },
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  base: 16,
  lg: 20,
  xl: 24,
  xxl: 32,
};

export const radii = {
  none: 0,
  sm: 2,
  md: 4, // Preferred card & container radius
  lg: 8,
  full: 9999, // Dot indicators only — no pill action buttons
};

export const shadows = {
  subtle: {
    shadowColor: '#031211',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  none: {
    shadowColor: 'transparent',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0,
    shadowRadius: 0,
    elevation: 0,
  },
};

export type ThemeColors = typeof colors;
export type ThemeTypography = typeof typography;

