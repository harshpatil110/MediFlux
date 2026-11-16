const mockState = {
  type: 'wifi',
  isConnected: true,
  isInternetReachable: true,
  details: { isConnectionExpensive: false },
};

export const NetInfo = {
  fetch: async () => mockState,
  addEventListener: (_listener: (state: any) => void) => () => {},
  useNetInfo: () => mockState,
};

export default NetInfo;

