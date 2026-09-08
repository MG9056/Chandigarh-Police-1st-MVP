import React, { useState, useRef, useEffect } from 'react';
import {
  Bot,
  Sparkles,
  X,
  Send,
  AlertCircle,
  ShieldCheck,
  ChevronDown,
  RefreshCw,
  HelpCircle,
  ArrowDown,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useAI } from '../../hooks/useAI';
import { Button } from '../ui/button';
import { useTranslation } from 'react-i18next';

/**
 * Simple Markdown-like text formatter for assistant responses.
 * Converts bold (**text**), inline code (`code`), lists (- item), and newlines.
 */
function FormatAIMessage({ content }) {
  if (!content) return null;

  // Split by code blocks if present
  const blocks = content.split(/(```[\s\S]*?```)/g);

  return (
    <div className="space-y-2 text-xs font-sans leading-relaxed">
      {blocks.map((block, idx) => {
        if (block.startsWith('```') && block.endsWith('```')) {
          const lines = block.slice(3, -3).trim().split('\n');
          const lang = lines[0].match(/^[a-zA-Z0-9_-]+$/) ? lines.shift() : '';
          const codeText = lines.join('\n');
          return (
            <pre
              key={idx}
              className="p-2.5 rounded bg-slate-950 border border-slate-800 font-mono text-[11px] text-emerald-400 overflow-x-auto my-1.5"
            >
              {codeText}
            </pre>
          );
        }

        // Process standard paragraph lines
        const lines = block.split('\n');
        return (
          <div key={idx} className="space-y-1">
            {lines.map((line, lineIdx) => {
              const trimmed = line.trim();

              // Bullet points
              if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
                const listContent = trimmed.slice(2);
                return (
                  <div key={lineIdx} className="flex items-start gap-1.5 ml-2">
                    <span className="text-primary mt-1">•</span>
                    <span>{renderInlineFormatting(listContent)}</span>
                  </div>
                );
              }

              // Numbered lists
              const numMatch = trimmed.match(/^(\d+)\.\s+(.*)/);
              if (numMatch) {
                return (
                  <div key={lineIdx} className="flex items-start gap-1.5 ml-2">
                    <span className="text-primary font-bold font-mono">{numMatch[1]}.</span>
                    <span>{renderInlineFormatting(numMatch[2])}</span>
                  </div>
                );
              }

              if (!trimmed) return <div key={lineIdx} className="h-1" />;

              return <p key={lineIdx}>{renderInlineFormatting(line)}</p>;
            })}
          </div>
        );
      })}
    </div>
  );
}

function renderInlineFormatting(text) {
  // Regex split for bold **text** and inline `code`
  const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-bold text-foreground">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code key={i} className="px-1 py-0.5 rounded bg-muted/80 text-primary font-mono text-[11px] border border-border/50">
          {part.slice(1, -1)}
        </code>
      );
    }
    return part;
  });
}

export default function AIAssistant({ activeView = 'dashboard', selectedInvestigationId = null }) {
  const { user, isAuthenticated } = useAuth();
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [inputText, setInputText] = useState('');
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const currentContext = {
    activeView,
    investigationId: selectedInvestigationId,
  };

  const {
    messages,
    status,
    errorMessage,
    quickPrompts,
    sendMessage,
    isStreaming,
  } = useAI(currentContext);

  // Auto-scroll message container to bottom
  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isStreaming, isOpen]);

  // Focus input when chat panel opens
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 150);
    }
  }, [isOpen]);

  // Render nothing if user is not authenticated
  if (!user || !isAuthenticated) {
    return null;
  }

  const handleSend = (e) => {
    e?.preventDefault();
    if (!inputText.trim() || isStreaming) return;
    sendMessage(inputText, currentContext);
    setInputText('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleQuickPromptClick = (promptText) => {
    sendMessage(promptText, currentContext);
  };

  return (
    <>
      {/* FLOATING TRIGGER BUTTON (Fixed Bottom-Right) */}
      <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 pointer-events-auto">
        {!isOpen && (
          <div className="hidden md:flex items-center gap-1.5 px-3 py-1 bg-background/90 border border-primary/50 rounded-full shadow-lg text-[11px] font-mono text-primary animate-pulse backdrop-blur-md">
            <Sparkles className="w-3 h-3 text-primary" />
            <span>{t('DarKnight AI')}</span>
          </div>
        )}

        <button
          onClick={() => setIsOpen(!isOpen)}
          aria-label={isOpen ? t('Close DarKnight AI Copilot') : t('Open DarKnight AI Copilot')}
          title={t('DarKnight AI — Your Investigative Copilot')}
          className={`relative group h-12 w-12 rounded-full border flex items-center justify-center shadow-2xl transition-all duration-300 backdrop-blur-md ${
            isOpen
              ? 'bg-primary text-primary-foreground border-primary shadow-[0_0_20px_hsl(var(--primary)/0.5)] scale-105'
              : 'bg-background/90 text-primary border-primary/60 hover:border-primary hover:bg-primary/10 shadow-[0_0_12px_hsl(var(--primary)/0.3)]'
          }`}
        >
          <div className="relative flex items-center justify-center">
            {isOpen ? (
              <X className="w-5 h-5 transition-transform duration-200" />
            ) : (
              <Bot className="w-6 h-6 text-primary group-hover:scale-110 transition-transform duration-200" />
            )}
          </div>
          {!isOpen && (
            <span className="absolute -top-1 -right-1 flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-primary"></span>
            </span>
          )}
        </button>
      </div>

      {/* FLOATING CHAT PANEL */}
      {isOpen && (
        <div
          className="fixed bottom-20 right-6 z-50 w-[420px] max-w-[calc(100vw-2rem)] h-[580px] max-h-[calc(100vh-6.5rem)] bg-background/95 border border-border/80 rounded-xl shadow-2xl flex flex-col font-mono text-foreground overflow-hidden backdrop-blur-xl animate-in fade-in slide-in-from-bottom-6 duration-300"
          style={{ boxShadow: '0 10px 40px -10px rgba(0, 0, 0, 0.5), 0 0 20px 0 hsl(var(--primary) / 0.15)' }}
        >
          {/* PANEL HEADER */}
          <div className="h-14 px-4 border-b border-border/60 bg-card/60 backdrop-blur-md flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-3">
              <div className="relative w-7 h-7 flex items-center justify-center bracket-border">
                <div className="w-2.5 h-2.5 bg-primary rotate-45 text-glow animate-pulse" />
              </div>
              <div className="flex flex-col">
                <div className="flex items-center gap-2">
                  <h3 className="text-xs font-bold tracking-[0.15em] text-primary uppercase font-mono text-glow">
                    DarKnight AI
                  </h3>
                </div>
                <span className="text-[10px] text-muted-foreground font-mono">{t('Your investigative copilot')}</span>
              </div>
            </div>

            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsOpen(false)}
                title={t('Close AI Panel')}
                className="h-7 w-7 text-muted-foreground hover:text-foreground"
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
          </div>

          {/* ACTIVE CONTEXT BADGE BAR */}
          <div className="px-4 py-1.5 bg-muted/40 border-b border-border/40 flex items-center justify-between text-[10px] text-muted-foreground flex-shrink-0">
            <div className="flex items-center gap-1.5 truncate">
              <ShieldCheck className="w-3 h-3 text-primary flex-shrink-0" />
              <span className="truncate">
                {t('Officer:')} <strong className="text-foreground">{user.full_name}</strong> ({user.role})
              </span>
            </div>
            <span className="px-1.5 py-0.5 rounded bg-background border border-border/50 text-primary text-[9px] uppercase font-bold flex-shrink-0">
              {t('View:')} {activeView}
            </span>
          </div>

          {/* MESSAGE AREA */}
          <div className="flex-1 p-4 overflow-y-auto space-y-3 font-mono text-xs custom-scrollbar">
            {/* GREETING & EMPTY STATE */}
            {messages.length === 0 && (
              <div className="space-y-4 my-2">
                <div className="p-3.5 bg-card/60 border border-primary/30 rounded-lg space-y-2">
                  <div className="flex items-center gap-2 text-primary font-bold text-xs uppercase">
                    <Sparkles className="w-4 h-4" />
                    <span>{t('Investigative Copilot Ready')}</span>
                  </div>
                  <p className="text-xs text-foreground font-sans leading-relaxed">
                    {t("Hi, I'm")} <strong>DarKnight AI</strong>, {t('your investigative copilot. What would you like to know about the platform, intelligence workflows, roles, or evidence requirements?')}
                  </p>
                </div>

                {/* QUICK PROMPTS */}
                {quickPrompts.length > 0 && (
                  <div className="space-y-2">
                    <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono block">
                      {t('Quick Prompts:')}
                    </span>
                    <div className="flex flex-col gap-1.5">
                      {quickPrompts.map((item) => (
                        <button
                          key={item.id}
                          onClick={() => handleQuickPromptClick(item.prompt)}
                          className="text-left p-2 rounded-lg bg-muted/30 hover:bg-primary/10 border border-border/50 hover:border-primary/40 text-xs text-muted-foreground hover:text-foreground transition-all flex items-center justify-between group font-sans"
                        >
                          <span>{item.label}</span>
                          <span className="text-primary opacity-0 group-hover:opacity-100 transition-opacity font-mono text-[10px]">
                            {t('Ask →')}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* CONVERSATION MESSAGES */}
            {messages.map((msg) => {
              const isUser = msg.role === 'user';
              return (
                <div
                  key={msg.id}
                  className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} space-y-1`}
                >
                  <div className="flex items-center gap-1.5 text-[9px] text-muted-foreground uppercase font-mono">
                    <span>{isUser ? user.full_name : 'DarKnight AI'}</span>
                    <span>•</span>
                    <span>
                      {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>

                  <div
                    className={`p-3 rounded-xl border text-xs max-w-[88%] ${
                      isUser
                        ? 'bg-primary/15 border-primary/40 text-foreground font-sans rounded-tr-none'
                        : msg.error
                        ? 'bg-destructive/10 border-destructive/40 text-destructive font-sans rounded-tl-none'
                        : 'bg-card/70 border-border/60 text-foreground rounded-tl-none shadow-sm'
                    }`}
                  >
                    {isUser ? (
                      <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                    ) : (
                      <FormatAIMessage content={msg.content} />
                    )}
                  </div>
                </div>
              );
            })}

            {/* THINKING / STREAMING INDICATOR */}
            {isStreaming && (
              <div className="flex items-center gap-2 p-2.5 rounded-lg bg-card/40 border border-border/40 text-xs text-primary font-mono animate-pulse w-max">
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-primary" />
                <span>{t('DarKnight AI is thinking...')}</span>
              </div>
            )}

            {/* ERROR BANNER */}
            {errorMessage && status === 'error' && (
              <div className="p-3 bg-destructive/10 border border-destructive/40 text-destructive text-xs rounded-lg flex items-center gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{errorMessage}</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* INPUT FORM AREA */}
          <form onSubmit={handleSend} className="p-3 border-t border-border/60 bg-card/40 flex flex-col gap-2 flex-shrink-0">
            <div className="relative flex items-center">
              <textarea
                ref={inputRef}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={t('Ask DarKnight AI a question...')}
                disabled={isStreaming}
                rows={1}
                className="w-full bg-background border border-border/60 rounded-lg px-3 py-2 pr-10 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/80 font-mono resize-none max-h-24 custom-scrollbar"
              />
              <Button
                type="submit"
                size="icon"
                disabled={!inputText.trim() || isStreaming}
                className="absolute right-1.5 h-7 w-7 rounded-md"
                title={t('Send Message (Enter)')}
              >
                <Send className="w-3.5 h-3.5" />
              </Button>
            </div>

            <div className="flex items-center justify-between text-[9px] text-muted-foreground font-mono">
              <span>{t('Press')} <kbd className="px-1 py-0.5 bg-muted rounded border border-border">Enter</kbd> {t('to send')}</span>
              <span className="text-primary/70">{t('RBAC & Session Enforced')}</span>
            </div>
          </form>
        </div>
      )}
    </>
  );
}

