export class EventSource {
  public url: string;
  public options: any;
  public listeners: Record<string, Function[]> = {};

  constructor(url: string, options?: any) {
    this.url = url;
    this.options = options;
  }

  addEventListener(type: string, listener: Function) {
    if (!this.listeners[type]) this.listeners[type] = [];
    this.listeners[type].push(listener);
  }

  removeEventListener(type: string, listener: Function) {
    if (!this.listeners[type]) return;
    this.listeners[type] = this.listeners[type].filter((l) => l !== listener);
  }

  close() {}
}

export default EventSource;

