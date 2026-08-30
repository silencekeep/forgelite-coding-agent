const form = document.getElementById("taskForm");
const taskInput = document.getElementById("task");
const runButton = document.getElementById("runButton");
const statusLine = document.getElementById("status");
const emptyState = document.getElementById("emptyState");
const userTurn = document.getElementById("userTurn");
const userTask = document.getElementById("userTask");
const activityPanel = document.getElementById("activityPanel");
const activityCount = document.getElementById("activityCount");
const timeline = document.getElementById("timeline");
const assistantTurn = document.getElementById("assistantTurn");
const result = document.getElementById("result");
const thinkingControl = document.querySelector("[data-thinking-control]");
let thinking = "medium";
let renderedEvents = 0;

thinkingControl.addEventListener("thinking-change", (event) => {
  thinking = event.detail.level;
});

function beginSession(task) {
  emptyState.hidden = true;
  userTask.textContent = task;
  userTurn.hidden = false;
  activityPanel.hidden = false;
  assistantTurn.hidden = true;
  result.textContent = "";
  timeline.replaceChildren();
  renderedEvents = 0;
  activityCount.textContent = "0 events";
}

function describeEvent(item) {
  if (item.event === "run_started") {
    return {
      phase: "start",
      title: "任务进入本地控制循环",
      detail: `${item.thinking_level || thinking} · 最多 ${item.max_steps || "?"} 回合 · ${item.context_char_budget || "?"} 字符上下文`,
      state: "started",
    };
  }
  if (item.event === "model_request_started") {
    return {
      phase: "reason",
      title: "模型规划下一步",
      detail: `第 ${item.step} 轮 · ${item.message_count} 条压缩后消息`,
      state: "planning",
    };
  }
  if (item.event === "model_request_failed") {
    return {
      phase: "observe error",
      title: "模型请求失败",
      detail: `第 ${item.step} 轮 · ${item.error_type}`,
      state: "error",
      stateClass: "error",
    };
  }
  if (item.event === "tool_called") {
    const keys = Array.isArray(item.argument_keys) && item.argument_keys.length
      ? item.argument_keys.join(", ")
      : "no arguments";
    return {
      phase: "act",
      title: `调用 ${item.tool}`,
      detail: `已校验参数字段：${keys}`,
      state: "running",
    };
  }
  if (item.event === "tool_finished") {
    const ok = item.ok === true;
    return {
      phase: ok ? "observe" : "observe error",
      title: `${item.tool} ${ok ? "执行成功" : "返回错误，交还模型修正"}`,
      detail: `观察结果 ${item.output_characters || 0} 字符 · 内容不写入审计轨迹`,
      state: ok ? "ok" : "error",
      stateClass: ok ? "ok" : "error",
    };
  }
  if (item.event === "run_finished") {
    return {
      phase: "finish",
      title: item.outcome === "model_final" ? "模型给出最终交付总结" : `运行结束：${item.outcome}`,
      detail: `${item.steps_used || "?"} 个模型回合 · 本地终止条件生效`,
      state: "done",
      stateClass: "ok",
    };
  }
  return {
    phase: "observe",
    title: item.event || "agent_event",
    detail: "credential-safe audit event",
    state: "event",
  };
}

function renderEvent(item, scroll = true) {
  const view = describeEvent(item);
  const row = document.createElement("li");
  row.className = "react-row";

  const phase = document.createElement("span");
  phase.className = `phase ${view.phase}`;
  phase.textContent = view.phase.split(" ")[0];

  const copy = document.createElement("div");
  copy.className = "event-copy";
  const title = document.createElement("strong");
  title.textContent = view.title;
  const detail = document.createElement("span");
  detail.textContent = view.detail;
  copy.append(title, detail);

  const eventState = document.createElement("span");
  eventState.className = `event-state ${view.stateClass || ""}`.trim();
  eventState.textContent = view.state;

  row.append(phase, copy, eventState);
  timeline.appendChild(row);
  renderedEvents += 1;
  activityCount.textContent = `${renderedEvents} events`;
  if (scroll) timeline.scrollTop = timeline.scrollHeight;
}

function handleRecord(record) {
  if (record.type === "status") {
    statusLine.className = "status running";
    statusLine.textContent = `Running · ${record.thinking} thinking · waiting for model…`;
    return;
  }
  if (record.type === "event") {
    renderEvent(record);
    if (record.event === "model_request_started") {
      statusLine.textContent = `Reason · model turn ${record.step} is planning the next action…`;
    } else if (record.event === "tool_called") {
      statusLine.textContent = `Act · running local tool ${record.tool}…`;
    } else if (record.event === "tool_finished") {
      statusLine.textContent = `Observe · ${record.tool} returned ${record.ok ? "success" : "an error"}`;
    }
    return;
  }
  if (record.type === "result") {
    result.textContent = record.result;
    assistantTurn.hidden = false;
    statusLine.className = "status";
    statusLine.textContent = `Finished · ${record.thinking} · ${record.event_count} audited events`;
    return;
  }
  if (record.type === "error") {
    const error = new Error(record.error || "Agent run failed.");
    error.status = record.status;
    throw error;
  }
}

async function runStreaming(task) {
  const response = await fetch("/api/run-stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task, thinking }),
  });
  if (!response.ok) {
    const payload = await response.json();
    throw new Error(payload.error || `HTTP ${response.status}`);
  }
  if (!response.body) throw new Error("Streaming response body is unavailable.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (line.trim()) handleRecord(JSON.parse(line));
    }
    if (done) break;
  }
  if (buffer.trim()) handleRecord(JSON.parse(buffer));
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const task = taskInput.value.trim();
  if (!task) return;
  beginSession(task);
  runButton.disabled = true;
  taskInput.disabled = true;
  statusLine.className = "status running";
  statusLine.textContent = `Starting · ${thinking} thinking…`;
  try {
    await runStreaming(task);
  } catch (error) {
    statusLine.className = "status error";
    statusLine.textContent = `Failed${error.status ? ` · HTTP ${error.status}` : ""}: ${error.message}`;
  } finally {
    runButton.disabled = false;
    taskInput.disabled = false;
  }
});

const demoTask = "从空目录创建一个 Python 命令行待办项目：实现 add、list、done 和 JSON 持久化；编写完整测试与 README，运行测试并根据失败自行修正。";
const demoEvents = [
  { event: "run_started", thinking_level: "high", max_steps: 28, context_char_budget: 80000 },
  { event: "model_request_started", step: 1, message_count: 2 },
  { event: "tool_called", tool: "list_files", argument_keys: ["path"] },
  { event: "tool_finished", tool: "list_files", ok: true, output_characters: 18 },
  { event: "model_request_started", step: 2, message_count: 4 },
  { event: "tool_called", tool: "write_file", argument_keys: ["content", "path"] },
  { event: "tool_finished", tool: "write_file", ok: true, output_characters: 27 },
  { event: "model_request_started", step: 3, message_count: 6 },
  { event: "tool_called", tool: "write_file", argument_keys: ["content", "path"] },
  { event: "tool_finished", tool: "write_file", ok: true, output_characters: 39 },
  { event: "model_request_started", step: 4, message_count: 8 },
  { event: "tool_called", tool: "write_file", argument_keys: ["content", "path"] },
  { event: "tool_finished", tool: "write_file", ok: true, output_characters: 25 },
  { event: "model_request_started", step: 5, message_count: 10 },
  { event: "tool_called", tool: "run_command", argument_keys: ["command"] },
  { event: "tool_finished", tool: "run_command", ok: false, output_characters: 104 },
  { event: "model_request_started", step: 6, message_count: 12 },
  { event: "tool_called", tool: "run_command", argument_keys: ["command"] },
  { event: "tool_finished", tool: "run_command", ok: true, output_characters: 156 },
  { event: "model_request_started", step: 7, message_count: 14 },
  { event: "run_finished", outcome: "model_final", steps_used: 7 },
];

function loadPreview() {
  const preview = new URLSearchParams(window.location.search).get("preview");
  if (!preview) return;
  document.body.dataset.previewStage = preview;
  window.ThinkingIndicator.select(thinkingControl, "high");
  taskInput.value = demoTask;
  beginSession(demoTask);
  if (preview === "task") {
    activityPanel.hidden = true;
    statusLine.textContent = "Ready to run · High thinking";
    return;
  }
  form.hidden = true;
  const limits = { build: 13, recover: 19, complete: demoEvents.length };
  for (const item of demoEvents.slice(0, limits[preview] || demoEvents.length)) renderEvent(item, false);
  timeline.scrollTop = timeline.scrollHeight;
  if (preview === "complete") {
    result.textContent = "完成：已创建 todo_app.py、5 项单元测试和 README。首次测试命令失败后已根据观察结果更正；最终 5/5 测试及黑盒验证通过。";
    assistantTurn.hidden = false;
    statusLine.textContent = "Finished · high · 21 audited events";
  } else if (preview === "recover") {
    statusLine.className = "status running";
    statusLine.textContent = "Observe · tests passed after autonomous correction";
  } else {
    statusLine.className = "status running";
    statusLine.textContent = "Act · creating implementation, tests and README…";
  }
}

loadPreview();
