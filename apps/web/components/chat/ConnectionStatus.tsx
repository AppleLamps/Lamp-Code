/**
 * Connection Status Component
 * Shows WebSocket connection status with visual indicators
 */
import React from 'react';
import { Wifi, WifiOff, RotateCcw } from 'lucide-react';

interface ConnectionStatusProps {
  isConnected: boolean;
  connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'reconnecting';
  className?: string;
}

export function ConnectionStatus({ 
  isConnected, 
  connectionStatus, 
  className = '' 
}: ConnectionStatusProps) {
  const getStatusConfig = () => {
    switch (connectionStatus) {
      case 'connected':
        return {
          icon: <Wifi size={16} />,
          text: 'Connected',
          color: 'text-green-500 dark:text-green-400',
          bgColor: 'bg-green-50 dark:bg-green-900/20',
          borderColor: 'border-green-200 dark:border-green-800'
        };
      case 'connecting':
        return {
          icon: <RotateCcw size={16} className="animate-spin" />,
          text: 'Connecting...',
          color: 'text-yellow-500 dark:text-yellow-400',
          bgColor: 'bg-yellow-50 dark:bg-yellow-900/20',
          borderColor: 'border-yellow-200 dark:border-yellow-800'
        };
      case 'reconnecting':
        return {
          icon: <RotateCcw size={16} className="animate-spin" />,
          text: 'Reconnecting...',
          color: 'text-orange-500 dark:text-orange-400',
          bgColor: 'bg-orange-50 dark:bg-orange-900/20',
          borderColor: 'border-orange-200 dark:border-orange-800'
        };
      case 'disconnected':
      default:
        return {
          icon: <WifiOff size={16} />,
          text: 'Disconnected',
          color: 'text-red-500 dark:text-red-400',
          bgColor: 'bg-red-50 dark:bg-red-900/20',
          borderColor: 'border-red-200 dark:border-red-800'
        };
    }
  };

  const config = getStatusConfig();

  return (
    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border ${config.bgColor} ${config.borderColor} ${className}`}>
      <div className={config.color}>
        {config.icon}
      </div>
      <span className={`text-sm font-medium ${config.color}`}>
        {config.text}
      </span>
    </div>
  );
}
