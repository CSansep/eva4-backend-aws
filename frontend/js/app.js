let state = { workspaces: [], projects: [], tasks: [], audits: [] };

function showGlobalAlert(msg, type = "success") {
  const el = document.getElementById("global-alert");
  el.textContent = msg;
  el.className = `alert ${type}`;
  setTimeout(() => el.classList.add("hidden"), 4000);
}

// Navegación lateral
document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("section-title").textContent = btn.textContent;

    document.querySelectorAll(".content-section").forEach((s) => s.classList.add("hidden"));
    document.getElementById(`sec-${btn.dataset.section}`).classList.remove("hidden");
  });
});

async function loadAllData() {
  try {
    const [wsRes, projRes, taskRes, auditRes] = await Promise.all([
      api.request("/workspaces/"),
      api.request("/projects/"),
      api.request("/tasks/"),
      api.request("/audit-logs/").catch(() => [])
    ]);

    state.workspaces = api.unwrapList(wsRes);
    state.projects = api.unwrapList(projRes);
    state.tasks = api.unwrapList(taskRes);
    state.audits = api.unwrapList(auditRes);

    renderDashboard();
    renderWorkspaces();
    renderProjects();
    renderTasks();
    renderAuditLogs();
  } catch (err) {
    showGlobalAlert("Error sincronizando con AWS: " + err.message, "error");
  }
}

function renderDashboard() {
  document.getElementById("kpi-workspaces").textContent = state.workspaces.length;
  document.getElementById("kpi-projects").textContent = state.projects.length;
  document.getElementById("kpi-pending").textContent = state.tasks.filter(t => t.status !== "COMPLETED").length;
  document.getElementById("kpi-completed").textContent = state.tasks.filter(t => t.status === "COMPLETED").length;

  const container = document.getElementById("recent-tasks-list");
  container.innerHTML = state.tasks.slice(0, 5).map(t => `
    <div class="task-row">
      <div>
        <strong>${t.title}</strong>
        <p style="font-size:0.82rem;color:#94a3b8;">Estado: ${t.status}</p>
      </div>
      <span class="badge badge-${t.priority}">${t.priority}</span>
    </div>
  `).join("") || "<p style='color:#94a3b8'>No hay tareas de obra registradas aún.</p>";
}

function renderWorkspaces() {
  const select = document.getElementById("proj-workspace");
  select.innerHTML = `<option value="">-- Sin área asignada --</option>` +
    state.workspaces.map(w => `<option value="${w.id}">${w.name}</option>`).join("");

  const list = document.getElementById("workspaces-list");
  list.innerHTML = state.workspaces.map(w => `
    <div class="item-card">
      <div>
        <h4>${w.name}</h4>
        <p>Slug: ${w.slug}</p>
        <p>${w.description || "Sin descripción"}</p>
      </div>
      <button class="btn btn-danger btn-sm" onclick="deleteEntity('/workspaces/${w.id}/')">Eliminar</button>
    </div>
  `).join("") || "<p style='color:#94a3b8'>Sin áreas creadas.</p>";
}

function renderProjects() {
  const select = document.getElementById("task-project");
  select.innerHTML = `<option value="">-- Seleccionar Proyecto --</option>` +
    state.projects.map(p => `<option value="${p.id}">${p.name}</option>`).join("");

  const list = document.getElementById("projects-list");
  list.innerHTML = state.projects.map(p => `
    <div class="item-card">
      <div>
        <h4>${p.name}</h4>
        <p>${p.description || "Obra en ejecución"}</p>
      </div>
      <button class="btn btn-danger btn-sm" onclick="deleteEntity('/projects/${p.id}/')">Eliminar</button>
    </div>
  `).join("") || "<p style='color:#94a3b8'>Sin proyectos registrados.</p>";
}

function renderTasks() {
  const list = document.getElementById("tasks-list");
  list.innerHTML = state.tasks.map(t => `
    <div class="task-row">
      <div>
        <strong>${t.title}</strong>
        <p style="font-size:0.84rem;color:#94a3b8;">${t.description || "Sin detalles"}</p>
        ${t.attachment ? `<a href="${t.attachment}" target="_blank" style="color:#f59e0b;font-size:0.8rem;">Ver plano adjunto (S3)</a>` : ""}
      </div>
      <div style="display:flex;gap:0.5rem;align-items:center;">
        <span class="badge badge-${t.priority}">${t.priority}</span>
        <select onchange="updateTaskStatus('${t.id}', this.value)" style="padding:0.35rem;font-size:0.8rem;">
          <option value="PENDING" ${t.status === "PENDING" ? "selected" : ""}>Pendiente</option>
          <option value="IN_PROGRESS" ${t.status === "IN_PROGRESS" ? "selected" : ""}>En Progreso</option>
          <option value="COMPLETED" ${t.status === "COMPLETED" ? "selected" : ""}>Completada</option>
        </select>
        <button class="btn btn-danger btn-sm" onclick="deleteEntity('/tasks/${t.id}/')">X</button>
      </div>
    </div>
  `).join("") || "<p style='color:#94a3b8'>No hay tareas asignadas.</p>";
}

function renderAuditLogs() {
  const tbody = document.getElementById("audit-tbody");
  tbody.innerHTML = state.audits.map(a => `
    <tr>
      <td>${new Date(a.timestamp).toLocaleString()}</td>
      <td><strong>${a.action}</strong></td>
      <td>${a.entity_name}</td>
      <td>${a.ip_address || "Sistema"}</td>
    </tr>
  `).join("") || "<tr><td colspan='4'>Sin registros de auditoría.</td></tr>";
}

// Formularios de creación
document.getElementById("workspace-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api.request("/workspaces/", {
      method: "POST",
      body: JSON.stringify({
        name: document.getElementById("ws-name").value.trim(),
        slug: document.getElementById("ws-slug").value.trim(),
        description: document.getElementById("ws-desc").value.trim()
      })
    });
    e.target.reset();
    showGlobalAlert("Área operativa creada correctamente.");
    loadAllData();
  } catch (err) {
    showGlobalAlert(err.message, "error");
  }
});

document.getElementById("project-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const workspace = document.getElementById("proj-workspace").value || null;
  try {
    await api.request("/projects/", {
      method: "POST",
      body: JSON.stringify({
        name: document.getElementById("proj-name").value.trim(),
        description: document.getElementById("proj-desc").value.trim(),
        workspace
      })
    });
    e.target.reset();
    showGlobalAlert("Proyecto de obra registrado.");
    loadAllData();
  } catch (err) {
    showGlobalAlert(err.message, "error");
  }
});

document.getElementById("task-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const formData = new FormData();
  formData.append("title", document.getElementById("task-title").value.trim());
  formData.append("project", document.getElementById("task-project").value);
  formData.append("priority", document.getElementById("task-priority").value);
  formData.append("status", document.getElementById("task-status").value);
  formData.append("description", document.getElementById("task-desc").value.trim());

  const due = document.getElementById("task-due").value;
  if (due) formData.append("due_date", new Date(due).toISOString());

  const fileInput = document.getElementById("task-file");
  if (fileInput.files.length > 0) {
    formData.append("attachment", fileInput.files[0]);
  }

  try {
    await api.request("/tasks/", { method: "POST", body: formData });
    e.target.reset();
    showGlobalAlert("Tarea de obra guardada y sincronizada.");
    loadAllData();
  } catch (err) {
    showGlobalAlert(err.message, "error");
  }
});

async function updateTaskStatus(id, status) {
  try {
    await api.request(`/tasks/${id}/`, {
      method: "PATCH",
      body: JSON.stringify({ status })
    });
    showGlobalAlert("Estado de tarea actualizado.");
    loadAllData();
  } catch (err) {
    showGlobalAlert(err.message, "error");
  }
}

async function deleteEntity(endpoint) {
  if (!confirm("¿Confirmas eliminar este registro de BuildCorp?")) return;
  try {
    await api.request(endpoint, { method: "DELETE" });
    showGlobalAlert("Registro eliminado.");
    loadAllData();
  } catch (err) {
    showGlobalAlert(err.message, "error");
  }
}

async function initApp() {
  if (!api.getAccessToken()) return;
  try {
    const user = await api.request("/auth/me/");
    document.getElementById("user-info").textContent = `${user.username} (${user.role}) — ${user.email}`;
    document.getElementById("auth-view").classList.add("hidden");
    document.getElementById("app-view").classList.remove("hidden");
    await loadAllData();
  } catch {
    api.clearTokens();
  }
}

initApp();
