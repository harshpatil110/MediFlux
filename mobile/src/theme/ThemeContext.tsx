import React, { createContext, useContext, useState, useEffect, useMemo } from 'react';
import { useColorScheme } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { lightColors, darkColors, typography, spacing, radii, shadows, ThemeColors } from './tokens';

export type ThemePreference = 'light' | 'dark' | 'system';

export interface ThemeContextValue {
  colors: ThemeColors;
  typography: typeof typography;
  spacing: typeof spacing;
  radii: typeof radii;
  shadows: typeof shadows;
  isDark: boolean;
  themePreference: ThemePreference;
  setThemePreference: (pref: ThemePreference) => void;
  toggleTheme: () => void;
}

const THEME_STORAGE_KEY = 'mediflux_theme_preference';

const ThemeContext = createContext<ThemeContextValue>({
  colors: lightColors,
  typography,
  spacing,
  radii,
  shadows,
  isDark: false,
  themePreference: 'system',
  setThemePreference: () => {},
  toggleTheme: () => {},
});

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const systemColorScheme = useColorScheme();
  const [themePreference, setThemePreferenceState] = useState<ThemePreference>('system');

  // Load saved preference from storage
  useEffect(() => {
    void (async () => {
      try {
        const saved = await AsyncStorage.getItem(THEME_STORAGE_KEY);
        if (saved === 'light' || saved === 'dark' || saved === 'system') {
          setThemePreferenceState(saved);
        }
      } catch {
        // Fallback to default
      }
    })();
  }, []);

  const setThemePreference = (pref: ThemePreference) => {
    setThemePreferenceState(pref);
    try {
      void AsyncStorage.setItem(THEME_STORAGE_KEY, pref);
    } catch {
      // Ignore storage write errors
    }
  };

  const isDark = useMemo(() => {
    if (themePreference === 'dark') return true;
    if (themePreference === 'light') return false;
    return systemColorScheme === 'dark';
  }, [themePreference, systemColorScheme]);

  const toggleTheme = () => {
    const nextPref: ThemePreference = isDark ? 'light' : 'dark';
    setThemePreference(nextPref);
  };

  const value = useMemo<ThemeContextValue>(() => ({
    colors: isDark ? darkColors : lightColors,
    typography,
    spacing,
    radii,
    shadows,
    isDark,
    themePreference,
    setThemePreference,
    toggleTheme,
  }), [isDark, themePreference]);

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => useContext(ThemeContext);
