import { useState, useEffect, useRef } from "react";
import { api } from "../api.js";

const ROLE_BADGE = {
  admin:      { label: "Admin",      color: "#dc2626", bg: "#fee2e2" },
  technician: { label: "Technician", color: "#2563eb", bg: "#dbeafe" },
  user:       { label: "User",       color: "#6b7280", bg: "#f3f4f6" },
};

export default function Profile({ user, onClose, onLogout, onChangePassword, onUserUpdate }) {
  const [editing, setEditing] = useState(false);
  const [fullName, setFullName] = useState(user.full_name);
  const [phone, setPhone] = useState(user.phone || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [deleteResult, setDeleteResult] = useState(null);
  const ref = useRef(null);

  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) onClose();
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [onClose]);

  async function saveProfile() {
    setSaving(true);
    setError("");
    try {
      const updated = await api.updateProfile({ full_name: fullName, phone });
      onUserUpdate(updated);
      setEditing(false);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteAccount() {
    setDeleting(true);
    setDeleteError("");
    try {
      const result = await api.deleteAccount();
      setDeleteResult(result);
      if (result.status === "deleted") {
        setTimeout(onLogout, 1500);
      }
    } catch (e) {
      setDeleteError(e.message);
    } finally {
      setDeleting(false);
    }
  }

  const badge = ROLE_BADGE[user.role] || ROLE_BADGE.user;

  return (
    <div
      ref={ref}
      style={{
        position: "absolute", top: "calc(100% + 8px)", right: 0, zIndex: 200,
        background: "var(--card)", border: "1px solid var(--border)",
        borderRadius: 12, boxShadow: "0 8px 32px rgba(0,0,0,0.15)",
        minWidth: 280, padding: 20,
      }}
    >
      {/* Avatar + name + role */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
        <div style={{
          width: 48, height: 48, borderRadius: "50%", background: "var(--primary)",
          color: "#fff", display: "flex", alignItems: "center", justifyContent: "center",
          fontWeight: 700, fontSize: 20,
        }}>
          {user.full_name?.[0]?.toUpperCase()}
        </div>
        <div>
          <div style={{ fontWeight: 700, fontSize: 15 }}>{user.full_name}</div>
          <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{user.email}</div>
          <span style={{
            fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 20,
            color: badge.color, background: badge.bg, marginTop: 4, display: "inline-block",
          }}>
            {badge.label}
          </span>
        </div>
      </div>

      <div style={{ borderTop: "1px solid var(--border)", paddingTop: 14 }}>
        {!editing ? (
          <>
            <div style={{ fontSize: 13, marginBottom: 8 }}>
              <span style={{ color: "var(--text-muted)" }}>Phone: </span>
              {user.phone || <span style={{ color: "var(--text-muted)" }}>—</span>}
            </div>
            <button className="btn btn-secondary btn-sm" style={{ width: "100%", marginBottom: 8 }}
              onClick={() => setEditing(true)}>
              Edit Profile
            </button>
          </>
        ) : (
          <>
            {error && <div className="error-msg" style={{ marginBottom: 8, fontSize: 12 }}>{error}</div>}
            <div className="field" style={{ marginBottom: 8 }}>
              <label style={{ fontSize: 12 }}>Full Name</label>
              <input value={fullName} onChange={e => setFullName(e.target.value)} style={{ fontSize: 13 }} />
            </div>
            <div className="field" style={{ marginBottom: 10 }}>
              <label style={{ fontSize: 12 }}>Phone</label>
              <input value={phone} onChange={e => setPhone(e.target.value)} style={{ fontSize: 13 }} />
            </div>
            <div className="btn-group" style={{ marginBottom: 8 }}>
              <button className="btn btn-secondary btn-sm" onClick={() => setEditing(false)}>Cancel</button>
              <button className="btn btn-primary btn-sm" onClick={saveProfile} disabled={saving}>
                {saving ? "Saving…" : "Save"}
              </button>
            </div>
          </>
        )}

        <button className="btn btn-secondary btn-sm" style={{ width: "100%", marginBottom: 8 }}
          onClick={onChangePassword}>
          🔑 Change Password
        </button>

        {/* Delete account */}
        {!showDeleteConfirm && !deleteResult && (
          <button className="btn btn-sm" style={{ width: "100%", marginBottom: 8, background: "#fff", color: "#dc2626", border: "1px solid #fca5a5" }}
            onClick={() => { setShowDeleteConfirm(true); setDeleteError(""); }}>
            Delete Account
          </button>
        )}

        {showDeleteConfirm && !deleteResult && (
          <div style={{ border: "1px solid #fca5a5", borderRadius: 8, padding: 12, marginBottom: 8, background: "#fff5f5" }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#dc2626", marginBottom: 6 }}>
              {user.role === "technician"
                ? "Request will be sent to admin for approval."
                : "This will permanently delete your account."}
            </div>
            {user.role === "user" && (
              <div style={{ fontSize: 11, color: "#92400e", marginBottom: 8 }}>
                Active or scheduled appointments will block deletion.
              </div>
            )}
            {deleteError && (
              <div className="error-msg" style={{ fontSize: 11, marginBottom: 8 }}>{deleteError}</div>
            )}
            <div className="btn-group">
              <button className="btn btn-secondary btn-sm" onClick={() => setShowDeleteConfirm(false)}>Cancel</button>
              <button
                className="btn btn-sm"
                style={{ background: "#dc2626", color: "#fff", border: "none" }}
                disabled={deleting}
                onClick={handleDeleteAccount}
              >
                {deleting ? "…" : "Confirm"}
              </button>
            </div>
          </div>
        )}

        {deleteResult && (
          <div style={{ fontSize: 12, padding: "8px 10px", borderRadius: 8, marginBottom: 8,
            background: deleteResult.status === "deleted" ? "#f0fdf4" : "#eff6ff",
            color: deleteResult.status === "deleted" ? "#166534" : "#1e40af",
            border: `1px solid ${deleteResult.status === "deleted" ? "#86efac" : "#93c5fd"}` }}>
            {deleteResult.status === "deleted"
              ? "✅ Account deleted. Logging out…"
              : "📨 " + deleteResult.message}
          </div>
        )}

        {!deleteResult && (
          <button className="btn btn-sm" style={{ width: "100%", background: "#fee2e2", color: "#dc2626", border: "none" }}
            onClick={onLogout}>
            Logout
          </button>
        )}
      </div>
    </div>
  );
}
