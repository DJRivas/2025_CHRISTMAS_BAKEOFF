(() => {
  const $ = (id) => document.getElementById(id);

  const tasteRange = $("tasteRange");
  const presentationRange = $("presentationRange");
  const spiritRange = $("spiritRange");

  const tasteValue = $("tasteValue");
  const presentationValue = $("presentationValue");
  const spiritValue = $("spiritValue");

  const tasteEmoji = $("tasteEmoji");
  const presentationEmoji = $("presentationEmoji");
  const spiritEmoji = $("spiritEmoji");

  const participantSelect = $("participantSelect");
  const leaderboardEl = $("leaderboard");
  const rosterEl = $("roster");
  const activityEl = $("activity");
  const submitStatus = $("submitStatus");

  const EMOJI = {
    taste: ["🤢","😖","😕","😐","🙂","😋","🤤","😍","🎉","🏆"],
    presentation: ["🫥","😬","😕","😐","🙂","✨","🎀","🎁","🌟","👑"],
    spirit: ["🥶","😐","🙂","🎄","🕯️","🎅","🤶","🦌","❄️","🎆"],
  };

  function scoreEmoji(kind, score) {
    const idx = Math.min(10, Math.max(1, Number(score || 1))) - 1;
    return (EMOJI[kind] && EMOJI[kind][idx]) || "🙂";
  }

  function setSliderUI() {
    if (tasteRange) {
      tasteValue.textContent = tasteRange.value;
      tasteEmoji.textContent = scoreEmoji("taste", tasteRange.value);
    }
    if (presentationRange) {
      presentationValue.textContent = presentationRange.value;
      presentationEmoji.textContent = scoreEmoji("presentation", presentationRange.value);
    }
    if (spiritRange) {
      spiritValue.textContent = spiritRange.value;
      spiritEmoji.textContent = scoreEmoji("spirit", spiritRange.value);
    }
  }

  ["input","change"].forEach(evt => {
    tasteRange?.addEventListener(evt, setSliderUI);
    presentationRange?.addEventListener(evt, setSliderUI);
    spiritRange?.addEventListener(evt, setSliderUI);
  });

  function fmt(n) {
    const x = Number(n);
    if (!Number.isFinite(x)) return "0.00";
    return x.toFixed(2);
  }

  function participantLabel(p) {
    const d = (p.dessert || "—").trim();
    return d && d !== "—" ? `${p.name} — ${d}` : p.name;
  }

  function renderRoster(participants) {
    if (!rosterEl) return;
    rosterEl.innerHTML = participants.map(p => {
      const dessert = (p.dessert || "—").trim();
      return `<div class="roster-item">
        <div class="roster-name">${escapeHtml(p.name)}</div>
        <div class="roster-dessert">${escapeHtml(dessert)}</div>
      </div>`;
    }).join("");
  }

  function renderActivity(participantsById, scores) {
    if (!activityEl) return;
    const recent = [...scores].slice(-10).reverse();
    activityEl.innerHTML = recent.map(s => {
      const p = participantsById[s.participantId];
      const who = p ? participantLabel(p) : s.participantId;
      const line = `${escapeHtml(s.judge || "Judge")} → ${escapeHtml(who)}`;
      const breakdown = `🍪 ${s.taste} ${scoreEmoji("taste", s.taste)}  •  🎁 ${s.presentation} ${scoreEmoji("presentation", s.presentation)}  •  ✨ ${s.spirit} ${scoreEmoji("spirit", s.spirit)}`;
      const comment = (s.comments || "").trim();
      return `<div class="activity-item">
        <div class="activity-top">
          <div class="activity-line">${line}</div>
          <div class="activity-total">🏅 ${fmt(s.total)}</div>
        </div>
        <div class="activity-sub">${breakdown}</div>
        ${comment ? `<div class="activity-comment">“${escapeHtml(comment)}”</div>` : ""}
      </div>`;
    }).join("") || `<div class="muted">No scores yet — start judging! 🎄</div>`;
  }

  function aggregate(participants, scores) {
    const map = {};
    participants.forEach(p => {
      map[p.id] = { p, count: 0, taste: 0, presentation: 0, spirit: 0, total: 0 };
    });
    scores.forEach(s => {
      const a = map[s.participantId];
      if (!a) return;
      a.count += 1;
      a.taste += Number(s.taste || 0);
      a.presentation += Number(s.presentation || 0);
      a.spirit += Number(s.spirit || 0);
      a.total += Number(s.total || 0);
    });
    const rows = Object.values(map).map(a => {
      const c = Math.max(1, a.count);
      return {
        id: a.p.id,
        name: a.p.name,
        dessert: a.p.dessert || "—",
        count: a.count,
        avgTaste: a.count ? a.taste / c : 0,
        avgPresentation: a.count ? a.presentation / c : 0,
        avgSpirit: a.count ? a.spirit / c : 0,
        avgTotal: a.count ? a.total / c : 0,
      };
    });
    rows.sort((x, y) => (y.avgTotal - x.avgTotal) || (y.count - x.count));
    return rows;
  }

  function renderLeaderboard(participants, scores) {
    if (!leaderboardEl) return;

    const rows = aggregate(participants, scores);
    if (!rows.length) {
      leaderboardEl.innerHTML = `<div class="muted">Add participants in Admin to begin 🎅</div>`;
      return;
    }

    leaderboardEl.innerHTML = rows.map((r, idx) => {
      const medal = idx === 0 ? "🥇" : idx === 1 ? "🥈" : idx === 2 ? "🥉" : "🎄";
      const dessert = (r.dessert || "—").trim();
      const subtitle = dessert && dessert !== "—" ? `${escapeHtml(dessert)}` : "—";
      return `<div class="leader-row">
        <div class="leader-rank">${medal}</div>
        <div class="leader-main">
          <div class="leader-name">${escapeHtml(r.name)}</div>
          <div class="leader-sub">${subtitle}</div>
          <div class="badges">
            <span class="badge">🍪 ${fmt(r.avgTaste)} ${scoreEmoji("taste", Math.round(r.avgTaste || 1))}</span>
            <span class="badge">🎁 ${fmt(r.avgPresentation)} ${scoreEmoji("presentation", Math.round(r.avgPresentation || 1))}</span>
            <span class="badge">✨ ${fmt(r.avgSpirit)} ${scoreEmoji("spirit", Math.round(r.avgSpirit || 1))}</span>
          </div>
        </div>
        <div class="leader-score">
          <div class="leader-total">🏅 ${fmt(r.avgTotal)}</div>
          <div class="leader-count">${r.count} vote${r.count === 1 ? "" : "s"}</div>
        </div>
      </div>`;
    }).join("");
  }

  function populateParticipants(participants) {
    if (!participantSelect) return;
    participantSelect.innerHTML = participants.map(p => {
      return `<option value="${escapeAttr(p.id)}">${escapeHtml(participantLabel(p))}</option>`;
    }).join("");
  }

  function escapeHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }
  function escapeAttr(s) { return escapeHtml(s).replace(/"/g, "&quot;"); }

  let latestState = null;

  function renderAll(state) {
    latestState = state;
    const participants = state.participants || [];
    const scores = state.scores || [];
    const byId = Object.fromEntries(participants.map(p => [p.id, p]));

    populateParticipants(participants);
    renderLeaderboard(participants, scores);
    renderRoster(participants);
    renderActivity(byId, scores);
  }

  async function fetchState() {
    const res = await fetch("/api/state", { cache: "no-store" });
    return await res.json();
  }

  async function init() {
    setSliderUI();
    const state = await fetchState();
    renderAll(state);

    // Live updates
    if (window.io) {
      const socket = io();
      socket.on("update", (state) => renderAll(state));
    }
  }

  $("refreshBtn")?.addEventListener("click", async () => {
    const state = await fetchState();
    renderAll(state);
  });

  $("scoreForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    submitStatus.textContent = "";

    const payload = {
      judge: $("judge").value.trim(),
      participantId: participantSelect.value,
      taste: Number(tasteRange.value),
      presentation: Number(presentationRange.value),
      spirit: Number(spiritRange.value),
      comments: $("comments").value.trim(),
    };

    if (!payload.judge) {
      submitStatus.textContent = "Please enter your name 🙂";
      return;
    }

    try {
      const res = await fetch("/api/score", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.error || "Failed");
      submitStatus.textContent = `Submitted! Total: ${data.total} 🎄`;

      // reset sliders (keep judge name)
      $("comments").value = "";
      tasteRange.value = "5";
      presentationRange.value = "5";
      spiritRange.value = "5";
      setSliderUI();

      // if sockets aren't working, pull latest
      if (!window.io) {
        const state = await fetchState();
        renderAll(state);
      }
    } catch (err) {
      submitStatus.textContent = `Error: ${err.message}`;
    }
  });

  document.addEventListener("DOMContentLoaded", init);
})();
