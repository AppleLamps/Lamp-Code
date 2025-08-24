/**
 * Pinned Messages Hook
 * Manages pinned messages state and persistence
 */
import { useState, useCallback, useEffect } from 'react';
import { Message } from '@/types/chat';

interface UsePinnedMessagesOptions {
  projectId: string;
}

export function usePinnedMessages({ projectId }: UsePinnedMessagesOptions) {
  const [pinnedMessageIds, setPinnedMessageIds] = useState<Set<string>>(new Set());

  // Load pinned messages from localStorage on mount
  useEffect(() => {
    const storageKey = `pinned-messages-${projectId}`;
    const stored = localStorage.getItem(storageKey);
    if (stored) {
      try {
        const pinnedIds = JSON.parse(stored);
        setPinnedMessageIds(new Set(pinnedIds));
      } catch (error) {
        console.error('Failed to load pinned messages:', error);
      }
    }
  }, [projectId]);

  // Save pinned messages to localStorage
  const savePinnedMessages = useCallback((pinnedIds: Set<string>) => {
    const storageKey = `pinned-messages-${projectId}`;
    localStorage.setItem(storageKey, JSON.stringify(Array.from(pinnedIds)));
  }, [projectId]);

  // Pin a message
  const pinMessage = useCallback((messageId: string) => {
    setPinnedMessageIds(prev => {
      const newSet = new Set(prev);
      newSet.add(messageId);
      savePinnedMessages(newSet);
      return newSet;
    });
  }, [savePinnedMessages]);

  // Unpin a message
  const unpinMessage = useCallback((messageId: string) => {
    setPinnedMessageIds(prev => {
      const newSet = new Set(prev);
      newSet.delete(messageId);
      savePinnedMessages(newSet);
      return newSet;
    });
  }, [savePinnedMessages]);

  // Check if a message is pinned
  const isMessagePinned = useCallback((messageId: string) => {
    return pinnedMessageIds.has(messageId);
  }, [pinnedMessageIds]);

  // Get pinned messages from a list of messages
  const getPinnedMessages = useCallback((messages: Message[]) => {
    return messages.filter(message => pinnedMessageIds.has(message.id));
  }, [pinnedMessageIds]);

  // Clear all pinned messages
  const clearPinnedMessages = useCallback(() => {
    setPinnedMessageIds(new Set());
    savePinnedMessages(new Set());
  }, [savePinnedMessages]);

  return {
    pinnedMessageIds,
    pinMessage,
    unpinMessage,
    isMessagePinned,
    getPinnedMessages,
    clearPinnedMessages,
    pinnedCount: pinnedMessageIds.size
  };
}
