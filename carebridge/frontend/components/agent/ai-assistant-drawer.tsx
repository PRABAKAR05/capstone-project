"use client";

import * as React from "react";
import { X, Send, Bot, AlertTriangle, ShieldCheck, PhoneCall, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiFetch, ProblemDetailsError } from "@/lib/api";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  is_emergency?: boolean;
  tool_calls?: Array<{ tool: string; result_summary: string }>;
  timestamp: string;
}

export function AiAssistantDrawer() {
  const [isOpen, setIsOpen] = React.useState(false);
  const msgCountRef = React.useRef(0);
  const [messages, setMessages] = React.useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hello! I am **CareBridge AI**, your hospital operations and clinical triage coordinator.\n\nI can help you check doctor availability, review clinic schedules, and coordinate appointments.\n\n*CareBridge AI provides operational assistance and clinical triage navigation. For medical emergencies, contact emergency services immediately.*",
      timestamp: "Just now",
    },
  ]);
  const [inputValue, setInputValue] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const messagesEndRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isOpen]);

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend || inputValue).trim();
    if (!text || loading) return;

    msgCountRef.current += 1;
    const userMsg: ChatMessage = {
      id: `user-${msgCountRef.current}`,
      role: "user",
      content: text,
      timestamp: "Just now",
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setInputValue("");
    setLoading(true);

    try {
      // Build conversation history for API
      const historyPayload = messages
        .filter((m) => m.id !== "welcome")
        .slice(-6)
        .map((m) => ({ role: m.role, content: m.content }));

      const res = await apiFetch<{
        role: string;
        content: string;
        is_emergency: boolean;
        tool_calls_executed: Array<{ tool: string; result_summary: string }>;
        model_used: string;
      }>("/agent/chat", {
        method: "POST",
        body: JSON.stringify({
          message: text,
          history: historyPayload,
        }),
      });

      msgCountRef.current += 1;
      const assistantMsg: ChatMessage = {
        id: `ai-${msgCountRef.current}`,
        role: "assistant",
        content: res.content,
        is_emergency: res.is_emergency,
        tool_calls: res.tool_calls_executed,
        timestamp: "Just now",
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      let errText = "Failed to communicate with AI coordinator. Please check backend connection.";
      if (err instanceof ProblemDetailsError) {
        errText = err.detail;
      }
      msgCountRef.current += 1;
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${msgCountRef.current}`,
          role: "assistant",
          content: `⚠️ ${errText}`,
          timestamp: "Just now",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const quickPrompts = [
    "Find Cardiology doctors",
    "What slots are available for Dr. Chen tomorrow?",
    "Show my upcoming appointments",
    "I have severe chest pain and cannot breathe",
  ];

  return (
    <>
      {/* Floating Action Button */}
      <div className="fixed bottom-6 right-6 z-50">
        {!isOpen && (
          <Button
            onClick={() => setIsOpen(true)}
            size="lg"
            className="rounded-full shadow-xl bg-teal-600 hover:bg-teal-700 text-white flex items-center gap-2 px-5 py-3 h-auto border-2 border-white/20"
          >
            <Bot className="h-5 w-5 animate-pulse text-teal-200" />
            <span className="font-semibold text-sm">CareBridge AI</span>
            <Badge variant="warning" className="text-[10px] py-0 px-1.5 uppercase font-bold bg-amber-400 text-amber-950">
              Free Tier
            </Badge>
          </Button>
        )}
      </div>

      {/* Slide-over Drawer */}
      {isOpen && (
        <div className="fixed bottom-6 right-6 z-50 w-full max-w-md h-[640px] max-h-[85vh] bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col overflow-hidden animate-in fade-in slide-in-from-bottom-6 duration-200">
          {/* Header */}
          <div className="bg-slate-900 text-white p-4 flex items-center justify-between border-b border-slate-800">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-xl bg-teal-500/20 text-teal-300 border border-teal-500/30">
                <Bot className="h-5 w-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-bold text-sm text-slate-100">CareBridge Clinical Agent</h3>
                  <Badge variant="teal" className="text-[9px] py-0 px-1 bg-teal-500/20 text-teal-300 border-teal-500/30">
                    Groq LLM
                  </Badge>
                </div>
                <p className="text-[11px] text-slate-400 flex items-center gap-1">
                  <ShieldCheck className="h-3 w-3 text-emerald-400" /> ₹0 Budget Autonomous Coordinator
                </p>
              </div>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
              aria-label="Close Assistant"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Quick Action Chips */}
          <div className="bg-slate-50 border-b border-slate-200 px-3 py-2 flex items-center gap-1.5 overflow-x-auto text-xs no-scrollbar">
            <Sparkles className="h-3.5 w-3.5 text-teal-600 shrink-0" />
            {quickPrompts.map((q, idx) => (
              <button
                key={idx}
                onClick={() => handleSend(q)}
                disabled={loading}
                className={`whitespace-nowrap px-2.5 py-1 rounded-full border text-[11px] font-medium transition ${
                  q.includes("chest pain")
                    ? "bg-rose-50 text-rose-700 border-rose-200 hover:bg-rose-100"
                    : "bg-white text-slate-700 border-slate-200 hover:border-teal-500 hover:text-teal-700 shadow-xs"
                }`}
              >
                {q}
              </button>
            ))}
          </div>

          {/* Chat Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs bg-slate-50/50">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}
              >
                <div
                  className={`max-w-[88%] rounded-2xl p-3.5 leading-relaxed shadow-xs ${
                    m.role === "user"
                      ? "bg-teal-600 text-white rounded-br-xs"
                      : m.is_emergency
                      ? "bg-rose-50 border-2 border-rose-500 text-rose-950 rounded-bl-xs"
                      : "bg-white border border-slate-200 text-slate-800 rounded-bl-xs"
                  }`}
                >
                  {m.is_emergency && (
                    <div className="flex items-center gap-1.5 font-bold text-rose-700 mb-2 pb-1.5 border-b border-rose-200">
                      <AlertTriangle className="h-4 w-4 animate-bounce text-rose-600" />
                      <span>EMERGENCY DISPATCH TRIGGERED</span>
                    </div>
                  )}

                  {/* Message body */}
                  <div className="whitespace-pre-wrap">{m.content}</div>

                  {/* Emergency Quick Dials */}
                  {m.is_emergency && (
                    <div className="mt-3 pt-2 border-t border-rose-200 flex items-center gap-2">
                      <a
                        href="tel:108"
                        className="flex items-center gap-1.5 bg-rose-600 text-white font-bold px-3 py-1.5 rounded-lg hover:bg-rose-700 transition"
                      >
                        <PhoneCall className="h-3.5 w-3.5" /> Call 108
                      </a>
                      <a
                        href="tel:112"
                        className="flex items-center gap-1.5 bg-slate-800 text-white font-bold px-3 py-1.5 rounded-lg hover:bg-slate-900 transition"
                      >
                        <PhoneCall className="h-3.5 w-3.5" /> Call 112
                      </a>
                    </div>
                  )}

                  {/* Tool execution badges */}
                  {m.tool_calls && m.tool_calls.length > 0 && (
                    <div className="mt-2.5 pt-2 border-t border-slate-100 flex flex-wrap gap-1">
                      {m.tool_calls.map((t, tidx) => (
                        <span
                          key={tidx}
                          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-100 text-[10px] font-mono text-slate-600 border border-slate-200"
                        >
                          ⚡ tool: {t.tool} ({t.result_summary})
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <span className="text-[10px] text-slate-400 mt-1 px-1">{m.timestamp}</span>
              </div>
            ))}

            {loading && (
              <div className="flex items-center gap-2 text-slate-500 bg-white border border-slate-200 rounded-2xl p-3 max-w-[70%]">
                <Bot className="h-4 w-4 animate-spin text-teal-600" />
                <span className="text-xs font-medium">CareBridge agent thinking & checking slots...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Footer */}
          <div className="p-3 bg-white border-t border-slate-200 flex items-center gap-2">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Ask appointment questions, check doctors..."
              disabled={loading}
              className="flex-1 text-xs border border-slate-200 rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent placeholder:text-slate-400"
            />
            <Button
              onClick={() => handleSend()}
              disabled={loading || !inputValue.trim()}
              size="sm"
              className="bg-teal-600 hover:bg-teal-700 text-white rounded-xl px-3 py-2.5 h-auto shrink-0"
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </>
  );
}
