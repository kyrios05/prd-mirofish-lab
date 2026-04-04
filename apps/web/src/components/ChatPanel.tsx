/**
 * ChatPanel.tsx — Left panel: conversation bubbles, input, phase badge,
 * action buttons, and next-question chips.
 *
 * T08: Core chat UI component.
 */

import { useEffect, useRef, useState } from 'react';
import type { UseChatReturn } from '../hooks/useChat';
import { PhaseBadge } from './PhaseBadge';
import styles from '../styles/chat.module.css';

// ---------------------------------------------------------------------------
// Action label mapping
// ---------------------------------------------------------------------------

const ACTION_LABELS: Record<string, string> = {
  continue: '▶ Continue',
  skip_section: '⏭ Skip section',
  save_checkpoint: '💾 Save checkpoint',
  confirm: '✓ Confirm',
  edit_section: '✎ Edit section',
  run_validation: '🚀 Run validation',
  go_back: '← Go back',
};

function actionLabel(action: string): string {
  return ACTION_LABELS[action] ?? action;
}

// ---------------------------------------------------------------------------
// Timestamp helper
// ---------------------------------------------------------------------------

function shortTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '';
  }
}

// ---------------------------------------------------------------------------
// ChatPanel
// ---------------------------------------------------------------------------

interface ChatPanelProps {
  chat: UseChatReturn;
  /** Triggered when user clicks the "run_validation" action */
  onRunValidation?: () => void;
  /** Triggered when user clicks "save_checkpoint" action */
  onSaveCheckpoint?: () => void;
}

export function ChatPanel({ chat, onRunValidation, onSaveCheckpoint }: ChatPanelProps) {
  const {
    messages,
    phase,
    availableActions,
    nextQuestions,
    isLoading,
    error,
    sendMessage,
    setPendingInput,
    pendingInput,
  } = chat;

  const [inputValue, setInputValue] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Sync pendingInput (from question chips) into local state
  useEffect(() => {
    if (pendingInput) {
      setInputValue(pendingInput);
      setPendingInput('');
      textareaRef.current?.focus();
    }
  }, [pendingInput, setPendingInput]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  function handleSend() {
    if (!inputValue.trim() || isLoading) return;
    void sendMessage(inputValue);
    setInputValue('');
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleAction(action: string) {
    if (action === 'run_validation') {
      onRunValidation?.();
      return;
    }
    if (action === 'save_checkpoint') {
      onSaveCheckpoint?.();
      return;
    }
    // For other actions, send the action text as a chat message
    void sendMessage(`/${action}`);
  }

  // Adjust textarea height automatically
  function handleInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInputValue(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
  }

  return (
    <div className={styles.panel}>
      {/* Panel header */}
      <div className={styles.panelHeader}>
        <span className={styles.panelTitle}>💬 Chat</span>
        <PhaseBadge phase={phase} />
      </div>

      {/* Message list */}
      <div className={styles.messageList} role="log" aria-live="polite">
        {messages.length === 0 ? (
          <div className={styles.emptyState}>
            <div className={styles.emptyIcon}>🤖</div>
            <div className={styles.emptyText}>
              세션을 초기화하는 중입니다…
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`${styles.messageRow} ${msg.role === 'user' ? styles.user : ''}`}
            >
              <div
                className={`${styles.avatar} ${msg.role === 'user' ? styles.avatarUser : ''}`}
                aria-hidden="true"
              >
                {msg.role === 'user' ? 'U' : 'AI'}
              </div>
              <div>
                <div
                  className={`${styles.bubble} ${
                    msg.role === 'user' ? styles.bubbleUser : styles.bubbleAssistant
                  }`}
                >
                  {msg.content}
                </div>
                <div className={styles.timestamp}>{shortTime(msg.timestamp)}</div>
              </div>
            </div>
          ))
        )}

        {/* Typing indicator */}
        {isLoading && (
          <div className={styles.typingIndicator}>
            <div className={`${styles.avatar}`} aria-hidden="true">
              AI
            </div>
            <div className={styles.typingDots}>
              <div className={styles.typingDot} />
              <div className={styles.typingDot} />
              <div className={styles.typingDot} />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Error banner */}
      {error && (
        <div
          style={{
            padding: '0.4rem 1rem',
            background: '#fef2f2',
            borderTop: '1px solid #fecaca',
            fontSize: '0.8rem',
            color: '#991b1b',
            flexShrink: 0,
          }}
        >
          ⚠ {error}
        </div>
      )}

      {/* Next questions */}
      {nextQuestions.length > 0 && (
        <div className={styles.nextQuestions}>
          <div className={styles.nextQuestionsLabel}>Suggested questions</div>
          {nextQuestions.map((q, i) => (
            <button
              key={i}
              className={styles.questionChip}
              onClick={() => setPendingInput(q)}
              title={q}
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Action buttons */}
      {availableActions.length > 0 && (
        <div className={styles.actionButtons}>
          {availableActions.map((action) => (
            <button
              key={action}
              className={styles.actionBtn}
              onClick={() => handleAction(action)}
              disabled={isLoading}
            >
              {actionLabel(action)}
            </button>
          ))}
        </div>
      )}

      {/* Input area */}
      <div className={styles.inputArea}>
        <div className={styles.inputRow}>
          <textarea
            ref={textareaRef}
            className={styles.textarea}
            value={inputValue}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder="메시지를 입력하세요… (Enter로 전송, Shift+Enter 줄바꿈)"
            rows={1}
            disabled={isLoading}
            aria-label="Chat input"
          />
          <button
            className={styles.sendBtn}
            onClick={handleSend}
            disabled={!inputValue.trim() || isLoading}
            aria-label="Send message"
          >
            ↑
          </button>
        </div>
      </div>
    </div>
  );
}
