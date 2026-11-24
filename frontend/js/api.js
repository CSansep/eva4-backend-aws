const API_BASE_URL = "http://3.95.25.91/api/v1";

const api = {
  getAccessToken() {
    return localStorage.getItem("buildcorp_access");
  },
  getRefreshToken() {
    return localStorage.getItem("buildcorp_refresh");
  },
  setTokens(access, refresh) {
    localStorage.setItem("buildcorp_access", access);
    if (refresh) localStorage.setItem("buildcorp_refresh", refresh);
  },
  clearTokens() {
    localStorage.removeItem("buildcorp_access");
    localStorage.removeItem("buildcorp_refresh");
  },

  async refreshAccessToken() {
    const refresh = this.getRefreshToken();
    if (!refresh) return false;
    const res = await fetch(`${API_BASE_URL}/auth/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh })
    });
    if (!res.ok) {
      this.clearTokens();
      return false;
    }
    const data = await res.json();
    this.setTokens(data.access, null);
    return true;
  },

  async request(endpoint, options = {}, retry = true) {
    const headers = options.headers || {};
    const token = this.getAccessToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
    if (!(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers
    });

    if (response.status === 401 && retry && this.getRefreshToken()) {
      const refreshed = await this.refreshAccessToken();
      if (refreshed) return this.request(endpoint, options, false);
    }

    if (response.status === 204) return null;

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const msg = data.detail || Object.values(data).flat().join(" ") || "Error en la solicitud";
      throw new Error(msg);
    }
    return data;
  },

  unwrapList(data) {
    return Array.isArray(data) ? data : (data.results || []);
  }
};
