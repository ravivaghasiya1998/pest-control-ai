const BASE = "/api";

function getToken() {
  return localStorage.getItem("token") || "";
}

async function request(method, path, body = null, auth = true) {
  const headers = { "Content-Type": "application/json" };
  if (auth) headers["Authorization"] = `Bearer ${getToken()}`;
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({ detail: res.statusText }));
    if (res.status === 409 && payload.detail?.code === "duplicate_lead") {
      const err = new Error("duplicate_lead");
      err.conflict = payload.detail;
      throw err;
    }
    throw new Error(
      typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail) || "Request failed"
    );
  }
  return res.json();
}

export const api = {
  // Auth
  login: (email, password) => request("POST", "/auth/login", { email, password }, false),
  register: (email, full_name, password) => request("POST", "/auth/register", { email, full_name, password }, false),
  me: () => request("GET", "/auth/me"),
  changePassword: (current_password, new_password) => request("POST", "/auth/change-password", { current_password, new_password }),
  updateProfile: (data) => request("PATCH", "/auth/profile", data),
  deleteAccount: () => request("DELETE", "/auth/account"),

  deleteLead: (lead_id, reason) => request("DELETE", `/leads/${lead_id}`, { reason }),

  // Admin
  createTechnician: (data) => request("POST", "/admin/create-technician", data),
  setTechnicianStatus: (id, is_available) => request("PATCH", `/admin/technicians/${id}/status`, { is_available }),
  deleteTechnician: (id) => request("DELETE", `/admin/technicians/${id}`),
  listDeleteRequests: () => request("GET", "/admin/delete-requests"),
  approveDeleteRequest: (userId) => request("POST", `/admin/delete-requests/${userId}/approve`),
  rejectDeleteRequest: (userId) => request("POST", `/admin/delete-requests/${userId}/reject`),

  // Dashboard
  dashboard: () => request("GET", "/dashboard"),

  // Leads
  leads: (params = {}) => {
    const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString();
    return request("GET", `/leads${q ? `?${q}` : ""}`);
  },
  createLead: (data) => request("POST", "/leads", data),
  getLead: (id) => request("GET", `/leads/${id}`),
  qualifyLead: (id) => request("POST", `/leads/${id}/qualify`),
  qualifyAll: () => request("POST", "/leads/qualify-all"),

  // Jobs
  jobs: (params = {}) => {
    const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString();
    return request("GET", `/jobs${q ? `?${q}` : ""}`);
  },
  createJob: (data) => request("POST", "/jobs", data),
  updateJob: (id, data) => request("PATCH", `/jobs/${id}`, data),

  // Operations
  assignJobs: () => request("POST", "/operations/assign"),
  sendReminders: () => request("POST", "/operations/reminders"),
  sendFollowups: () => request("POST", "/operations/followups"),

  // Technicians
  technicians: () => request("GET", "/technicians"),

  // Chat (no auth required)
  chat: (session_id, message, visitor_name = "Visitor", visitor_email = "") =>
    request("POST", "/chat/message", { session_id, message, visitor_name, visitor_email }, false),
  getConversation: (session_id) => request("GET", `/chat/${session_id}`, null, false),

  // Reports
  reports: () => request("GET", "/reports"),
  generateReport: (report_type, question = "") => request("POST", "/reports/generate", { report_type, question }),
};
