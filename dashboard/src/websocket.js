// websocket.js — WebSocket connection manager

const WS_URL = 'ws://localhost:8080/ws';

class WSManager {
  constructor() {
    this.ws = null;
    this.handlers = {};
    this.reconnectDelay = 2000;
    this.connected = false;
  }

  connect(onStatusChange) {
    this.onStatusChange = onStatusChange;
    this._connect();
  }

  _connect() {
    try {
      this.ws = new WebSocket(WS_URL);

      this.ws.onopen = () => {
        this.connected = true;
        this.reconnectDelay = 2000;
        console.log('[WS] Connected to Intelligence Proxy');
        this.onStatusChange && this.onStatusChange(true);
      };

      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          const handlers = this.handlers[msg.type] || [];
          handlers.forEach(h => h(msg.data, msg.timestamp));
        } catch (e) {
          console.error('[WS] Parse error:', e);
        }
      };

      this.ws.onclose = () => {
        this.connected = false;
        this.onStatusChange && this.onStatusChange(false);
        console.log(`[WS] Disconnected. Reconnecting in ${this.reconnectDelay}ms...`);
        setTimeout(() => this._connect(), this.reconnectDelay);
        this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, 10000);
      };

      this.ws.onerror = () => {
        this.ws.close();
      };

    } catch (e) {
      console.error('[WS] Connection failed:', e);
      setTimeout(() => this._connect(), this.reconnectDelay);
    }
  }

  on(type, handler) {
    if (!this.handlers[type]) this.handlers[type] = [];
    this.handlers[type].push(handler);
    return () => {
      this.handlers[type] = this.handlers[type].filter(h => h !== handler);
    };
  }

  off(type, handler) {
    if (this.handlers[type]) {
      this.handlers[type] = this.handlers[type].filter(h => h !== handler);
    }
  }
}

export const wsManager = new WSManager();
