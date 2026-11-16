export const Platform = {
  OS: 'web',
  select: (objs: Record<string, any>) => objs.web ?? objs.default,
};

export const StyleSheet = {
  create: (styles: Record<string, any>) => styles,
  flatten: (style: any) => style,
};

export const AppState = {
  currentState: 'active',
  addEventListener: (_type: string, _handler: (state: string) => void) => ({
    remove: () => {},
  }),
};

export const View = 'View';
export const Text = 'Text';
export const TouchableOpacity = 'TouchableOpacity';
export const FlatList = 'FlatList';
export const ActivityIndicator = 'ActivityIndicator';

export default {
  Platform,
  StyleSheet,
  AppState,
  View,
  Text,
  TouchableOpacity,
  FlatList,
  ActivityIndicator,
};

