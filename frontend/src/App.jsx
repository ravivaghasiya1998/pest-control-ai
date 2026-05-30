import { useState, useEffect, useCallback } from "react";
import { api } from "./api.js";
import Auth from "./components/Auth.jsx";
import Dashboard from "./components/Dashboard.jsx";
import Leads from "./components/Leads.jsx";
import Jobs from "./components/Jobs.jsx";
import Chat from "./components/Chat.jsx";
import Reports from "./components/Reports.jsx";
import AdminPanel from "./components/AdminPanel.jsx";
import Profile from "./components/Profile.jsx";
import ChangePasswordModal from "./components/ChangePasswordModal.jsx";

const ALL_PAGES = [
  { id: "dashboard", label: "Dashboard", icon: "📊", roles: ["admin"] },
  { id: "leads",     label: "Leads",     icon: "🎯", roles: ["admin"] },
  { id: "jobs",      label: "Jobs",      icon: "🔧", roles: ["admin", "technician"] },
  { id: "chat",      label: "Chat Agent",icon: "💬", roles: ["admin", "user"] },
  { id: "reports",   label: "Reports",   icon: "📈", roles: ["admin"] },
  { id: "admin",     label: "Admin",     icon: "⚙️",  roles: ["admin"] },
];

const PAGE_TITLES = {
  dashboard: "Dashboard", leads: "Lead Pipeline", jobs: "Job Operations",
  chat: "Customer Service Agent", reports: "AI Reports", admin: "Admin Panel",
};

const DEFAULT_PAGE = { admin: "dashboard", technician: "jobs", user: "chat" };

export default function App() {
  const [user, setUser] = useState(null);
  const [page, setPage] = useState("dashboard");
  const [provider, setProvider] = useState("mock");
  const [showProfile, setShowProfile] = useState(false);
  const [showChangePw, setShowChangePw] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("token");
    const saved = localStorage.getItem("user");
    if (token && saved) {
      try {
        const u = JSON.parse(saved);
        setUser(u);
        setPage(DEFAULT_PAGE[u.role] || "jobs");
      } catch { /* ignore */ }
    }
  }, []);

  useEffect(() => {
    fetch("/api/health").then(r => r.json()).then(d => setProvider(d.provider || "mock")).catch(() => {});
  }, []);

  const handleLogin = useCallback((token, userData) => {
    localStorage.setItem("token", token);
    localStorage.setItem("user", JSON.stringify(userData));
    setUser(userData);
    setPage(DEFAULT_PAGE[userData.role] || "jobs");
  }, []);

  const handleLogout = useCallback(() => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setUser(null);
    setShowProfile(false);
  }, []);

  const handleUserUpdate = useCallback((updated) => {
    localStorage.setItem("user", JSON.stringify(updated));
    setUser(updated);
  }, []);

  if (!user) return <Auth onLogin={handleLogin} />;

  const visiblePages = ALL_PAGES.filter(p => p.roles.includes(user.role));

  const pageComponents = {
    dashboard: <Dashboard />,
    leads: <Leads />,
    jobs: <Jobs />,
    chat: <Chat userId={user.id} />,
    reports: <Reports />,
    admin: <AdminPanel />,
  };

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          🐛 PestGuard <span>Pro</span>
          <div className="sidebar-subtitle">AI Automation Suite</div>
        </div>
        <nav className="sidebar-nav">
          {visiblePages.map(p => (
            <div
              key={p.id}
              className={`nav-item ${page === p.id ? "active" : ""}`}
              onClick={() => setPage(p.id)}
            >
              <span className="nav-icon">{p.icon}</span>
              {p.label}
            </div>
          ))}
        </nav>
        <div className="sidebar-footer">v1.0 · {new Date().getFullYear()}</div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="topbar-title">{PAGE_TITLES[page]}</div>
          <div className="topbar-right">
            <span className="provider-badge">🤖 {provider}</span>
            <div style={{ position: "relative" }}>
              <button
                className="btn btn-secondary btn-sm"
                style={{ borderRadius: "50%", width: 36, height: 36, padding: 0, fontWeight: 700 }}
                onClick={() => setShowProfile(v => !v)}
                title={user.full_name}
              >
                {user.full_name?.[0]?.toUpperCase() || "?"}
              </button>
              {showProfile && (
                <Profile
                  user={user}
                  onClose={() => setShowProfile(false)}
                  onLogout={handleLogout}
                  onChangePassword={() => { setShowProfile(false); setShowChangePw(true); }}
                  onUserUpdate={handleUserUpdate}
                />
              )}
            </div>
          </div>
        </header>
        <div className="page">
          {pageComponents[page] || pageComponents[DEFAULT_PAGE[user.role]]}
        </div>
      </div>

      {/* Forced password change — can't dismiss */}
      {user.must_change_password && (
        <ChangePasswordModal
          forced
          onSuccess={handleUserUpdate}
        />
      )}

      {/* Voluntary password change from profile */}
      {showChangePw && !user.must_change_password && (
        <ChangePasswordModal
          onSuccess={(updated) => { handleUserUpdate(updated); setShowChangePw(false); }}
          onClose={() => setShowChangePw(false)}
        />
      )}
    </div>
  );
}
