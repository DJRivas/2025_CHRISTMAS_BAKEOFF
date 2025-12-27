
async function loadParticipants() {
  const res = await fetch("/api/state");
  const data = await res.json();
  const container = document.getElementById("participants");
  container.innerHTML = "";
  data.participants.forEach((p, i) => {
    const row = document.createElement("div");
    row.innerHTML = `
      <input value="${p.name}" onchange="update(${i}, 'name', this.value)"/>
      <input value="${p.dessert}" onchange="update(${i}, 'dessert', this.value)"/>
      <input type="checkbox" ${p.active ? "checked" : ""} onchange="update(${i}, 'active', this.checked)"/>
    `;
    container.appendChild(row);
  });
}

let participants = [];

async function update(index, key, value) {
  participants[index][key] = value;
  await fetch("/api/participants", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(participants)
  });
}

async function addParticipant() {
  participants.push({name: "New", dessert: "Dessert", active: true});
  await fetch("/api/participants", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(participants)
  });
  loadParticipants();
}

(async () => {
  const res = await fetch("/api/state");
  const data = await res.json();
  participants = data.participants;
  loadParticipants();
})();
