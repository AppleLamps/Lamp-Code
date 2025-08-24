/**
 * Pinned Messages Panel Component
 * Shows pinned messages in a collapsible panel
 */
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Pin, ChevronDown, ChevronUp, X } from 'lucide-react';
import { Message } from '@/types/chat';
import ReactMarkdown from 'react-markdown';

interface PinnedMessagesPanelProps {
  pinnedMessages: Message[];
  onUnpin: (messageId: string) => void;
  className?: string;
}

export function PinnedMessagesPanel({ 
  pinnedMessages, 
  onUnpin, 
  className = '' 
}: PinnedMessagesPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (pinnedMessages.length === 0) {
    return null;
  }

  return (
    <div className={`border-b border-gray-200 dark:border-gray-700 ${className}`}>
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-3 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Pin size={16} className="text-blue-500 dark:text-blue-400" />
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Pinned Messages ({pinnedMessages.length})
          </span>
        </div>
        {isExpanded ? (
          <ChevronUp size={16} className="text-gray-500" />
        ) : (
          <ChevronDown size={16} className="text-gray-500" />
        )}
      </button>

      {/* Pinned Messages */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="p-3 space-y-3 bg-blue-50/50 dark:bg-blue-900/10">
              {pinnedMessages.map((message) => (
                <div
                  key={message.id}
                  className="group relative bg-white dark:bg-gray-800 rounded-lg p-3 border border-blue-200 dark:border-blue-800"
                >
                  {/* Unpin Button */}
                  <button
                    onClick={() => onUnpin(message.id)}
                    className="absolute top-2 right-2 p-1 opacity-0 group-hover:opacity-100 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-all"
                    title="Unpin message"
                  >
                    <X size={14} className="text-gray-500" />
                  </button>

                  {/* Message Content */}
                  <div className="pr-8">
                    <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">
                      {message.role === 'user' ? 'You' : 'Assistant'} • {new Date(message.created_at).toLocaleTimeString()}
                    </div>
                    <div className="text-sm text-gray-800 dark:text-gray-200">
                      <ReactMarkdown
                        components={{
                          p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
                          code: ({ children }) => (
                            <code className="bg-gray-100 dark:bg-gray-700 px-1 py-0.5 rounded text-xs font-mono">
                              {children}
                            </code>
                          ),
                          pre: ({ children }) => (
                            <pre className="bg-gray-100 dark:bg-gray-700 p-2 rounded text-xs overflow-x-auto">
                              {children}
                            </pre>
                          )
                        }}
                      >
                        {message.content.length > 200 
                          ? `${message.content.substring(0, 200)}...` 
                          : message.content
                        }
                      </ReactMarkdown>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
