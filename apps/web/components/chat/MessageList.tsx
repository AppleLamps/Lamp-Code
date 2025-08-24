/**
 * Message List Component
 * Displays chat messages
 */
import React, { useState } from 'react';
import { Message } from '@/types/chat';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import { CodeBlock, InlineCode } from './CodeBlock';
import { MessageActions } from './MessageActions';
import { usePinnedMessages } from '@/hooks/usePinnedMessages';
import { useToast } from '@/hooks/useToast';
import { ToastContainer } from '@/components/ui/ToastContainer';

interface MessageListProps {
  messages: Message[];
  isLoading?: boolean;
  projectId: string;
}

// Group consecutive messages from the same role
function groupMessages(messages: Message[]): Message[][] {
  if (messages.length === 0) return [];
  
  const groups: Message[][] = [];
  let currentGroup: Message[] = [messages[0]];
  
  for (let i = 1; i < messages.length; i++) {
    const current = messages[i];
    const previous = messages[i - 1];
    
    // Group if same role, same conversation, and within reasonable time
    const timeDiff = new Date(current.created_at).getTime() - new Date(previous.created_at).getTime();
    const shouldGroup = (
      current.role === previous.role && 
      current.conversation_id === previous.conversation_id &&
      timeDiff < 120000 // 2 minutes
    );
    
    if (shouldGroup) {
      currentGroup.push(current);
    } else {
      groups.push(currentGroup);
      currentGroup = [current];
    }
  }
  
  groups.push(currentGroup);
  return groups;
}

export function MessageList({ messages, isLoading, projectId }: MessageListProps) {
  const messageGroups = groupMessages(messages);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);

  // Toast notifications
  const { toasts, success, error, removeToast } = useToast();

  // Pinned messages functionality
  const {
    pinMessage,
    unpinMessage,
    isMessagePinned,
    getPinnedMessages
  } = usePinnedMessages({ projectId });

  // Copy message content to clipboard
  const handleCopyMessage = async (content: string, messageId: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedMessageId(messageId);
      success('Message copied to clipboard');
      setTimeout(() => setCopiedMessageId(null), 2000);
    } catch (err) {
      console.error('Failed to copy message:', err);
      error('Failed to copy message');
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      <AnimatePresence initial={false}>
        {messageGroups.map((group, groupIndex) => {
          const firstMessage = group[0];
          const isUser = firstMessage.role === 'user';
          
          return (
            <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`} key={`group-${groupIndex}-${firstMessage.id}`}>
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.3 }}
                className="group relative"
              >
              <div
                className={`max-w-[70%] rounded-lg px-4 py-2 space-y-2 ${
                  isUser
                    ? 'bg-blue-500 text-white'
                    : firstMessage.message_type === 'error'
                    ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                    : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
                } ${isMessagePinned(firstMessage.id) ? 'ring-2 ring-blue-400 dark:ring-blue-500' : ''}`}
              >
                {/* Message Actions */}
                {!isUser && (
                  <div className="absolute -top-2 -right-2">
                    <MessageActions
                      message={{ ...firstMessage, pinned: isMessagePinned(firstMessage.id) }}
                      onPin={pinMessage}
                      onUnpin={unpinMessage}
                      onCopy={(content) => handleCopyMessage(content, firstMessage.id)}
                    />
                  </div>
                )}

                {group.map((message, messageIndex) => (
                  <div key={message.id || messageIndex}>
                    {message.message_type === 'error' && messageIndex === 0 && (
                      <div className="flex items-center gap-2 mb-1">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <span className="font-semibold text-sm">Error</span>
                      </div>
                    )}
                    
                    {message.message_type === 'tool_use' ? (
                      <div className="text-sm opacity-75 italic mb-1">
                        {message.content}
                      </div>
                    ) : (
                      <div className="whitespace-pre-wrap break-words">
                        <ReactMarkdown
                          components={{
                            p: ({ children }) => <p className="mb-2 last:mb-0 break-words">{children}</p>,
                            strong: ({ children }) => <strong className="font-medium">{children}</strong>,
                            em: ({ children }) => <em className="italic">{children}</em>,
                            code: ({ children, className, ...props }) => {
                              const isInline = !className;
                              if (isInline) {
                                return <InlineCode>{children}</InlineCode>;
                              }
                              return <CodeBlock className={className} {...props}>{children}</CodeBlock>;
                            },
                            pre: ({ children }) => <>{children}</>, // Let CodeBlock handle the pre wrapper
                            ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
                            ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
                            li: ({ children }) => <li className="mb-1 break-words">{children}</li>
                          }}
                        >
                          {message.content}
                        </ReactMarkdown>
                      </div>
                    )}
                  </div>
                ))}
                
                {firstMessage.cli_source && (
                  <div className="mt-2 text-xs opacity-70">
                    via {firstMessage.cli_source}
                  </div>
                )}
                
                <div className="mt-1 text-xs opacity-50">
                  {new Date(group[group.length - 1].created_at).toLocaleTimeString()}
                </div>
              </div>
              </motion.div>
            </div>
          );
        })}
      </AnimatePresence>
      
      {isLoading && (
        <div className="flex justify-start">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <div className="bg-gray-100 dark:bg-gray-700 rounded-lg px-4 py-2">
              <div className="flex space-x-2">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:0ms]" />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]" />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          </motion.div>
        </div>
      )}

      {/* Toast Notifications */}
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </div>
  );
}