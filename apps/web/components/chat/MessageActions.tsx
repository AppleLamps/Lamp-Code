/**
 * Message Actions Component
 * Provides actions like pin/unpin for chat messages
 */
import React from 'react';
import { Pin, PinOff, Copy } from 'lucide-react';
import { Message } from '@/types/chat';

interface MessageActionsProps {
  message: Message;
  onPin: (messageId: string) => void;
  onUnpin: (messageId: string) => void;
  onCopy?: (content: string) => void;
  className?: string;
}

export function MessageActions({ 
  message, 
  onPin, 
  onUnpin, 
  onCopy,
  className = '' 
}: MessageActionsProps) {
  const handlePin = () => {
    if (message.pinned) {
      onUnpin(message.id);
    } else {
      onPin(message.id);
    }
  };

  const handleCopy = () => {
    if (onCopy) {
      onCopy(message.content);
    }
  };

  return (
    <div className={`flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity ${className}`}>
      {/* Pin/Unpin Button */}
      <button
        onClick={handlePin}
        className={`p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors ${
          message.pinned 
            ? 'text-blue-500 dark:text-blue-400' 
            : 'text-gray-500 dark:text-gray-400'
        }`}
        title={message.pinned ? 'Unpin message' : 'Pin message'}
      >
        {message.pinned ? <PinOff size={14} /> : <Pin size={14} />}
      </button>

      {/* Copy Button */}
      {onCopy && (
        <button
          onClick={handleCopy}
          className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors text-gray-500 dark:text-gray-400"
          title="Copy message"
        >
          <Copy size={14} />
        </button>
      )}
    </div>
  );
}
