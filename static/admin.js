const loginCard = document.getElementById("loginCard");
const adminCard = document.getElementById("adminCard");
const loginMsg = document.getElementById("loginMsg");
const adminMsg = document.getElementById("adminMsg");

const passwordEl = document.getElementById("password");
const btnLogin = document.getElementById("btnLogin");
const btnReload = document.getElementById("btnReload");
const btnLogout = document.getElementById("btnLogout");

const summaryEl = document.getElementById("summary");
const listEl = document.getElementById("list");
const detailsEl = document.getElementById("details");
const photosEl = document.getElementById("photos");
const recordsView = document.getElementById("recordsView");
const vehiclesView = document.getElementById("vehiclesView");
const adminViewHint = document.getElementById("adminViewHint");
const tabRecords = document.getElementById("tabRecords");
const tabVehicles = document.getElementById("tabVehicles");
const vehicleForm = document.getElementById("vehicleForm");
const vehicleFormTitle = document.getElementById("vehicleFormTitle");
const vehicleIdEl = document.getElementById("vehicleId");
const vehiclePlateEl = document.getElementById("vehiclePlate");
const vehicleDescriptionEl = document.getElementById("vehicleDescription");
const vehicleBoxEl = document.getElementById("vehicleBox");
const vehiclesListEl = document.getElementById("vehiclesList");
const btnSaveVehicle = document.getElementById("btnSaveVehicle");
const btnCancelVehicle = document.getElementById("btnCancelVehicle");

let selectedId = "";
let currentView = "records";
let vehiclesCache = [];
let editingVehicleId = "";

function setLoginMessage(text, type = "") {
  loginMsg.className = `msg ${type}`;
  loginMsg.textContent = text;
}

function setAdminMessage(text, type = "") {
  adminMsg.className = `msg ${type}`;
  adminMsg.textContent = text;
}

function showLogin() {
  loginCard.style.display = "block";
  adminCard.style.display = "none";
  summaryEl.innerHTML = "";
  listEl.innerHTML = "";
  detailsEl.innerHTML = "";
  photosEl.innerHTML = "";
  vehiclesListEl.innerHTML = "";
  currentView = "records";
  setAdminView("records");
  setAdminMessage("");
}

function showAdmin() {
  loginCard.style.display = "none";
  adminCard.style.display = "block";
  setLoginMessage("");
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (m) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[m]));
}

function formatDate(value) {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return escapeHtml(value);
  return d.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function statusMeta(status) {
  const normalized = String(status || "").toUpperCase();
  if (normalized === "OPEN" || normalized === "IN_USE") return { label: "Em uso", className: "statusOpen" };
  if (normalized === "CLOSED") return { label: "Devolvido", className: "statusClosed" };
  if (normalized === "AVAILABLE") return { label: "Disponível", className: "statusAvailable" };
  if (normalized === "INACTIVE") return { label: "Inativo", className: "statusInactive" };
  return { label: status || "-", className: "" };
}

function formatApiError(data, fallback = "Erro ao processar solicitação.") {
  const detail = data?.detail;

  if (!detail) return fallback;
  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    return detail.map((item) => {
      if (typeof item === "string") return item;
      const loc = Array.isArray(item.loc) ? item.loc.filter((x) => x !== "body").join(".") : "";
      const msgText = item.msg || "Campo inválido";
      return loc ? `${loc}: ${msgText}` : msgText;
    }).join("\n");
  }

  if (typeof detail === "object") {
    return detail.msg || JSON.stringify(detail);
  }

  return String(detail);
}

function yn(value) {
  const s = String(value ?? "").toLowerCase();
  if (!s) return "-";
  if (["yes", "sim", "true"].includes(s)) return "Sim";
  if (["no", "nao", "não", "false"].includes(s)) return "Não";
  return escapeHtml(value);
}

function renderSummary(items) {
  const total = items.length;
  const open = items.filter((it) => String(it.status || "").toUpperCase() === "OPEN").length;
  const closed = items.filter((it) => String(it.status || "").toUpperCase() === "CLOSED").length;
  const last = items[0]?.checkout_at ? formatDate(items[0].checkout_at) : "-";

  summaryEl.innerHTML = `
    <div class="summaryCard">
      <span>Total</span>
      <strong>${total}</strong>
    </div>
    <div class="summaryCard">
      <span>Em uso</span>
      <strong>${open}</strong>
    </div>
    <div class="summaryCard">
      <span>Devolvidos</span>
      <strong>${closed}</strong>
    </div>
    <div class="summaryCard">
      <span>Última retirada</span>
      <strong>${last}</strong>
    </div>
  `;
}

function renderEmptyDetails() {
  detailsEl.innerHTML = `
    <div class="emptyState">
      <strong>Nenhum registro selecionado</strong>
      <span>Escolha uma linha do histórico para ver checklist e fotos.</span>
    </div>
  `;
  photosEl.innerHTML = "";
}

function renderTable(items) {
  if (!items.length) {
    listEl.innerHTML = "<div class='emptyState'><strong>Nenhum registro ainda</strong><span>As retiradas aparecerão aqui.</span></div>";
    return;
  }

  const rows = items.map((it) => {
    const meta = statusMeta(it.status);
    const isSelected = it.id === selectedId ? " selected" : "";

    return `
      <tr data-id="${escapeHtml(it.id)}" class="${isSelected}">
        <td>
          <div class="plateCell">${escapeHtml(it.vehicle_plate)}</div>
        </td>
        <td><span class="statusPill ${meta.className}">${escapeHtml(meta.label)}</span></td>
        <td>
          <div class="personCell">${escapeHtml(it.checkout_user || "-")}</div>
          <small>${formatDate(it.checkout_at)}</small>
        </td>
        <td>
          <div class="personCell">${escapeHtml(it.checkin_user || "-")}</div>
          <small>${formatDate(it.checkin_at)}</small>
        </td>
      </tr>
    `;
  }).join("");

  listEl.innerHTML = `
    <div class="tableWrap">
      <table class="adminTable">
        <thead>
          <tr>
            <th>Placa</th>
            <th>Status</th>
            <th>Retirada</th>
            <th>Devolução</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;

  listEl.querySelectorAll("tr[data-id]").forEach((tr) => {
    tr.addEventListener("click", () => loadDetails(tr.getAttribute("data-id")));
  });
}

function renderChecklist(title, items) {
  return `
    <div class="detailBlock">
      <h4>${escapeHtml(title)}</h4>
      <div class="checkRows">${items.join("")}</div>
    </div>
  `;
}

function formatCheckout(answers = {}) {
  const labels = {
    retrovisores: "Retrovisores",
    pneus: "Pneus",
    farois: "Faróis",
    lataria: "Lataria",
  };

  return Object.entries(labels).map(([key, label]) => {
    const value = yn(answers[key]);
    const issue = value === "Não" ? " issue" : "";
    return `
      <div class="checkRow">
        <span>${label}</span>
        <strong class="${issue}">${value}</strong>
      </div>
    `;
  });
}

function formatCheckin(answers = {}) {
  if (answers.admin_action === "mark_returned") {
    return [
      `<div class="checkRow"><span>Marcado pelo admin</span><strong>${escapeHtml(answers.admin_name || "ADMIN")}</strong></div>`,
      `<div class="checkRow"><span>Data/Hora</span><strong>${formatDate(answers.marked_at)}</strong></div>`,
      `<div class="noteBox">${escapeHtml(answers.note || "Sem observações.").replace(/\n/g, "<br/>")}</div>`,
    ];
  }

  return [
    `<div class="checkRow"><span>KM final</span><strong>${escapeHtml(answers.km_final || "-")}</strong></div>`,
    `<div class="noteBox">${escapeHtml(answers.obs || "Sem observações.").replace(/\n/g, "<br/>")}</div>`,
  ];
}

async function apiFetch(url, opts = {}) {
  opts.credentials = "include";
  const res = await fetch(url, opts);
  let data = {};
  const ct = (res.headers.get("content-type") || "").toLowerCase();

  try {
    data = ct.includes("application/json") ? await res.json() : { detail: await res.text() };
  } catch {
    data = {};
  }

  if (res.status === 401) {
    showLogin();
    throw new Error("Não autenticado. Faça login novamente.");
  }
  if (!res.ok) throw new Error(formatApiError(data, `Erro HTTP ${res.status}`));
  return data;
}

function setAdminView(view) {
  currentView = view;
  const isRecords = view === "records";

  tabRecords.classList.toggle("active", isRecords);
  tabVehicles.classList.toggle("active", !isRecords);
  recordsView.style.display = isRecords ? "block" : "none";
  vehiclesView.style.display = isRecords ? "none" : "block";
  adminViewHint.textContent = isRecords
    ? "Clique em um registro para abrir os detalhes."
    : "Cadastre novos veículos para liberar retirada na página principal.";
}

async function doLogin() {
  setLoginMessage("");
  const password = passwordEl.value || "";
  if (!password.trim()) return setLoginMessage("Digite a senha.", "err");

  btnLogin.disabled = true;
  btnLogin.textContent = "Entrando...";

  try {
    const fd = new FormData();
    fd.append("password", password);
    await apiFetch("/api/admin/login", { method: "POST", body: fd });
    showAdmin();
    setAdminView("records");
    await loadList();
  } catch (e) {
    setLoginMessage(e.message, "err");
  } finally {
    btnLogin.disabled = false;
    btnLogin.textContent = "Entrar";
  }
}

async function loadList() {
  setAdminMessage("");
  listEl.innerHTML = "<div class='loadingLine'>Carregando registros...</div>";
  renderEmptyDetails();

  try {
    const data = await apiFetch("/api/admin/assignments?limit=200");
    const items = data.items || [];
    renderSummary(items);
    renderTable(items);
  } catch (e) {
    summaryEl.innerHTML = "";
    listEl.innerHTML = "<div class='emptyState'><strong>Falha ao carregar</strong><span>Tente atualizar a página.</span></div>";
    setAdminMessage(e.message, "err");
  }
}

function splitVehiclePlate(fullPlate) {
  const value = String(fullPlate || "");
  const slashIndex = value.indexOf("/");
  if (slashIndex === -1) {
    return { plate: value, description: "" };
  }
  return {
    plate: value.slice(0, slashIndex),
    description: value.slice(slashIndex + 1),
  };
}

function setVehicleFormMode(mode, vehicle = null) {
  const isEdit = mode === "edit" && vehicle;

  editingVehicleId = isEdit ? vehicle.id : "";
  vehicleIdEl.value = editingVehicleId;
  vehicleFormTitle.textContent = isEdit ? "Editar carro" : "Cadastrar carro";
  btnSaveVehicle.textContent = isEdit ? "Salvar alterações" : "Cadastrar carro";
  btnCancelVehicle.style.display = isEdit ? "inline-flex" : "none";

  if (isEdit) {
    const parts = splitVehiclePlate(vehicle.plate);
    vehiclePlateEl.value = parts.plate;
    vehicleDescriptionEl.value = parts.description;
    vehicleBoxEl.value = vehicle.caixa ?? "";
    return;
  }

  vehicleForm.reset();
  vehicleIdEl.value = "";
}

function renderVehiclesTable(items) {
  if (!items.length) {
    vehiclesListEl.innerHTML = "<div class='emptyState'><strong>Nenhum carro cadastrado</strong><span>Use o formulário ao lado para adicionar o primeiro veículo.</span></div>";
    return;
  }

  const rows = items.map((vehicle) => {
    const meta = statusMeta(vehicle.status);
    const caixa = vehicle.caixa ? escapeHtml(vehicle.caixa) : "-";
    const isEditing = vehicle.id === editingVehicleId ? " selected" : "";
    const isInactive = Number(vehicle.active) !== 1;
    const isInUse = String(vehicle.status || "").toUpperCase() === "IN_USE";
    const rowClass = `${isEditing}${isInactive ? " rowInactive" : ""}`.trim();

    let actions = "";
    if (isInactive) {
      actions = `<button type="button" class="tableActionBtn" data-activate-vehicle="${escapeHtml(vehicle.id)}">Reativar</button>`;
    } else {
      actions = `
        <button type="button" class="tableActionBtn" data-edit-vehicle="${escapeHtml(vehicle.id)}">Editar</button>
        <button type="button" class="tableActionBtn tableActionBtnDanger" data-deactivate-vehicle="${escapeHtml(vehicle.id)}" ${isInUse ? "disabled title='Finalize a devolução antes de desativar.'" : ""}>Desativar</button>
      `;
    }

    return `
      <tr data-vehicle-id="${escapeHtml(vehicle.id)}" class="${rowClass}">
        <td>
          <div class="plateCell${isInactive ? " plateCellInactive" : ""}">${escapeHtml(vehicle.plate)}</div>
        </td>
        <td><span class="statusPill ${meta.className}">${escapeHtml(meta.label)}</span></td>
        <td>${caixa}</td>
        <td><small>${formatDate(vehicle.created_at)}</small></td>
        <td class="tableActions">${actions}</td>
      </tr>
    `;
  }).join("");

  vehiclesListEl.innerHTML = `
    <div class="tableWrap">
      <table class="adminTable">
        <thead>
          <tr>
            <th>Placa</th>
            <th>Status</th>
            <th>Caixa</th>
            <th>Cadastro</th>
            <th>Ações</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;

  vehiclesListEl.querySelectorAll("[data-edit-vehicle]").forEach((button) => {
    button.addEventListener("click", () => {
      const vehicle = vehiclesCache.find((item) => item.id === button.getAttribute("data-edit-vehicle"));
      if (!vehicle) return;
      setVehicleFormMode("edit", vehicle);
      setAdminMessage("");
      renderVehiclesTable(vehiclesCache);
      vehiclePlateEl.focus();
    });
  });

  vehiclesListEl.querySelectorAll("[data-deactivate-vehicle]").forEach((button) => {
    button.addEventListener("click", () => deactivateVehicle(button.getAttribute("data-deactivate-vehicle")));
  });

  vehiclesListEl.querySelectorAll("[data-activate-vehicle]").forEach((button) => {
    button.addEventListener("click", () => activateVehicle(button.getAttribute("data-activate-vehicle")));
  });
}

async function deactivateVehicle(vehicleId) {
  const vehicle = vehiclesCache.find((item) => item.id === vehicleId);
  if (!vehicle) return;

  const confirmed = window.confirm(`Desativar o veículo ${vehicle.plate}?\n\nEle sairá da página principal, mas o histórico será mantido.`);
  if (!confirmed) return;

  setAdminMessage("");
  try {
    const data = await apiFetch(`/api/admin/vehicles/${vehicleId}`, { method: "DELETE" });
    if (editingVehicleId === vehicleId) setVehicleFormMode("create");
    setAdminMessage(data.message || "Veículo desativado com sucesso.", "ok");
    await loadVehicles();
  } catch (e) {
    setAdminMessage(e.message, "err");
  }
}

async function activateVehicle(vehicleId) {
  setAdminMessage("");
  try {
    const data = await apiFetch(`/api/admin/vehicles/${vehicleId}/activate`, { method: "POST" });
    setAdminMessage(data.message || "Veículo reativado com sucesso.", "ok");
    await loadVehicles();
  } catch (e) {
    setAdminMessage(e.message, "err");
  }
}

async function loadVehicles() {
  setAdminMessage("");
  vehiclesListEl.innerHTML = "<div class='loadingLine'>Carregando carros...</div>";

  try {
    const data = await apiFetch("/api/admin/vehicles");
    vehiclesCache = data.items || [];
    renderVehiclesTable(vehiclesCache);
  } catch (e) {
    vehiclesListEl.innerHTML = "<div class='emptyState'><strong>Falha ao carregar carros</strong><span>Tente atualizar a página.</span></div>";
    setAdminMessage(e.message, "err");
  }
}

async function saveVehicle(ev) {
  ev.preventDefault();
  setAdminMessage("");

  const plate = vehiclePlateEl.value || "";
  const description = vehicleDescriptionEl.value || "";
  const caixa = vehicleBoxEl.value || "";

  if (!plate.trim()) {
    return setAdminMessage("Informe a placa do veículo.", "err");
  }

  const fd = new FormData();
  fd.append("plate", plate.trim());
  fd.append("description", description.trim());
  if (caixa.trim()) fd.append("caixa", caixa.trim());

  const isEdit = Boolean(editingVehicleId);
  btnSaveVehicle.disabled = true;
  btnSaveVehicle.textContent = isEdit ? "Salvando..." : "Cadastrando...";

  try {
    const data = isEdit
      ? await apiFetch(`/api/admin/vehicles/${editingVehicleId}`, { method: "PUT", body: fd })
      : await apiFetch("/api/admin/vehicles", { method: "POST", body: fd });

    setVehicleFormMode("create");
    setAdminMessage(data.message || (isEdit ? "Carro atualizado com sucesso." : "Carro cadastrado com sucesso."), "ok");
    await loadVehicles();
  } catch (e) {
    setAdminMessage(e.message, "err");
  } finally {
    btnSaveVehicle.disabled = false;
    btnSaveVehicle.textContent = editingVehicleId ? "Salvar alterações" : "Cadastrar carro";
  }
}

async function reloadCurrentView() {
  if (currentView === "vehicles") {
    await loadVehicles();
    return;
  }
  await loadList();
}

async function loadDetails(id) {
  selectedId = id;
  setAdminMessage("");
  detailsEl.innerHTML = "<div class='loadingLine'>Carregando detalhes...</div>";
  photosEl.innerHTML = "";

  listEl.querySelectorAll("tr[data-id]").forEach((tr) => {
    tr.classList.toggle("selected", tr.getAttribute("data-id") === id);
  });

  try {
    const data = await apiFetch(`/api/admin/assignment/${id}`);
    const a = data.assignment || {};
    const photos = data.photos || [];
    const meta = statusMeta(a.status);

    detailsEl.innerHTML = `
      <div class="detailHero">
        <div>
          <span class="eyebrow">Placa</span>
          <strong>${escapeHtml(a.vehicle_plate)}</strong>
        </div>
        <span class="statusPill ${meta.className}">${escapeHtml(meta.label)}</span>
      </div>

      <div class="timeline">
        <div>
          <span>Retirada</span>
          <strong>${escapeHtml(a.checkout_user || "-")}</strong>
          <small>${formatDate(a.checkout_at)}</small>
        </div>
        <div>
          <span>Devolução</span>
          <strong>${escapeHtml(a.checkin_user || "-")}</strong>
          <small>${formatDate(a.checkin_at)}</small>
        </div>
      </div>

      ${renderChecklist("Checklist de retirada", formatCheckout(a.checkout_answers_obj))}
      ${renderChecklist("Checklist de devolução", formatCheckin(a.checkin_answers_obj))}
    `;

    if (!photos.length) {
      photosEl.innerHTML = "<div class='emptyState compact'><strong>Nenhuma foto salva</strong></div>";
      return;
    }

    photosEl.innerHTML = photos.map((p) => `
      <a class="photoCard" href="${p.url}" target="_blank">
        <img src="${p.url}?v=${Date.now()}" alt="${escapeHtml(p.slot)}" loading="lazy" />
        <span>${escapeHtml(p.phase)} · ${escapeHtml(p.slot)}</span>
      </a>
    `).join("");
  } catch (e) {
    detailsEl.innerHTML = "<div class='emptyState'><strong>Falha ao carregar detalhes</strong><span>Tente abrir o registro novamente.</span></div>";
    setAdminMessage(e.message, "err");
  }
}

async function doLogout() {
  try {
    await apiFetch("/api/admin/logout", { method: "POST" });
  } catch {}
  showLogin();
}

btnLogin.addEventListener("click", doLogin);
btnReload.addEventListener("click", reloadCurrentView);
btnLogout.addEventListener("click", doLogout);
vehicleForm.addEventListener("submit", saveVehicle);
btnCancelVehicle.addEventListener("click", () => {
  setVehicleFormMode("create");
  setAdminMessage("");
  renderVehiclesTable(vehiclesCache);
});

tabRecords.addEventListener("click", async () => {
  setAdminView("records");
  setAdminMessage("");
  await loadList();
});

tabVehicles.addEventListener("click", async () => {
  setAdminView("vehicles");
  setAdminMessage("");
  setVehicleFormMode("create");
  await loadVehicles();
});

passwordEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter") doLogin();
});

showLogin();
