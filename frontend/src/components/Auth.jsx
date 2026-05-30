import { useState } from "react";
import { api } from "../api.js";

export default function Auth({ onLogin }) {
  const [tab, setTab] = useState("login");
  const [email, setEmail] = useState("admin@pestguard.com");
  const [password, setPassword] = useState("demo1234");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (tab === "login") {
        const data = await api.login(email, password);
        onLogin(data.access_token, data.user);
      } else {
        await api.register(email, fullName, password);
        const data = await api.login(email, password);
        onLogin(data.access_token, data.user);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-logo">🐛 PestGuard <span>Pro</span></div>
        <p className="auth-subtitle">AI-powered pest control automation</p>

        <div className="auth-tabs">
          <button className={`auth-tab ${tab === "login" ? "active" : ""}`} onClick={() => setTab("login")}>Login</button>
          <button className={`auth-tab ${tab === "register" ? "active" : ""}`} onClick={() => setTab("register")}>Register</button>
        </div>

        {error && <div className="error-msg">{error}</div>}

        <form className="form" onSubmit={handleSubmit}>
          {tab === "register" && (
            <div className="field">
              <label>Full Name</label>
              <input value={fullName} onChange={e => setFullName(e.target.value)} placeholder="Your name" required />
            </div>
          )}
          <div className="field">
            <label>Email</label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@company.com" required />
          </div>
          <div className="field">
            <label>Password</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" required />
          </div>
          <button className="btn btn-primary" type="submit" disabled={loading} style={{ marginTop: 4 }}>
            {loading ? "Please wait…" : tab === "login" ? "Sign In" : "Create Account"}
          </button>
        </form>

        <p style={{ marginTop: 16, fontSize: 12, color: "var(--text-muted)", textAlign: "center" }}>
          Demo: admin@pestguard.com / demo1234
        </p>
      </div>
    </div>
  );
}
