import { useState, useEffect, useCallback, useRef } from 'react';

const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws';

interface WebSocketMessage {
  type: string;
  data: any;
}

export const useWebSocket = (userId: string) => {
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return;

    try {
      ws.current = new WebSocket(`${WS_URL}/${userId}`);

      ws.current.onopen = () => {
        console.log('WebSocket connected');
        setConnected(true);
        
        // Clear reconnect timer
        if (reconnectTimer.current) {
          clearTimeout(reconnectTimer.current);
          reconnectTimer.current = null;
        }
      };

      ws.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          setLastMessage(message);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      ws.current.onclose = () => {
        console.log('WebSocket disconnected');
        setConnected(false);
        ws.current = null;

        // Attempt to reconnect after 3 seconds
        reconnectTimer.current = setTimeout(() => {
          connect();
        }, 3000);
      };
    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
      
      // Retry connection after 3 seconds
      reconnectTimer.current = setTimeout(() => {
        connect();
      }, 3000);
    }
  }, [userId]);

  const disconnect = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }

    if (ws.current) {
      ws.current.close();
      ws.current = null;
    }
  }, []);

  const sendMessage = useCallback((type: string, data: any) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type, data }));
    } else {
      console.error('WebSocket is not connected');
    }
  }, []);

  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    connected,
    lastMessage,
    sendMessage
  };
};

// Singleton WebSocket manager for global use
class WebSocketManager {
  private static instance: WebSocketManager;
  private ws: WebSocket | null = null;
  private listeners: Map<string, Set<Function>> = new Map();
  private userId: string | null = null;

  static getInstance(): WebSocketManager {
    if (!WebSocketManager.instance) {
      WebSocketManager.instance = new WebSocketManager();
    }
    return WebSocketManager.instance;
  }

  connect(userId: string) {
    if (this.ws?.readyState === WebSocket.OPEN && this.userId === userId) {
      return;
    }

    this.disconnect();
    this.userId = userId;

    this.ws = new WebSocket(`${WS_URL}/${userId}`);

    this.ws.onopen = () => {
      this.emit('connected', true);
    };

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        this.emit('message', message);
        
        // Emit specific event based on message type
        if (message.type) {
          this.emit(message.type, message.data);
        }
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    this.ws.onerror = (error) => {
      this.emit('error', error);
    };

    this.ws.onclose = () => {
      this.emit('connected', false);
      this.ws = null;
      
      // Auto-reconnect
      setTimeout(() => {
        if (this.userId) {
          this.connect(this.userId);
        }
      }, 3000);
    };
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.userId = null;
  }

  send(type: string, data: any) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, data }));
    }
  }

  on(event: string, callback: Function) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);
  }

  off(event: string, callback: Function) {
    this.listeners.get(event)?.delete(callback);
  }

  private emit(event: string, data: any) {
    this.listeners.get(event)?.forEach(callback => {
      try {
        callback(data);
      } catch (error) {
        console.error(`Error in WebSocket listener for event ${event}:`, error);
      }
    });
  }
}

export const wsManager = WebSocketManager.getInstance();