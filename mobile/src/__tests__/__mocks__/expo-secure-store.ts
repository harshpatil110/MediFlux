const secureStore: Record<string, string> = {};

export async function getItemAsync(key: string): Promise<string | null> {
  return secureStore[key] ?? null;
}

export async function setItemAsync(key: string, value: string): Promise<void> {
  secureStore[key] = value;
}

export async function deleteItemAsync(key: string): Promise<void> {
  delete secureStore[key];
}

export default {
  getItemAsync,
  setItemAsync,
  deleteItemAsync,
};

