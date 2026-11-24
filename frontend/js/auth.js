function showAuthAlert(message, type = "error") {
  const el = document.getElementById("auth-alert");
  el.textContent = message;
  el.className = `alert ${type}`;
}

document.getElementById("tab-login").addEventListener("click", () => {
  document.getElementById("tab-login").classList.add("active");
  document.getElementById("tab-register").classList.remove("active");
  document.getElementById("login-form").classList.remove("hidden");
  document.getElementById("register-form").classList.add("hidden");
  document.getElementById("auth-alert").classList.add("hidden");
});

document.getElementById("tab-register").addEventListener("click", () => {
  document.getElementById("tab-register").classList.add("active");
  document.getElementById("tab-login").classList.remove("active");
  document.getElementById("register-form").classList.remove("hidden");
  document.getElementById("login-form").classList.add("hidden");
  document.getElementById("auth-alert").classList.add("hidden");
});

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const email = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-password").value;

  try {
    const tokens = await api.request("/auth/token/", {
      method: "POST",
      body: JSON.stringify({ email, password })
    }, false);
    api.setTokens(tokens.access, tokens.refresh);
    await initApp();
  } catch (err) {
    showAuthAlert(err.message, "error");
  }
});

document.getElementById("register-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = document.getElementById("reg-username").value.trim();
  const email = document.getElementById("reg-email").value.trim();
  const password = document.getElementById("reg-password").value;

  try {
    await api.request("/auth/register/", {
      method: "POST",
      body: JSON.stringify({ username, email, password })
    }, false);
    showAuthAlert("Usuario registrado en BuildCorp. Ahora inicia sesión.", "success");
    document.getElementById("tab-login").click();
    document.getElementById("login-email").value = email;
  } catch (err) {
    showAuthAlert(err.message, "error");
  }
});

document.getElementById("logout-btn").addEventListener("click", () => {
  api.clearTokens();
  document.getElementById("app-view").classList.add("hidden");
  document.getElementById("auth-view").classList.remove("hidden");
});
