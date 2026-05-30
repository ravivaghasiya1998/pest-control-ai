import { useState, useEffect } from "react";
import { api } from "../api.js";

function ScoreBar({ score, tier }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div className="score-bar" style={{ width: 50 }}>
        <div className={`score-fill ${tier || "nurture"}`} style={{ width: `${score || 0}%` }} />
      </div>
      <span style={{ fontWeight: 700, fontSize: 13 }}>{score || 0}</span>
    </div>
  );
}

const URGENCY_COLORS = { emergency: "badge-emergency", high: "badge-high", medium: "badge-medium", low: "badge-low" };
const STATUS_COLORS = { hot: "badge-hot", qualified: "badge-qualified", nurture: "badge-nurture", new: "badge-new", converted: "badge-converted" };

export default function Leads() {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [qualifying, setQualifying] = useState({});
  const [selected, setSelected] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [createError, setCreateError] = useState("");
  const [conflict, setConflict] = useState(null); // { conflict_field, existing }
  const [deleteModal, setDeleteModal] = useState(null); // lead to delete
  const [deleteReason, setDeleteReason] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", phone: "", address: "", city: "", property_type: "residential", pest_type: "general", pest_description: "", urgency: "medium", source: "website", is_repeat_customer: false });

  async function load() {
    setLoading(true);
    try {
      const data = await api.leads(statusFilter ? { status: statusFilter } : {});
      setLeads(data.items || []);
    } catch { /* ignore */ } finally { setLoading(false); }
  }

  useEffect(() => { load(); }, [statusFilter]);

  async function qualify(id) {
    setQualifying(q => ({ ...q, [id]: true }));
    try {
      const result = await api.qualifyLead(id);
      setLeads(ls => ls.map(l => l.id === id ? result.lead : l));
    } catch { /* ignore */ } finally {
      setQualifying(q => ({ ...q, [id]: false }));
    }
  }

  async function confirmDelete() {
    if (!deleteReason.trim() || deleteReason.trim().length < 5) {
      setDeleteError("Please enter a reason (at least 5 characters)");
      return;
    }
    setDeleting(true);
    setDeleteError("");
    try {
      await api.deleteLead(deleteModal.id, deleteReason.trim());
      setDeleteModal(null);
      setDeleteReason("");
      if (selected?.id === deleteModal.id) setSelected(null);
      load();
    } catch (err) {
      setDeleteError(err.message);
    } finally {
      setDeleting(false);
    }
  }

  async function createLead(e) {
    e.preventDefault();
    setCreateError("");
    setConflict(null);
    try {
      await api.createLead(form);
      setShowCreate(false);
      setForm({ name: "", email: "", phone: "", address: "", city: "", property_type: "residential", pest_type: "general", pest_description: "", urgency: "medium", source: "website", is_repeat_customer: false });
      load();
    } catch (err) {
      if (err.message === "duplicate_lead" && err.conflict) {
        setConflict(err.conflict);
      } else {
        setCreateError(err.message);
      }
    }
  }

  function clearConflictField() {
    if (!conflict) return;
    setForm(f => ({ ...f, [conflict.conflict_field]: "" }));
    setConflict(null);
    setCreateError("");
  }

  function viewExisting() {
    setSelected(conflict.existing);
    setConflict(null);
    setShowCreate(false);
  }

  const filterBtns = ["", "hot", "qualified", "nurture", "new"];

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Lead Pipeline</div>
          <div className="page-subtitle">{leads.length} leads · AI qualification powered by {statusFilter || "all"}</div>
        </div>
        <div className="btn-group">
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>+ Add Lead</button>
          <button className="btn btn-secondary" onClick={load}>↻</button>
        </div>
      </div>

      {/* Filter bar */}
      <div className="pill-group mb-12">
        {filterBtns.map(s => (
          <button key={s || "all"} className={`btn btn-sm ${statusFilter === s ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setStatusFilter(s)}>
            {s || "All"}
          </button>
        ))}
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="card section-gap">
          <div className="card-header">New Lead<button className="btn btn-sm btn-secondary" onClick={() => setShowCreate(false)}>Cancel</button></div>
          <div className="card-body">
            {createError && <div className="error-msg" style={{ marginBottom: 12 }}>{createError}</div>}

            {conflict && (
              <div style={{ background: "#fffbeb", border: "1px solid #fcd34d", borderRadius: 8, padding: 14, marginBottom: 14 }}>
                <div style={{ fontWeight: 700, color: "#92400e", marginBottom: 6 }}>
                  ⚠️ Duplicate {conflict.conflict_field === "email" ? "Email" : "Phone Number"}
                </div>
                <div style={{ fontSize: 13, color: "#78350f", marginBottom: 10 }}>
                  A lead already exists with this {conflict.conflict_field}:
                  <strong> {conflict.existing.name}</strong> — {conflict.existing.pest_type} in {conflict.existing.city}
                  <span style={{ marginLeft: 6 }} className={`badge ${conflict.existing.status === "hot" ? "badge-hot" : "badge-new"}`}>
                    {conflict.existing.status}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: "#92400e", marginBottom: 12 }}>
                  Is this the same person? If not, ask them to provide a different {conflict.conflict_field === "email" ? "email address" : "phone number"}.
                </div>
                <div className="btn-group">
                  <button type="button" className="btn btn-secondary btn-sm" onClick={viewExisting}>
                    View existing lead
                  </button>
                  <button type="button" className="btn btn-sm btn-amber" onClick={clearConflictField}>
                    Update {conflict.conflict_field === "email" ? "email" : "phone"} and retry
                  </button>
                </div>
              </div>
            )}

            <form className="form" onSubmit={createLead}>
              <div className="form-row">
                <div className="field"><label>Name</label><input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} required /></div>
                <div className="field"><label>Email</label><input type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} required /></div>
              </div>
              <div className="form-row">
                <div className="field"><label>Phone</label><input value={form.phone} onChange={e => setForm(f => ({ ...f, phone: e.target.value }))} /></div>
                <div className="field"><label>City</label><input value={form.city} onChange={e => setForm(f => ({ ...f, city: e.target.value }))} required /></div>
              </div>
              <div className="field"><label>Address</label><input value={form.address} onChange={e => setForm(f => ({ ...f, address: e.target.value }))} /></div>
              <div className="form-row">
                <div className="field"><label>Property Type</label>
                  <select value={form.property_type} onChange={e => setForm(f => ({ ...f, property_type: e.target.value }))}>
                    <option value="residential">Residential</option><option value="commercial">Commercial</option><option value="multi-family">Multi-Family</option>
                  </select>
                </div>
                <div className="field"><label>Pest Type</label>
                  <select value={form.pest_type} onChange={e => setForm(f => ({ ...f, pest_type: e.target.value }))}>
                    {["termites","bedbugs","rodents","roaches","wasps","ants","spiders","general"].map(p => <option key={p}>{p}</option>)}
                  </select>
                </div>
              </div>
              <div className="form-row">
                <div className="field"><label>Urgency</label>
                  <select value={form.urgency} onChange={e => setForm(f => ({ ...f, urgency: e.target.value }))}>
                    <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="emergency">Emergency</option>
                  </select>
                </div>
                <div className="field"><label>Source</label>
                  <select value={form.source} onChange={e => setForm(f => ({ ...f, source: e.target.value }))}>
                    {["website","phone","chat","referral"].map(s => <option key={s}>{s}</option>)}
                  </select>
                </div>
              </div>
              <div className="field"><label>Description</label><textarea value={form.pest_description} onChange={e => setForm(f => ({ ...f, pest_description: e.target.value }))} /></div>
              <button className="btn btn-primary" type="submit">Create Lead</button>
            </form>
          </div>
        </div>
      )}

      {loading ? <div className="loading">Loading leads…</div> : (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Contact</th><th>Pest / Property</th><th>City</th><th>Urgency</th><th>Score</th><th>Status</th><th>Actions</th></tr>
              </thead>
              <tbody>
                {leads.length === 0 && <tr><td colSpan={7}><div className="empty-state"><div className="empty-icon">🎯</div>No leads found</div></td></tr>}
                {leads.map(l => (
                  <tr key={l.id} style={{ cursor: "pointer" }} onClick={() => setSelected(selected?.id === l.id ? null : l)}>
                    <td>
                      <div className="td-name">{l.name}</div>
                      <div className="td-muted text-sm">{l.email}</div>
                    </td>
                    <td>
                      <div>{l.pest_type}</div>
                      <div className="td-muted text-sm">{l.property_type}</div>
                    </td>
                    <td>{l.city}</td>
                    <td><span className={`badge ${URGENCY_COLORS[l.urgency] || "badge-medium"}`}>{l.urgency}</span></td>
                    <td><ScoreBar score={l.qualification?.score} tier={l.qualification?.tier} /></td>
                    <td><span className={`badge ${STATUS_COLORS[l.status] || "badge-new"}`}>{l.status}</span></td>
                    <td onClick={e => e.stopPropagation()}>
                      <div className="btn-group" style={{ flexWrap: "nowrap" }}>
                        <button className="btn btn-sm btn-secondary" onClick={() => qualify(l.id)} disabled={qualifying[l.id]}>
                          {qualifying[l.id] ? "…" : "⚡ Qualify"}
                        </button>
                        <button className="btn btn-sm" style={{ background: "#fee2e2", color: "#dc2626", border: "none" }}
                          onClick={() => { setDeleteModal(l); setDeleteReason(""); setDeleteError(""); }}>
                          🗑
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Delete lead modal */}
      {deleteModal && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div style={{ background: "var(--card)", borderRadius: 12, padding: 28, minWidth: 380, boxShadow: "0 8px 32px rgba(0,0,0,0.2)" }}>
            <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 4 }}>Delete Lead</div>
            <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 16 }}>
              You are about to permanently delete <strong>{deleteModal.name}</strong> ({deleteModal.pest_type} · {deleteModal.city}).
              This cannot be undone.
            </div>
            {deleteError && <div className="error-msg" style={{ marginBottom: 12 }}>{deleteError}</div>}
            <div className="field">
              <label>Reason for deletion <span style={{ color: "#dc2626" }}>*</span></label>
              <textarea
                rows={3}
                placeholder="Explain why this lead is being deleted…"
                value={deleteReason}
                onChange={e => setDeleteReason(e.target.value)}
                autoFocus
                style={{ resize: "vertical" }}
              />
            </div>
            <div className="btn-group" style={{ marginTop: 16, justifyContent: "flex-end" }}>
              <button className="btn btn-secondary" onClick={() => setDeleteModal(null)} disabled={deleting}>Cancel</button>
              <button
                className="btn"
                style={{ background: "#dc2626", color: "#fff", border: "none" }}
                onClick={confirmDelete}
                disabled={deleting}
              >
                {deleting ? "Deleting…" : "Confirm Delete"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Lead detail panel */}
      {selected && (
        <div className="card mt-8">
          <div className="card-header">
            {selected.name} — Lead Detail
            <button className="btn btn-sm btn-secondary" onClick={() => setSelected(null)}>Close</button>
          </div>
          <div className="card-body">
            <div className="grid-3" style={{ marginBottom: 12 }}>
              {[
                ["Email", selected.email], ["Phone", selected.phone || "—"], ["City", selected.city],
                ["Address", selected.address || "—"], ["Property", selected.property_type], ["Source", selected.source],
              ].map(([k, v]) => (
                <div key={k}>
                  <div className="text-sm text-muted">{k}</div>
                  <div style={{ fontWeight: 600 }}>{v}</div>
                </div>
              ))}
            </div>
            {selected.pest_description && (
              <div style={{ marginBottom: 12 }}>
                <div className="text-sm text-muted mb-12">Description</div>
                <div style={{ fontSize: 13 }}>{selected.pest_description}</div>
              </div>
            )}
            {selected.qualification?.reasons?.length > 0 && (
              <div>
                <div className="text-sm text-muted" style={{ marginBottom: 6 }}>Qualification Reasons</div>
                <ul style={{ paddingLeft: 16, display: "flex", flexDirection: "column", gap: 4 }}>
                  {selected.qualification.reasons.map((r, i) => <li key={i} style={{ fontSize: 13 }}>{r}</li>)}
                </ul>
                {selected.qualification.next_step && (
                  <div style={{ marginTop: 10, padding: "8px 12px", background: "var(--green-light)", borderRadius: 7, fontSize: 13, color: "var(--green-dark)" }}>
                    <strong>Next step:</strong> {selected.qualification.next_step}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
