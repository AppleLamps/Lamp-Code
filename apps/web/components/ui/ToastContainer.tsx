/**
 * Toast Container Component
 * Displays toast notifications
 */
import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react';
import { Toast } from '@/hooks/useToast';

interface ToastContainerProps {
  toasts: Toast[];
  onRemove: (id: string) => void;
}

export function ToastContainer({ toasts, onRemove }: ToastContainerProps) {
  const getToastConfig = (type: Toast['type']) => {
    switch (type) {
      case 'success':
        return {
          icon: <CheckCircle size={20} />,
          bgColor: 'bg-green-500/90',
          textColor: 'text-white'
        };
      case 'error':
        return {
          icon: <AlertCircle size={20} />,
          bgColor: 'bg-red-500/90',
          textColor: 'text-white'
        };
      case 'warning':
        return {
          icon: <AlertTriangle size={20} />,
          bgColor: 'bg-yellow-500/90',
          textColor: 'text-white'
        };
      case 'info':
      default:
        return {
          icon: <Info size={20} />,
          bgColor: 'bg-blue-500/90',
          textColor: 'text-white'
        };
    }
  };

  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2">
      <AnimatePresence>
        {toasts.map((toast) => {
          const config = getToastConfig(toast.type);
          
          return (
            <motion.div
              key={toast.id}
              initial={{ opacity: 0, y: 50, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 50, scale: 0.9 }}
              transition={{ duration: 0.2 }}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg backdrop-blur-sm ${config.bgColor} ${config.textColor} max-w-sm`}
            >
              <div className="flex-shrink-0">
                {config.icon}
              </div>
              <p className="text-sm font-medium flex-1">
                {toast.message}
              </p>
              <button
                onClick={() => onRemove(toast.id)}
                className="flex-shrink-0 p-1 hover:bg-white/20 rounded transition-colors"
                aria-label="Close notification"
                title="Close notification"
              >
                <X size={16} />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
