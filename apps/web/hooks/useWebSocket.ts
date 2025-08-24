/**
 * WebSocket Hook
 * Manages WebSocket connection for real-time updates
 */
import { useEffect, useRef, useCallback, useState } from 'react';
import { Message } from '@/types/chat';

interface WebSocketOptions {
  projectId: string;
  onMessage?: (message: Message) => void;
  onStatus?: (status: string, data?: any, requestId?: string) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Error) => void;
}

export function useWebSocket({
  projectId,
  onMessage,
  onStatus,
  onConnect,
  onDisconnect,
  onError
}: WebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const connectionAttemptsRef = useRef(0);
  const shouldReconnectRef = useRef(true);
  const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const lastPongRef = useRef<number>(Date.now());
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'reconnecting'>('disconnected');

  const maxReconnectAttempts = 5; // Reduced from 10
  const baseReconnectDelay = 2000; // Increased from 1000
  const heartbeatInterval = 60000; // Increased to 60 seconds
  const pongTimeout = 15000; // Increased to 15 seconds

  // Start heartbeat mechanism
  const startHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
    }

    heartbeatIntervalRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        // Check if we received a pong recently (before sending new ping)
        const timeSinceLastPong = Date.now() - lastPongRef.current;
        if (timeSinceLastPong > heartbeatInterval + pongTimeout) {
          console.warn('WebSocket heartbeat timeout, reconnecting...');
          wsRef.current.close();
          return;
        }

        // Send ping
        wsRef.current.send('ping');
      }
    }, heartbeatInterval);
  }, [heartbeatInterval, pongTimeout]);

  // Stop heartbeat mechanism
  const stopHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    // Don't reconnect if we're intentionally disconnecting
    if (!shouldReconnectRef.current) {
      return;
    }

    setConnectionStatus(connectionAttemptsRef.current === 0 ? 'connecting' : 'reconnecting');

    try {
      const wsUrl = process.env.NEXT_PUBLIC_WS_BASE || 'ws://localhost:8080';
      const fullUrl = `${wsUrl}/api/chat/${projectId}`;
      const ws = new WebSocket(fullUrl);

      ws.onopen = () => {
        setIsConnected(true);
        setConnectionStatus('connected');
        connectionAttemptsRef.current = 0;
        lastPongRef.current = Date.now();
        startHeartbeat();
        onConnect?.();
      };

      ws.onmessage = (event) => {
        try {
          if (event.data === 'pong') {
            lastPongRef.current = Date.now();
            return;
          }

          const data = JSON.parse(event.data);
          
          if (data.type === 'message' && onMessage && data.data) {
            onMessage(data.data);
          } else if (data.type === 'preview_error' && onMessage) {
            onMessage(data);
          } else if (data.type === 'preview_success' && onMessage) {
            onMessage(data);
          } else if ((data.type === 'project_status' || data.type === 'status') && onStatus) {
            onStatus('project_status', data.data || { status: data.status, message: data.message });
          } else if (data.type === 'act_start' && onStatus) {
            onStatus('act_start', data.data, data.data?.request_id);
          } else if (data.type === 'chat_start' && onStatus) {
            onStatus('chat_start', data.data, data.data?.request_id);
          } else if (data.type === 'act_complete' && onStatus) {
            onStatus('act_complete', data.data, data.data?.request_id);
          } else if (data.type === 'chat_complete' && onStatus) {
            onStatus('chat_complete', data.data, data.data?.request_id);
          } else {
          }
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
        console.error('❌ WebSocket readyState:', ws.readyState);
        console.error('❌ WebSocket URL:', ws.url);
        setConnectionStatus('disconnected');
        onError?.(new Error(`WebSocket connection error to ${ws.url}`));
      };

      ws.onclose = (event) => {
        setIsConnected(false);
        setConnectionStatus('disconnected');
        stopHeartbeat();
        onDisconnect?.();

        // Only reconnect if we should and haven't exceeded attempts
        if (shouldReconnectRef.current && event.code !== 1000) {
          const attempts = connectionAttemptsRef.current + 1;
          connectionAttemptsRef.current = attempts;

          if (attempts < maxReconnectAttempts) {
            const delay = Math.min(baseReconnectDelay * Math.pow(2, attempts), 30000);
            setConnectionStatus('reconnecting');
            reconnectTimeoutRef.current = setTimeout(() => {
              connect();
            }, delay);
          } else {
            console.error('Max reconnection attempts reached');
            setConnectionStatus('disconnected');
          }
        }
      };

      wsRef.current = ws;
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      onError?.(error as Error);
    }
  }, [projectId, onMessage, onStatus, onConnect, onDisconnect, onError]);

  const disconnect = useCallback(() => {
    shouldReconnectRef.current = false;

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    stopHeartbeat();

    if (wsRef.current) {
      wsRef.current.close(1000, 'Intentional disconnect');
      wsRef.current = null;
    }

    setIsConnected(false);
    setConnectionStatus('disconnected');
  }, [stopHeartbeat]);

  const sendMessage = useCallback((data: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    } else {
      console.warn('WebSocket is not connected');
    }
  }, []);

  useEffect(() => {
    shouldReconnectRef.current = true;
    connectionAttemptsRef.current = 0;
    connect();
    
    return () => {
      disconnect();
    };
  }, [projectId]);

  return {
    isConnected,
    connectionStatus,
    connect,
    disconnect,
    sendMessage
  };
}