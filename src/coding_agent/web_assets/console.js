const form = document.getElementById("taskForm");
const taskInput = document.getElementById("task");
const runButton = document.getElementById("runButton");
const status = document.getElementById("status");
const result = document.getElementById("result");
const timeline = document.getElementById("timeline");
const thinkingControl = document.querySelector("[data-thinking-control]");
let thinking = "medium";

thinkingControl.addEventListener("thinking-change", (event) => { thinking = event.detail.level; });

function renderEvents(events) {
  timeline.replaceChildren();
  for (const item of events) {
    const row = document.createElement("li");
    const detail = item.tool ? ` · ${item.tool}` : item.outcome ? ` · ${item.outcome}` : "";
    row.textContent = `${item.event}${detail}`;
    timeline.appendChild(row);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const task = taskInput.value.trim();
  if (!task) return;
  runButton.disabled = true;
  status.className = "status";
  status.textContent = `Running with ${thinking} thinking…`;
  result.textContent = "";
  timeline.replaceChildren();
  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task, thinking }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    result.textContent = payload.result;
    renderEvents(payload.events);
    status.textContent = `Finished · ${payload.thinking} · ${payload.events.length} audited events`;
  } catch (error) {
    status.className = "status error";
    status.textContent = `Failed: ${error.message}`;
  } finally {
    runButton.disabled = false;
  }
});
