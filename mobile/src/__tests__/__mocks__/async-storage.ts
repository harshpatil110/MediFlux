const store: Record<string, string> = {};

const AsyncStorage = {
  getItem: async (key: string): Promise<string | null> => {
    return store[key] ?? null;
  },
  setItem: async (key: string, value: string): Promise<void> => {
    store[key] = value;
  },
  removeItem: async (key: string): Promise<void> => {
    delete store[key];
  },
  clear: async (): Promise<void> => {
    Object.keys(store).forEach((k) => delete store[k]);
  },
  getAllKeys: async (): Promise<string[]> => {
    return Object.keys(store);
  },
};

export default AsyncStorage;

