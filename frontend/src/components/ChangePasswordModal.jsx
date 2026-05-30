import { useState } from "react";
import { api } from "../api.js";

export default function ChangePasswordModal({ forced = false, onSuccess, onClose }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (next !== confirm) { setError("Passwords do not match"); return; }
    if (next.length < 8) { setError("Password must be at least 8 characters"); return; }
    setSaving(true);
    try {
      const updated = await api.changePassword(current, next);
      onSuccess(updated);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
    }}>
      <div style={{
        background: "var(--card)", borderRadius: 12, padding: 28,
        minWidth: 360, boxShadow: "0 8px 32px rgba(0,0,0,0.25)",
      }}>
        <div style={{ fontWeight: 700, fontSize: 17, marginBottom: 4 }}>
          {forced ? "🔑 Set Your Password" : "Change Password"}
        </div>
        {forced && (
          <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 16 }}>
            Your account was created by an admin. Please set a new password before continuing.
          </div>
        )}

        {error && <div className="error-msg" style={{ marginBottom: 12 }}>{error}</div>}

        <form className="form" onSubmit={handleSubmit}>
          <div className="field">
            <label>Current Password</label>
            <input type="password" value={current} onChange={e => setCurrent(e.target.value)}
              placeholder="Enter the password you received" required autoFocus />
          </div>
          <div className="field">
            <label>New Password</label>
            <input type="password" value={next} onChange={e => setNext(e.target.value)}
              placeholder="At least 8 characters" required />
          </div>
          <div className="field">
            <label>Confirm New Password</label>
            <input type="password" value={confirm} onChange={e => setConfirm(e.target.value)}
              placeholder="Repeat new password" required />
          </div>
          <div className="btn-group" style={{ marginTop: 8, justifyContent: "flex-end" }}>
            {!forced && (
              <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            )}
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? "Saving…" : "Set New Password"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
