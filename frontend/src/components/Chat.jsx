import { useState, useEffect, useRef } from "react";
import MarkdownText from "./MarkdownText.jsx";
import { api } from "../api.js";

const sessionKey = (userId) => `pestguard_chat_${userId}`;

function generateSessionId() {
  return `chat-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

const GREETING = {
  id: 0,
  role: "assistant",
  content: "👋 Hello! I'm the PestGuard Pro AI assistant. I can help with pricing, scheduling, pest information, and booking appointments. What pest problem can I help you with today?",
  created_at: new Date().toISOString(),
};

function formatTime(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

const QUICK_REPLIES = [
  "How much does termite treatment cost?",
  "Do you serve Berlin?",
  "I need to book an appointment",
  "Is it safe for my pets?",
  "What pests do you treat?",
  "Tell me about your annual plans",
];

export default function Chat({ userId }) {
  const KEY = sessionKey(userId);
  const [sessionId] = useState(() => localStorage.getItem(KEY) || generateSessionId());
  const [messages, setMessages] = useState([GREETING]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [visitorName, setVisitorName] = useState("Visitor");
  const [bookedLeads, setBookedLeads] = useState([]);
  const bottomRef = useRef(null);

  useEffect(() => {
    localStorage.setItem(KEY, sessionId);
    setLoading(true);
    api.getConversation(sessionId)
      .then(data => {
        if (data.messages?.length) {
          setMessages([GREETING, ...data.messages]);
          if (data.visitor_name && data.visitor_name !== "Visitor") {
            setVisitorName(data.visitor_name);
          }
        }
      })
      .catch(() => { /* 404 = new session, keep greeting only */ })
      .finally(() => setLoading(false));
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function send(text) {
    const msg = text || input.trim();
    if (!msg || sending) return;
    setInput("");

    const userMsg = { id: Date.now(), role: "user", content: msg, created_at: new Date().toISOString() };
    setMessages(prev => [...prev, userMsg]);
    setSending(true);

    try {
      const data = await api.chat(sessionId, msg, visitorName);
      const assistantMsg = { id: Date.now() + 1, role: "assistant", content: data.reply, created_at: new Date().toISOString() };
      setMessages(prev => [...prev, assistantMsg]);
      if (data.booked_leads?.length) {
        setBookedLeads(prev => [...prev, ...data.booked_leads]);
      }
    } catch (e) {
      setMessages(prev => [...prev, {
        id: Date.now() + 1, role: "assistant",
        content: "Sorry, I'm having trouble connecting. Please try again.",
        created_at: new Date().toISOString(),
      }]);
    } finally {
      setSending(false);
    }
  }

  function handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  }

  function newSession() {
    localStorage.setItem(KEY, generateSessionId());
    window.location.reload();
  }

  return (
    <div style={{ maxWidth: 720, margin: "0 auto" }}>
      <div className="page-header">
        <div>
          <div className="page-title">Customer Service Agent</div>
          <div className="page-subtitle">AI-powered chat · Books appointments · Answers FAQs · Collects leads</div>
        </div>
        <div className="btn-group">
          <div className="field" style={{ margin: 0 }}>
            <input
              placeholder="Your name"
              value={visitorName}
              onChange={e => setVisitorName(e.target.value)}
              style={{ width: 140 }}
            />
          </div>
          <button className="btn btn-secondary btn-sm" onClick={newSession}>New Session</button>
        </div>
      </div>

      {bookedLeads.length > 0 && (
        <div className="success-msg" style={{ marginBottom: 12 }}>
          ✅ Appointment booked!{" "}
          {bookedLeads.map(l => l.name || l.id).join(", ")} —{" "}
          {bookedLeads.some(l => l.is_existing)
            ? "matched to an existing lead."
            : "lead and job created."}{" "}
          Check the <strong>Leads</strong> and <strong>Jobs</strong> tabs.
        </div>
      )}

      <div className="chat-container" style={{ height: "calc(100vh - 240px)" }}>
        <div className="chat-messages">
          {loading && (
            <div className="msg msg-assistant">
              <div className="msg-bubble"><span className="chat-typing">Loading history…</span></div>
            </div>
          )}
          {messages.map(m => (
            <div key={m.id} className={`msg msg-${m.role}`}>
              <div className="msg-bubble">
                {m.role === "assistant"
                  ? <MarkdownText>{m.content}</MarkdownText>
                  : m.content
                }
              </div>
              <div className="msg-time">{formatTime(m.created_at)}</div>
            </div>
          ))}
          {sending && (
            <div className="msg msg-assistant">
              <div className="msg-bubble">
                <span className="chat-typing">PestGuard AI is typing…</span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Quick replies */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, margin: "10px 0" }}>
          {QUICK_REPLIES.map(q => (
            <button key={q} className="btn btn-secondary btn-sm"
              onClick={() => send(q)} disabled={sending}
              style={{ borderRadius: 20, fontSize: 12 }}>
              {q}
            </button>
          ))}
        </div>

        <div className="chat-input-row">
          <input
            className="chat-input"
            placeholder="Type your message…"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            disabled={sending || loading}
          />
          <button className="chat-send" onClick={() => send()} disabled={sending || loading || !input.trim()}>
            Send
          </button>
        </div>
      </div>

      <div style={{ marginTop: 16, padding: 12, background: "var(--card)", borderRadius: 8, border: "1px solid var(--border)", fontSize: 12, color: "var(--text-muted)" }}>
        <strong>Session:</strong> {sessionId} ·
        <strong> Provider:</strong> {localStorage.getItem("provider") || "mock"} ·
        The agent can book appointments — try asking "I need to book a termite inspection in Berlin"
      </div>
    </div>
  );
}
