const $ = (sel) => document.querySelector(sel);

function badge(tone, label) {
  return `<span class="badge badge-${tone || "neutral"}">${label}</span>`;
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const message = body?.error?.message || `Error ${res.status}`;
    const err = new Error(message);
    err.body = body;
    throw err;
  }
  return body;
}

// ---------- Health ----------
async function checkHealth() {
  const el = $("#health");
  try {
    const data = await api("/api/health");
    el.textContent = data.tenant_account_configured
      ? "conectado · tenant configurado"
      : "servidor OK · falta MONO_TENANT_ACCOUNT_ID en .env";
    el.className = "health " + (data.tenant_account_configured ? "ok" : "error");
  } catch (e) {
    el.textContent = "sin conexión con el backend";
    el.className = "health error";
  }
}

// ---------- Recaudos ----------
async function crearRecaudo(evt) {
  evt.preventDefault();
  const form = evt.target;
  const fd = new FormData(form);
  try {
    await api("/api/recaudos", {
      method: "POST",
      body: JSON.stringify({
        nickname: fd.get("nickname") || undefined,
        reference: fd.get("reference") || undefined,
        usage_mode: fd.get("usage_mode"),
        amount_pesos: fd.get("amount_pesos") || undefined,
      }),
    });
    form.reset();
    await cargarRecaudos();
  } catch (e) {
    alert("No se pudo crear el recaudo: " + e.message);
  }
}

async function cargarRecaudos() {
  const tbody = $("#tabla-recaudos");
  try {
    const { items } = await api("/api/recaudos");
    if (!items.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="empty">Sin recaudos aún</td></tr>`;
      return;
    }
    tbody.innerHTML = items
      .map(
        (c) => `<tr>
          <td>${c.id}</td>
          <td>${c.nickname || "-"}</td>
          <td>${badge(c.state_tone, c.state_label)}</td>
          <td>${c.paid_amount}</td>
          <td>${c.total_maximum_amount}</td>
        </tr>`
      )
      .join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="5" class="empty">Error al listar: ${e.message}</td></tr>`;
  }
}

async function buscarRecaudo() {
  const id = $("#input-recaudo-id").value.trim();
  const box = $("#recaudo-detalle");
  if (!id) return;
  try {
    const c = await api(`/api/recaudos/${encodeURIComponent(id)}`);
    box.classList.remove("hidden");
    box.textContent = JSON.stringify(c, null, 2);
  } catch (e) {
    box.classList.remove("hidden");
    box.textContent = "Error: " + e.message;
  }
}

// ---------- Transferencias ----------
async function enviarTransferencia(evt) {
  evt.preventDefault();
  const form = evt.target;
  const fd = new FormData(form);
  try {
    await api("/api/transferencias", {
      method: "POST",
      body: JSON.stringify({
        key_value: fd.get("key_value"),
        amount_pesos: fd.get("amount_pesos"),
        description: fd.get("description") || undefined,
      }),
    });
    form.reset();
    await cargarTransferencias();
  } catch (e) {
    alert("No se pudo crear la transferencia: " + e.message);
  }
}

async function cargarTransferencias() {
  const tbody = $("#tabla-transferencias");
  try {
    const { items } = await api("/api/transferencias");
    if (!items.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="empty">Sin transferencias aún</td></tr>`;
      return;
    }
    tbody.innerHTML = items
      .map(
        (t) => `<tr>
          <td>${t.id}</td>
          <td>${t.target?.key_value || "-"}</td>
          <td>${t.amount}</td>
          <td>${badge(t.state_tone, t.state_label)}</td>
          <td>${t.is_final ? "Sí" : "No, en curso"}</td>
        </tr>`
      )
      .join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="5" class="empty">Error al listar: ${e.message}</td></tr>`;
  }
}

async function buscarTransferencia() {
  const id = $("#input-transferencia-id").value.trim();
  const box = $("#transferencia-detalle");
  if (!id) return;
  try {
    const t = await api(`/api/transferencias/${encodeURIComponent(id)}`);
    box.classList.remove("hidden");
    box.textContent = JSON.stringify(t, null, 2);
  } catch (e) {
    box.classList.remove("hidden");
    box.textContent = "Error: " + e.message;
  }
}

// ---------- Webhook events ----------
async function cargarEventos() {
  const ul = $("#lista-eventos");
  try {
    const { events } = await api("/api/webhooks/events");
    if (!events.length) {
      ul.innerHTML = `<li class="empty">Sin eventos recibidos aún</li>`;
      return;
    }
    ul.innerHTML = events
      .slice(0, 20)
      .map((e) => `<li>[${e.receivedAt}] ${e.type}</li>`)
      .join("");
  } catch (e) {
    ul.innerHTML = `<li class="empty">Error: ${e.message}</li>`;
  }
}

// ---------- wiring ----------
$("#form-recaudo").addEventListener("submit", crearRecaudo);
$("#form-transferencia").addEventListener("submit", enviarTransferencia);
$("#btn-refresh-recaudos").addEventListener("click", cargarRecaudos);
$("#btn-refresh-transferencias").addEventListener("click", cargarTransferencias);
$("#btn-refresh-eventos").addEventListener("click", cargarEventos);
$("#btn-buscar-recaudo").addEventListener("click", buscarRecaudo);
$("#btn-buscar-transferencia").addEventListener("click", buscarTransferencia);

checkHealth();
cargarRecaudos();
cargarTransferencias();
cargarEventos();
setInterval(cargarEventos, 8000);
