
const emojiMap = ["😡","😞","😕","😐","🙂","😊","😄","😁","🤩","🔥"];

const slider = document.getElementById("scoreRange");
const emoji = document.getElementById("scoreEmoji");

slider.oninput = () => {
  emoji.innerText = emojiMap[slider.value - 1];
};

async function loadState() {
  const res = await fetch("/api/state");
  const data = await res.json();
  const select = document.getElementById("participant");
  select.innerHTML = "";
  data.participants.filter(p => p.active).forEach(p => {
    const opt = document.createElement("option");
    opt.value = p.name;
    opt.innerText = p.name + " - " + p.dessert;
    select.appendChild(opt);
  });
}

async function submitScore() {
  await fetch("/api/score", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      judge: document.getElementById("judge").value,
      participant: document.getElementById("participant").value,
      score: slider.value
    })
  });
  alert("Score submitted!");
}

loadState();
