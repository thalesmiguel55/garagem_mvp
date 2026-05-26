const card = document.getElementById("card");
const msg = document.getElementById("msg");
const subtitle = document.getElementById("subtitle");

function el(tag, attrs = {}, children = []) {
  const e = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => {
    if (k === "class") e.className = v;
    else if (k === "text") e.textContent = v;
    else e.setAttribute(k, v);
  });
  children.forEach((c) => e.appendChild(c));
  return e;
}

function showMessage(text, type = "") {
  msg.className = `msg ${type}`;
  msg.textContent = typeof text === "string" ? text : formatApiError({ detail: text });
}

function formatApiError(data, fallback = "Erro ao enviar.") {
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

async function parseApiResponse(res) {
  const text = await res.text();
  if (!text) return {};

  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

async function loadContext() {
  showMessage("");
  card.innerHTML = "Carregando...";

  const r = await fetch("/api/context");
  const ctx = await r.json();

  renderHome(ctx);
}

function renderHome(ctx) {
  card.innerHTML = "";
  const plates = ctx.plates || [];
  const openAssignments = ctx.openAssignments || [];

  const anyAvailable = plates.some((p) => p.status === "AVAILABLE");
  const anyInUse = openAssignments.length > 0;

  subtitle.textContent =
    "Retirada: escolha uma placa disponível. Placa em uso fica bloqueada. " +
    "Devolução: escolha a placa em uso e finalize.";

  if (anyAvailable) {
    card.appendChild(renderCheckout(plates));
  } else {
    const warn = el("div", { class: "info" });
    warn.innerHTML = "<b>Retirada:</b> nenhuma placa disponível no momento.";
    card.appendChild(warn);
  }

  if (anyInUse) {
    card.appendChild(el("div", { style: "height:12px" }));
    card.appendChild(renderCheckin(openAssignments));
  } else {
    const info = el("div", { class: "info" });
    info.innerHTML = "<b>Devolução:</b> nenhum veículo em uso agora.";
    card.appendChild(info);
  }
}

function renderCheckout(plates) {
  const wrap = el("div", { class: "card" });

  const title = el("h3", { text: "RETIRADA" });
  title.style.margin = "0 0 8px";
  wrap.appendChild(title);

  const form = el("form");

  // Placa (com bloqueio por status)
  form.appendChild(el("label", { text: "Selecione a placa" }));
  const plateWrap = el("div", { class: "row" });

  const plateHidden = el("input", { type: "hidden", name: "vehicle_plate", value: "" });
  form.appendChild(plateHidden);

  const details = el("div");
  details.style.display = "none";

  plates.forEach((pobj) => {
    const p = pobj.plate;
    const inUse = pobj.status === "IN_USE";
    const text = inUse ? `${p} (EM USO)` : p;

    const b = el("button", { type: "button", class: "chip", text });

    if (inUse) {
      b.disabled = true;
      b.style.opacity = "0.55";
      b.style.cursor = "not-allowed";
      b.title = `Em uso por ${pobj.openAssignment?.checkoutUser || "alguém"} desde ${pobj.openAssignment?.checkoutAt || ""}`;
    }

    b.addEventListener("click", () => {
      if (b.disabled) return;
      [...plateWrap.querySelectorAll(".chip")].forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      plateHidden.value = p;
      details.style.display = "block";
    });

    plateWrap.appendChild(b);
  });

  form.appendChild(plateWrap);

  // Funcionário (obrigatório)
  details.appendChild(el("label", { text: "Funcionário (obrigatório)" }));
  const user = el("input", {
    name: "user",
    placeholder: "Nome ou matrícula",
    required: "required",
  });
  details.appendChild(user);

  // Selfie obrigatória
  details.appendChild(el("label", { text: "Selfie obrigatória" }));
  const selfieInput = el("input", {
    type: "file",
    accept: "image/*",
    capture: "user",
    name: "selfie",
  });
  details.appendChild(selfieInput);

  // Checklist SIM / NÃO + foto se NÃO
  details.appendChild(
    el("label", { text: "Checklist (SIM / NÃO) - se marcar NÃO, enviar foto do problema" })
  );

  const checklistItems = [
    { key: "retrovisores", label: "Retrovisores" },
    { key: "pneus", label: "Pneus" },
    { key: "farois", label: "Faróis" },
    { key: "lataria", label: "Lataria" },
  ];

  const checklistBox = el("div", { class: "checklist" });
  const itemState = {};

  checklistItems.forEach((it) => {
    const row = el("div", { class: "checkline" });

    const left = el("div", { text: it.label });
    left.style.minWidth = "120px";
    left.style.fontWeight = "700";

    const right = el("div", {});

    const radios = el("div", { class: "row" });
    const yesId = `chk_${it.key}_yes`;
    const noId = `chk_${it.key}_no`;

    const yes = el("input", { type: "radio", name: `chk_${it.key}`, id: yesId, value: "yes" });
    const yesLb = el("label", { for: yesId, text: "Sim" });
    const no = el("input", { type: "radio", name: `chk_${it.key}`, id: noId, value: "no" });
    const noLb = el("label", { for: noId, text: "Não" });

    yes.checked = true;

    radios.appendChild(yes); radios.appendChild(yesLb);
    radios.appendChild(no);  radios.appendChild(noLb);

    const issueWrap = el("div", { class: "photoSlot" });
    issueWrap.style.marginTop = "8px";
    issueWrap.style.display = "none";
    issueWrap.appendChild(el("div", { class: "slotTitle", text: `Foto do problema (${it.label})` }));

    const issueInput = el("input", {
      type: "file",
      accept: "image/*",
      capture: "environment",
      name: `issue_${it.key}`,
    });
    issueWrap.appendChild(issueInput);

    function sync() {
      issueWrap.style.display = no.checked ? "block" : "none";
      if (!no.checked) issueInput.value = "";
    }
    yes.addEventListener("change", sync);
    no.addEventListener("change", sync);

    right.appendChild(radios);
    right.appendChild(issueWrap);

    row.appendChild(left);
    row.appendChild(right);

    checklistBox.appendChild(row);
    itemState[it.key] = { noRadio: no, issueInput };
  });

  details.appendChild(checklistBox);

  // Fotos obrigatórias do carro na retirada
  details.appendChild(el("label", { text: "4 fotos obrigatórias do carro" }));
  const slots = [
    ["front", "Frente"],
    ["rear", "Trás"],
    ["left", "Lado esquerdo"],
    ["right", "Lado direito"],
  ];

  const photosBox = el("div", { class: "photos" });
  const fileInputs = {};

  slots.forEach(([name, label]) => {
    const box = el("div", { class: "photoSlot" });
    box.appendChild(el("div", { class: "slotTitle", text: label }));
    const input = el("input", { type: "file", accept: "image/*", capture: "environment", name });
    fileInputs[name] = input;
    box.appendChild(input);
    photosBox.appendChild(box);
  });

  details.appendChild(photosBox);

  const btn = el("button", { type: "submit", class: "primary", text: "Enviar e Liberar" });
  details.appendChild(btn);
  form.appendChild(details);

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    showMessage("");

    if (!user.value || !user.value.trim()) return showMessage("Informe o nome do funcionário.", "err");
    if (!plateHidden.value) return showMessage("Escolha uma placa disponível.", "err");

    btn.disabled = true;
    btn.textContent = "Liberando...";

    try {
      const releaseFd = new FormData();
      releaseFd.append("vehicle_plate", plateHidden.value);
      const releaseRes = await fetch("/api/liberar-caixa", { method: "POST", body: releaseFd });
      const releaseData = await parseApiResponse(releaseRes);
      if (!releaseRes.ok) throw new Error(formatApiError(releaseData));

      btn.textContent = "Validando...";

      if (!selfieInput.files || selfieInput.files.length === 0) {
        throw new Error("Tire uma selfie.");
      }

      for (const key of Object.keys(fileInputs)) {
        if (!fileInputs[key].files || fileInputs[key].files.length === 0) {
          throw new Error(`Falta a foto do carro: ${key}`);
        }
      }

      const answers = {};
      for (const it of checklistItems) {
        const st = itemState[it.key];
        const isNo = st.noRadio.checked;
        answers[it.key] = isNo ? "no" : "yes";

        if (isNo && (!st.issueInput.files || st.issueInput.files.length === 0)) {
          throw new Error(`Você marcou NÃO em "${it.label}". Envie a foto do problema.`);
        }
      }

      btn.textContent = "Enviando...";

      const fd = new FormData();
      fd.append("vehicle_plate", plateHidden.value);
      fd.append("user", user.value.trim());
      fd.append("answers_json", JSON.stringify(answers));
      fd.append("box_released", "true");

      Object.entries(fileInputs).forEach(([k, input]) => fd.append(k, input.files[0]));
      fd.append("selfie", selfieInput.files[0]);

      for (const it of checklistItems) {
        const st = itemState[it.key];
        if (st.noRadio.checked) fd.append(`issue_${it.key}`, st.issueInput.files[0]);
      }

      const res = await fetch("/api/checkout", { method: "POST", body: fd });
      const data = await parseApiResponse(res);
      if (!res.ok) throw new Error(formatApiError(data));

      showMessage(data.message || "OK!", "ok");
      await loadContext();
    } catch (e) {
      showMessage(e.message || e, "err");
    } finally {
      btn.disabled = false;
      btn.textContent = "Enviar e Liberar";
    }
  });

  wrap.appendChild(form);
  return wrap;
}

function renderCheckin(openAssignments) {
  const wrap = el("div", { class: "card" });

  const title = el("h3", { text: "DEVOLUÇÃO" });
  title.style.margin = "0 0 8px";
  wrap.appendChild(title);

  wrap.appendChild(el("div", { class: "muted", text: "Escolha qual placa devolver:" }));

  const pick = el("div", { class: "row" });
  wrap.appendChild(pick);

  let selected = openAssignments[0];

  const details = el("div", { class: "info" });
  wrap.appendChild(details);

  function renderDetails() {
    details.innerHTML = `
      <b>Placa:</b> ${selected.vehiclePlate}<br/>
      <b>Retirado por:</b> ${selected.checkoutUser || "(não informado)"}<br/>
      <b>Em:</b> ${selected.checkoutAt}
    `;
  }

  openAssignments.forEach((a, idx) => {
    const b = el("button", { type: "button", class: "chip", text: a.vehiclePlate });
    b.addEventListener("click", () => {
      [...pick.querySelectorAll(".chip")].forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      selected = a;
      renderDetails();
    });
    pick.appendChild(b);

    if (idx === 0) b.classList.add("active");
  });

  renderDetails();

  const form = el("form");

  form.appendChild(el("label", { text: "Funcionário devolvendo (obrigatório)" }));
  const user = el("input", { name: "user", placeholder: "Nome ou matrícula", required: "required" });
  form.appendChild(user);

  form.appendChild(el("label", { text: "Checklist devolução" }));
  const km = el("input", { name: "km_final", placeholder: "KM final (opcional)", inputmode: "numeric" });
  const obs = el("textarea", { name: "obs", placeholder: "Observações / avarias" });
  form.appendChild(km);
  form.appendChild(obs);

  form.appendChild(el("label", { text: "Foto obrigatória na devolução" }));
  const interiorBox = el("div", { class: "photos" });
  const interiorSlot = el("div", { class: "photoSlot" });
  interiorSlot.appendChild(el("div", { class: "slotTitle", text: "Interior" }));
  const interiorInput = el("input", {
    type: "file",
    accept: "image/*",
    capture: "environment",
    name: "interior",
  });
  interiorSlot.appendChild(interiorInput);
  interiorBox.appendChild(interiorSlot);
  form.appendChild(interiorBox);

  const btn = el("button", { type: "submit", class: "primary", text: "Confirmar devolução" });
  form.appendChild(btn);

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    showMessage("");

    if (!user.value || !user.value.trim()) {
      return showMessage("Informe o nome do funcionário que está devolvendo.", "err");
    }
    if (!interiorInput.files || interiorInput.files.length === 0) {
      return showMessage("Tire a foto do interior do carro.", "err");
    }

    const answers = { km_final: km.value || "", obs: obs.value || "" };

    const fd = new FormData();
    fd.append("assignment_id", selected.id);
    fd.append("user", user.value.trim());
    fd.append("answers_json", JSON.stringify(answers));
    fd.append("interior", interiorInput.files[0]);

    btn.disabled = true;
    btn.textContent = "Enviando...";

    try {
      const res = await fetch("/api/checkin", { method: "POST", body: fd });
      const data = await parseApiResponse(res);
      if (!res.ok) throw new Error(formatApiError(data));

      showMessage(data.message || "OK!", "ok");
      await loadContext();
    } catch (e) {
      showMessage(e.message || e, "err");
    } finally {
      btn.disabled = false;
      btn.textContent = "Confirmar devolução";
    }
  });

  wrap.appendChild(form);
  return wrap;
}

loadContext();
