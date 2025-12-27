(() => {
  const $ = (id) => document.getElementById(id);

  const tbody = $("participantsTbody");
  const statusEl = $("adminStatus");

  const pwModal = $("pwModal");
  const requirePassword = pwModal?.dataset?.require === "1";

  let unlocked = !requirePassword;
  let state = null;

  function escapeHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }

  function slugify(name) {
    return (name || "")
      .toLowerCase()
      .trim()
      .replace(/\s+/g, "-")
      .replace(/[^a-z0-9\-]/g, "");
  }

  function showStatus(msg) {
    if (statusEl) statusEl.textContent = msg || "";
  }

  function renderTable(participants) {
    if (!tbody) return;
    tbody.innerHTML = participants.map((p, idx) => {
      return `<tr data-idx="${idx}">
        <td><input class="input input-sm" value="${escapeHtml(p.name || "")}" data-field="name" placeholder="Name" /></td>
        <td><input class="input input-sm" value="${escapeHtml(p.dessert || "")}" data-field="dessert" placeholder="Dessert name" /></td>
        <td class="col-tight"><button class="btn btn-ghost btn-sm" data-action="remove" type="button">🗑️</button></td>
      </tr>`;
    }).join("");
  }

  function readTable() {
    const rows = [...tbody.querySelectorAll("tr")];
    const participants = rows.map((tr) => {
      const name = tr.querySelector('[data-field="name"]').value.trim();
      const dessert = tr.querySelector('[data-field="dessert"]').value.trim();
      const id = slugify(name) || `p-${Math.random().toString(16).slice(2,8)}`;
      return { id, name, dessert: dessert || "—" };
    }).filter(p => p.name);
    return participants;
  }

  async function fetchState() {
    const res = await fetch("/api/state", { cache: "no-store" });
    return await res.json();
  }

  async function saveParticipants(participants) {
    const res = await fetch("/api/participants", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(participants),
    });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error("Save failed");
  }

  function openModal() {
    if (pwModal) pwModal.classList.add("open");
  }
  function closeModal() {
    if (pwModal) pwModal.classList.remove("open");
  }

  async function unlock() {
    const pw = ($("adminPasswordInput")?.value || "").trim();
    $("pwStatus").textContent = "";
    const res = await fetch("/api/admin/auth", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ password: pw }),
    });
    const data = await res.json();
    if (data.success) {
      unlocked = true;
      closeModal();
      await initAdmin();
    } else {
      $("pwStatus").textContent = "Wrong password.";
    }
  }

  async function initAdmin() {
    state = await fetchState();
    renderTable(state.participants || []);
    showStatus("");
  }

  document.addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    const action = btn.dataset.action;

    if (btn.id === "addRowBtn") {
      const participants = readTable();
      participants.push({ id: `p-${Date.now()}`, name: "", dessert: "—" });
      renderTable(participants);
      showStatus("");
      return;
    }

    if (btn.id === "saveParticipantsBtn") {
      (async () => {
        try {
          const participants = readTable();
          await saveParticipants(participants);
          showStatus("Saved ✅");
        } catch (err) {
          showStatus("Error saving. Try again.");
        }
      })();
      return;
    }

    if (action === "remove") {
      const tr = btn.closest("tr");
      if (!tr) return;
      tr.remove();
      showStatus("");
    }

    if (btn.id === "adminPasswordBtn") {
      unlock();
    }
  });

  document.addEventListener("DOMContentLoaded", async () => {
    if (requirePassword) openModal();
    if (!requirePassword) await initAdmin();
  });
})();
