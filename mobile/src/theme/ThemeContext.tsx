import React, { createContext, useContext, useState, useMemo } from 'react';
import { colors, typography, spacing, radii, shadows } from './tokens';

export interface ThemeContextValue {
  colors: typeof colors;
  typography: typeof typography;
  spacing: typeof spacing;
  radii: typeof radii;
  shadows: typeof shadows;
  isDark: boolean;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  colors,
  typography,
  spacing,
  radii,
  shadows,
  isDark: false,
  toggleTheme: () => {},
});

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isDark, setIsDark] = useState(false);

  const value = useMemo<ThemeContextValue>(() => ({
    colors,
    typography,
    spacing,
    radii,
    shadows,
    isDark,
    toggleTheme: () => setIsDark((prev) => !prev),
  }), [isDark]);

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => useContext(ThemeContext);
