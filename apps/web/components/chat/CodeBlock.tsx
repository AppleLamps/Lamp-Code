/**
 * CodeBlock Component with Copy Functionality
 * Enhanced code block rendering for chat messages
 */
import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';

interface CodeBlockProps {
  children: React.ReactNode;
  className?: string;
  inline?: boolean;
}

export function CodeBlock({ children, className, inline }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  
  // Extract language from className (format: language-javascript)
  const language = className?.replace('language-', '') || 'text';
  
  // Get the code content as string
  const codeContent = React.Children.toArray(children).join('');
  
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(codeContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy code:', err);
    }
  };

  // For inline code, render simple styled span
  if (inline) {
    return (
      <code className="bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded text-xs font-mono">
        {children}
      </code>
    );
  }

  // For code blocks, render with copy button
  return (
    <div className="relative group my-3">
      {/* Language label and copy button */}
      <div className="flex items-center justify-between bg-gray-50 dark:bg-gray-800 px-4 py-2 rounded-t-lg border-b border-gray-200 dark:border-gray-600">
        <span className="text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">
          {language}
        </span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 px-2 py-1 text-xs text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-colors"
          title="Copy code"
        >
          {copied ? (
            <>
              <Check size={12} />
              <span>Copied!</span>
            </>
          ) : (
            <>
              <Copy size={12} />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      
      {/* Code content */}
      <pre className="bg-gray-100 dark:bg-gray-700 p-4 rounded-b-lg overflow-x-auto text-sm">
        <code className={className}>
          {children}
        </code>
      </pre>
    </div>
  );
}

interface InlineCodeProps {
  children: React.ReactNode;
}

export function InlineCode({ children }: InlineCodeProps) {
  return (
    <code className="bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded text-xs font-mono">
      {children}
    </code>
  );
}
