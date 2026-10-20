"use client";

import * as React from "react";
import {
  X,
  Send,
  Bot,
  AlertTriangle,
  ShieldCheck,
  PhoneCall,
  Sparkles,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  FileText,
  Calendar,
  CheckCircle2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiFetch, ProblemDetailsError } from "@/lib/api";

interface ChatCitation {
  source_type: string;
  title: string;
  reference_id?: string;
  snippet?: string;
}

interface ActionConfirmation {
  action_type: string;
  parameters: Record<string, unknown>;
  description: string;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  is_emergency?: boolean;
  requires_confirmation?: boolean;
  pending_action?: ActionConfirmation | null;
  citations?: ChatCitation[];
  tool_calls?: Array<{ tool: string; status?: string }>;
  timestamp: string;
}

export function ConversationalDrawer() {
  const [isOpen, setIsOpen] = React.useState(false);
  const [conversationId, setConversationId] = React.useState<string | null>(null);
  const msgCountRef = React.useRef(0);
  const [messages, setMessages] = React.useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hello! I am **CareBridge AI**, your hospital navigation and clinical care assistant.\n\nI can help you:\n• Check specialist availability & book consultations\n• Review your active digital prescriptions & adherence\n• Track uploaded clinical document processing\n• Check your care coordination tasks\n\n*For acute medical emergencies, immediately dial 112 or 108.*",
      timestamp: "Just now",
    },
  ]);
  const [inputValue, setInputValue] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [isListening, setIsListening] = React.useState(false);
  const [selectedLocale, setSelectedLocale] = React.useState<string>("en-IN");
  const [speechSynthesisActive, setSpeechSynthesisActive] = React.useState(false);
  const recognitionRef = React.useRef<unknown>(null);
  const messagesEndRef = React.useRef<HTMLDivElement>(null);

  // Initialize Web Speech API detection without cascading render effect
  const speechSupported = React.useSyncExternalStore(
    () => () => {},
    () =>
      typeof window !== "undefined" &&
      !!(
        (window as unknown as { SpeechRecognition?: unknown; webkitSpeechRecognition?: unknown }).SpeechRecognition ||
        (window as unknown as { webkitSpeechRecognition?: unknown }).webkitSpeechRecognition
      ),
    () => false
  );

  React.useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isOpen]);

  // Handle Speech-to-Text Toggle
  const toggleListening = () => {
    if (isListening) {
      if (recognitionRef.current) {
        (recognitionRef.current as { stop: () => void }).stop();
      }
      setIsListening(false);
      return;
    }

    if (typeof window === "undefined") return;
    const win = window as unknown as {
      webkitSpeechRecognition?: new () => {
        continuous: boolean;
        interimResults: boolean;
        lang: string;
        onresult: (e: { results: Array<Array<{ transcript: string }>> }) => void;
        onerror: (e: { error: string }) => void;
        onend: () => void;
        start: () => void;
        stop: () => void;
      };
      SpeechRecognition?: new () => {
        continuous: boolean;
        interimResults: boolean;
        lang: string;
        onresult: (e: { results: Array<Array<{ transcript: string }>> }) => void;
        onerror: (e: { error: string }) => void;
        onend: () => void;
        start: () => void;
        stop: () => void;
      };
    };

    const SpeechRec = win.SpeechRecognition || win.webkitSpeechRecognition;
    if (!SpeechRec) {
      alert("Speech recognition is not supported in this browser. Please type your message.");
      return;
    }

    try {
      const recognition = new SpeechRec();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = selectedLocale;

      recognition.onresult = (event) => {
        const transcript = event.results[0]?.[0]?.transcript || "";
        if (transcript) {
          setInputValue((prev) => (prev ? `${prev} ${transcript}` : transcript));
        }
      };

      recognition.onerror = () => {
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognition.start();
      recognitionRef.current = recognition;
      setIsListening(true);
    } catch {
      setIsListening(false);
    }
  };

  // Text to speech playback
  const speakMessage = (text: string) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    if (speechSynthesisActive) {
      window.speechSynthesis.cancel();
      setSpeechSynthesisActive(false);
      return;
    }

    // Clean markdown before speaking
    const cleanText = text.replace(/[*#_`]/g, "");
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = selectedLocale;
    utterance.onend = () => setSpeechSynthesisActive(false);
    utterance.onerror = () => setSpeechSynthesisActive(false);

    window.speechSynthesis.speak(utterance);
    setSpeechSynthesisActive(true);
  };

  // Send message
  const handleSend = async (textToSend?: string, confirmedActionPayload?: ActionConfirmation) => {
    const text = (textToSend || inputValue).trim();
    if (!text && !confirmedActionPayload) return;
    if (loading) return;

    msgCountRef.current += 1;
    const userMsg: ChatMessage = {
      id: `user-${msgCountRef.current}`,
      role: "user",
      content: text || `[Confirmed: ${confirmedActionPayload?.action_type}]`,
      timestamp: "Just now",
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend && !confirmedActionPayload) setInputValue("");
    setLoading(true);

    try {
      const historyPayload = messages
        .filter((m) => m.id !== "welcome")
        .slice(-6)
        .map((m) => ({ role: m.role, content: m.content }));

      const res = await apiFetch<{
        conversation_id: string;
        role: string;
        content: string;
        is_emergency: boolean;
        requires_confirmation: boolean;
        pending_action?: ActionConfirmation | null;
        citations?: ChatCitation[];
        tool_calls_executed: Array<{ tool: string }>;
        model_used: string;
      }>("/chat/message", {
        method: "POST",
        body: JSON.stringify({
          message: text || "Confirm action",
          conversation_id: conversationId,
          history: historyPayload,
          confirmed_action: confirmedActionPayload || null,
        }),
      });

      if (res.conversation_id) {
        setConversationId(res.conversation_id);
      }

      msgCountRef.current += 1;
      const assistantMsg: ChatMessage = {
        id: `ai-${msgCountRef.current}`,
        role: "assistant",
        content: res.content,
        is_emergency: res.is_emergency,
        requires_confirmation: res.requires_confirmation,
        pending_action: res.pending_action,
        citations: res.citations || [],
        tool_calls: res.tool_calls_executed,
        timestamp: "Just now",
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      let errText = "Failed to communicate with CareBridge assistant. Please check backend connection.";
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

  const executeConfirmedAction = (action: ActionConfirmation) => {
    handleSend("Yes, I confirm and authorize this action.", action);
  };

  return (
    <>
      {/* Floating Trigger Button */}
      <div className="fixed bottom-6 right-6 z-40">
        <Button
          onClick={() => setIsOpen(true)}
          className="h-14 px-5 rounded-full shadow-xl bg-blue-700 hover:bg-blue-800 text-white font-medium flex items-center space-x-2 border-2 border-white/20 transition-all hover:scale-105"
          aria-label="Open CareBridge Conversational Assistant"
        >
          <Sparkles className="h-5 w-5 text-amber-300 animate-pulse" />
          <span className="font-semibold text-sm">Ask CareBridge AI</span>
        </Button>
      </div>

      {/* Drawer Overlay */}
      {isOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-900/40 backdrop-blur-xs flex justify-end">
          <div
            className="w-full max-w-lg bg-white h-full shadow-2xl flex flex-col border-l border-slate-200 animate-in slide-in-from-right duration-200"
            role="dialog"
            aria-modal="true"
            aria-label="CareBridge AI Assistant Drawer"
          >
            {/* Header */}
            <div className="px-5 py-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
              <div className="flex items-center space-x-2.5">
                <div className="h-9 w-9 rounded-lg bg-blue-700 text-white flex items-center justify-center font-bold">
                  <Bot className="h-5 w-5 text-white" />
                </div>
                <div>
                  <div className="flex items-center space-x-1.5">
                    <h3 className="font-bold text-slate-900 text-sm">CareBridge Assistant</h3>
                    <Badge variant="teal" className="text-[10px] py-0 px-1.5 font-mono">
                      Phase 10 AI
                    </Badge>
                  </div>
                  <p className="text-[11px] text-slate-500">Hospital navigation & triage assistant</p>
                </div>
              </div>
              <div className="flex items-center space-x-1">
                {speechSupported && (
                  <select
                    value={selectedLocale}
                    onChange={(e) => setSelectedLocale(e.target.value)}
                    className="text-[11px] bg-white border border-slate-200 rounded px-1.5 py-1 text-slate-600 focus:outline-hidden"
                    title="Select Voice Language"
                  >
                    <option value="en-IN">English (India)</option>
                    <option value="ta-IN">Tamil (India)</option>
                    <option value="en-US">English (US)</option>
                  </select>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsOpen(false)}
                  className="h-8 w-8 p-0 text-slate-500 hover:text-slate-800"
                  aria-label="Close Assistant"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {/* Quick Prompt Suggestions */}
            <div className="px-4 py-2 bg-blue-50/60 border-b border-blue-100 flex items-center space-x-2 overflow-x-auto text-xs text-blue-900 scrollbar-none">
              <span className="font-semibold shrink-0 text-[11px] text-blue-700">Quick:</span>
              <button
                onClick={() => handleSend("Show my active prescriptions and adherence")}
                className="shrink-0 bg-white border border-blue-200 rounded-full px-2.5 py-0.5 text-[11px] hover:bg-blue-100 transition-colors"
              >
                💊 My Prescriptions
              </button>
              <button
                onClick={() => handleSend("What doctors are available in Cardiology?")}
                className="shrink-0 bg-white border border-blue-200 rounded-full px-2.5 py-0.5 text-[11px] hover:bg-blue-100 transition-colors"
              >
                🩺 Find Cardiologists
              </button>
              <button
                onClick={() => handleSend("What is the status of my uploaded medical documents?")}
                className="shrink-0 bg-white border border-blue-200 rounded-full px-2.5 py-0.5 text-[11px] hover:bg-blue-100 transition-colors"
              >
                📄 Document Status
              </button>
            </div>

            {/* Message Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex flex-col ${
                    msg.role === "user" ? "items-end" : "items-start"
                  }`}
                >
                  {/* Emergency Critical Alert Card */}
                  {msg.is_emergency && (
                    <div className="w-full mb-2 p-3 bg-red-600 text-white rounded-lg shadow-md border border-red-700 animate-pulse">
                      <div className="flex items-center space-x-2 font-bold text-sm mb-1">
                        <AlertTriangle className="h-5 w-5 text-yellow-300" />
                        <span>EMERGENCY DISPATCH PROTOCOL</span>
                      </div>
                      <p className="text-xs text-red-50 mb-2">
                        Severe red-flag symptoms detected. Do not delay emergency care!
                      </p>
                      <div className="flex space-x-2">
                        <a
                          href="tel:112"
                          className="flex items-center space-x-1.5 bg-white text-red-700 px-3 py-1.5 rounded font-bold text-xs hover:bg-red-50"
                        >
                          <PhoneCall className="h-3.5 w-3.5" />
                          <span>Call 112 (National)</span>
                        </a>
                        <a
                          href="tel:108"
                          className="flex items-center space-x-1.5 bg-red-800 text-white px-3 py-1.5 rounded font-bold text-xs hover:bg-red-900 border border-red-500"
                        >
                          <PhoneCall className="h-3.5 w-3.5" />
                          <span>Call 108 (Ambulance)</span>
                        </a>
                      </div>
                    </div>
                  )}

                  {/* Message Bubble */}
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-3 text-xs leading-relaxed ${
                      msg.role === "user"
                        ? "bg-blue-600 text-white rounded-br-xs shadow-xs"
                        : msg.is_emergency
                        ? "bg-red-50 border border-red-200 text-slate-800 rounded-bl-xs shadow-xs"
                        : "bg-slate-100 text-slate-800 rounded-bl-xs border border-slate-200/60 shadow-xs"
                    }`}
                  >
                    <div className="whitespace-pre-wrap">{msg.content}</div>

                    {/* Sensitive Action Confirmation Card */}
                    {msg.requires_confirmation && msg.pending_action && (
                      <div className="mt-3 p-2.5 bg-amber-50 border border-amber-300 rounded-md text-amber-950">
                        <div className="flex items-center space-x-1.5 font-semibold text-[11px] text-amber-900 mb-1">
                          <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
                          <span>Confirmation Required</span>
                        </div>
                        <p className="text-[11px] mb-2">{msg.pending_action.description}</p>
                        <div className="flex space-x-2">
                          <Button
                            size="sm"
                            onClick={() => executeConfirmedAction(msg.pending_action!)}
                            className="h-7 text-xs bg-emerald-700 hover:bg-emerald-800 text-white font-medium"
                          >
                            <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
                            Confirm & Proceed
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleSend("I cancel this request.")}
                            className="h-7 text-xs border-slate-300"
                          >
                            Cancel
                          </Button>
                        </div>
                      </div>
                    )}

                    {/* Source Citations */}
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="mt-2.5 pt-2 border-t border-slate-200/80 space-y-1">
                        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                          Verified Sources:
                        </span>
                        {msg.citations.map((c, i) => (
                          <div
                            key={i}
                            className="flex items-center space-x-1 text-[10px] text-blue-700 bg-white px-2 py-0.5 rounded border border-slate-200/80"
                          >
                            {c.source_type === "document" && <FileText className="h-3 w-3 text-slate-500" />}
                            {c.source_type === "appointment" && <Calendar className="h-3 w-3 text-slate-500" />}
                            <span className="font-semibold truncate">{c.title}</span>
                            {c.snippet && <span className="text-slate-400 truncate">({c.snippet})</span>}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Tool Execution Badges */}
                    {msg.tool_calls && msg.tool_calls.length > 0 && (
                      <div className="mt-2 pt-1 border-t border-slate-200/60 flex flex-wrap gap-1">
                        {msg.tool_calls.map((t, idx) => (
                          <span
                            key={idx}
                            className="inline-flex items-center text-[9px] bg-slate-200/80 text-slate-600 px-1.5 py-0.5 rounded font-mono"
                          >
                            <ShieldCheck className="h-2.5 w-2.5 mr-1 text-emerald-600" />
                            {t.tool}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Message Meta & Audio Playback Button */}
                  <div className="flex items-center space-x-2 mt-1 px-1">
                    <span className="text-[10px] text-slate-400">{msg.timestamp}</span>
                    {msg.role === "assistant" && !msg.is_emergency && (
                      <button
                        onClick={() => speakMessage(msg.content)}
                        className="text-[10px] text-slate-400 hover:text-blue-600 transition-colors flex items-center space-x-0.5"
                        title="Read aloud"
                      >
                        {speechSynthesisActive ? (
                          <VolumeX className="h-3 w-3 text-blue-600" />
                        ) : (
                          <Volume2 className="h-3 w-3" />
                        )}
                      </button>
                    )}
                  </div>
                </div>
              ))}

              {loading && (
                <div className="flex items-center space-x-2 text-slate-400 text-xs py-2">
                  <div className="h-4 w-4 rounded-full border-2 border-blue-600 border-t-transparent animate-spin" />
                  <span>CareBridge assistant is consulting verified hospital records...</span>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input Bar with Voice & Keyboard Controls */}
            <div className="p-4 border-t border-slate-200 bg-white">
              {isListening && (
                <div className="mb-2 p-1.5 bg-red-50 border border-red-200 rounded text-red-700 text-xs flex items-center justify-between animate-pulse">
                  <span className="flex items-center space-x-1.5">
                    <Mic className="h-3.5 w-3.5" />
                    <span>Listening ({selectedLocale}). Speak now...</span>
                  </span>
                  <button
                    onClick={toggleListening}
                    className="text-[11px] underline font-bold"
                  >
                    Stop
                  </button>
                </div>
              )}

              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSend();
                }}
                className="flex items-center space-x-2"
              >
                {/* Voice Input Toggle Button */}
                {speechSupported && (
                  <Button
                    type="button"
                    variant={isListening ? "destructive" : "outline"}
                    size="sm"
                    onClick={toggleListening}
                    className={`h-9 w-9 p-0 shrink-0 ${
                      isListening ? "bg-red-600 hover:bg-red-700 text-white animate-pulse" : "border-slate-300 text-slate-600"
                    }`}
                    title={isListening ? "Stop Listening" : "Speak Message"}
                    aria-label="Toggle Speech Recognition"
                  >
                    {isListening ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
                  </Button>
                )}

                <input
                  type="text"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  placeholder="Ask hospital questions, doctor slots, or prescriptions..."
                  className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-xs text-slate-800 placeholder-slate-400 focus:border-blue-600 focus:outline-hidden focus:ring-1 focus:ring-blue-600"
                  disabled={loading}
                />
                <Button
                  type="submit"
                  size="sm"
                  disabled={!inputValue.trim() || loading}
                  className="h-9 px-3 bg-blue-700 hover:bg-blue-800 text-white shrink-0"
                  aria-label="Send Message"
                >
                  <Send className="h-3.5 w-3.5" />
                </Button>
              </form>
              <div className="flex items-center justify-between text-[10px] text-slate-400 mt-2 px-1">
                <span>Safe navigation co-pilot</span>
                <span>Zero real PHI transmitted</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
