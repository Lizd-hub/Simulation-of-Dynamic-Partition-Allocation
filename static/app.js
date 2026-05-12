const algorithmGrid = document.getElementById("algorithmGrid");
const processQueue = document.getElementById("processQueue");
const logTabs = document.getElementById("logTabs");
const logBody = document.getElementById("logBody");
const runStatus = document.getElementById("runStatus");
const sessionId = document.getElementById("sessionId");
const tickValue = document.getElementById("tickValue");
const seedValue = document.getElementById("seedValue");
const seedInput = document.getElementById("seedInput");
const speedSelect = document.getElementById("speedSelect");
const startButton = document.getElementById("startButton");
const pauseButton = document.getElementById("pauseButton");
const resumeButton = document.getElementById("resumeButton");
const stopButton = document.getElementById("stopButton");

const TOTAL_MEMORY_KB = 10 * 1024;
const EXIT_ANIMATION_MS = 240;

const uiState = {
  selectedAlgorithm: "first_fit",
  poller: null,
  latest: null,
  cards: new Map(),
  previousSignature: "",
  isFetching: false,
};

function isRenderableState(state) {
  return Boolean(
    state
    && Array.isArray(state.algorithms)
    && Array.isArray(state.active_processes),
  );
}

function hashColor(input) {
  let hash = 0;
  for (let index = 0; index < input.length; index += 1) {
    hash = input.charCodeAt(index) + ((hash << 5) - hash);
  }
  const hue = Math.abs(hash) % 360;
  return `hsl(${hue} 52% 46%)`;
}

function formatDistribution(values) {
  if (!values.length) {
    return "无空闲块";
  }
  return values.map((value) => `${value}KB`).join(" / ");
}

function toPercent(sizeKb) {
  return `${(sizeKb / TOTAL_MEMORY_KB) * 100}%`;
}

function createStatBox(label) {
  const box = document.createElement("div");
  const labelElement = document.createElement("small");
  const valueElement = document.createElement("strong");
  box.className = "stat-box";
  labelElement.textContent = label;
  valueElement.textContent = "0";
  box.append(labelElement, valueElement);
  return { box, valueElement };
}

function getBlockKey(block) {
  return block.process_id
    ? `used-${block.process_id}`
    : `free-${block.start_kb}-${block.end_kb}`;
}

function applyBlockState(blockElement, block) {
  const isUsed = Boolean(block.process_id);
  const labelElement = blockElement.querySelector(".block-label");
  const compact = block.size_kb < 360;

  blockElement.className = `memory-block ${isUsed ? "used" : "free"}${compact ? " compact" : ""}`;
  blockElement.style.background = isUsed ? hashColor(block.process_id) : "var(--memory-free)";
  blockElement.style.top = toPercent(block.start_kb);
  blockElement.style.height = toPercent(block.size_kb);
  blockElement.title = `${block.start_kb}KB - ${block.end_kb}KB`;

  labelElement.className = `block-label${block.size_kb < 220 ? " mini" : ""}`;
  labelElement.innerHTML = isUsed
    ? `${block.process_id}<br>${block.size_kb}KB`
    : `空闲<br>${block.size_kb}KB`;
}

function createBlockElement(block) {
  const blockElement = document.createElement("div");
  const labelElement = document.createElement("span");

  blockElement.className = "memory-block is-entering";
  blockElement.dataset.blockKey = getBlockKey(block);
  labelElement.className = "block-label";
  blockElement.append(labelElement);
  applyBlockState(blockElement, block);

  requestAnimationFrame(() => {
    blockElement.classList.remove("is-entering");
  });

  return blockElement;
}

function markLeaving(element) {
  if (element.dataset.leaving === "true") {
    return;
  }

  element.dataset.leaving = "true";
  element.classList.add("is-leaving");

  window.setTimeout(() => {
    if (element.dataset.leaving === "true" && element.parentElement) {
      element.remove();
    }
  }, EXIT_ANIMATION_MS);
}

function updateMemoryColumn(columnElement, blocks) {
  const existingBlocks = new Map(
    Array.from(columnElement.children).map((element) => [element.dataset.blockKey, element]),
  );
  const seenKeys = new Set();

  blocks.forEach((block) => {
    const key = getBlockKey(block);
    seenKeys.add(key);

    let blockElement = existingBlocks.get(key);
    if (!blockElement) {
      blockElement = createBlockElement(block);
      columnElement.append(blockElement);
      return;
    }

    if (blockElement.dataset.leaving === "true") {
      delete blockElement.dataset.leaving;
      blockElement.classList.remove("is-leaving");
    }

    applyBlockState(blockElement, block);
    columnElement.append(blockElement);
  });

  existingBlocks.forEach((element, key) => {
    if (!seenKeys.has(key)) {
      markLeaving(element);
    }
  });
}

function createAlgorithmCard(algorithm) {
  const article = document.createElement("article");
  article.className = "algorithm-card";

  const head = document.createElement("div");
  head.className = "card-head";

  const titleGroup = document.createElement("div");
  const title = document.createElement("h3");
  const subtitle = document.createElement("p");
  title.textContent = algorithm.label;
  subtitle.textContent = "10MB 连续空间链表管理";
  titleGroup.append(title, subtitle);

  const chip = document.createElement("span");
  chip.className = "chip";
  head.append(titleGroup, chip);

  const memoryShell = document.createElement("div");
  memoryShell.className = "memory-shell";
  memoryShell.innerHTML = `
    <div class="memory-scale">
      <span>0KB</span>
      <span>10240KB</span>
    </div>
  `;
  const memoryColumn = document.createElement("div");
  memoryColumn.className = "memory-column";
  memoryShell.append(memoryColumn);

  const statsGrid = document.createElement("div");
  statsGrid.className = "stats-grid";
  const statRefs = {
    success: createStatBox("分配成功"),
    failure: createStatBox("分配失败"),
    running: createStatBox("已装入进程"),
    freeCount: createStatBox("空闲块数量"),
    utilization: createStatBox("利用率"),
    largest: createStatBox("最大空闲块"),
  };
  Object.values(statRefs).forEach((stat) => statsGrid.append(stat.box));

  const distributionBox = document.createElement("div");
  distributionBox.className = "distribution-box";
  distributionBox.innerHTML = `
    <p>空闲块分布</p>
    <div class="distribution-values"></div>
  `;
  const distributionValues = distributionBox.querySelector(".distribution-values");

  const downloadLink = document.createElement("a");
  downloadLink.className = "download-link";

  article.append(head, memoryShell, statsGrid, distributionBox, downloadLink);
  algorithmGrid.append(article);

  return {
    chip,
    memoryColumn,
    statRefs,
    distributionValues,
    downloadLink,
  };
}

function ensureAlgorithmCards(algorithms) {
  if (uiState.cards.size === algorithms.length) {
    return;
  }

  algorithmGrid.replaceChildren();
  uiState.cards.clear();

  algorithms.forEach((algorithm) => {
    uiState.cards.set(algorithm.key, createAlgorithmCard(algorithm));
  });
}

function updateAlgorithmCard(algorithm) {
  const refs = uiState.cards.get(algorithm.key);
  if (!refs) {
    return;
  }

  refs.chip.textContent = `${algorithm.failure_count} 次失败`;
  refs.statRefs.success.valueElement.textContent = String(algorithm.success_count);
  refs.statRefs.failure.valueElement.textContent = String(algorithm.failure_count);
  refs.statRefs.running.valueElement.textContent = String(algorithm.stats.allocated_process_count);
  refs.statRefs.freeCount.valueElement.textContent = String(algorithm.stats.free_block_count);
  refs.statRefs.utilization.valueElement.textContent = `${algorithm.stats.utilization_rate}%`;
  refs.statRefs.largest.valueElement.textContent = `${algorithm.stats.largest_free_block_kb}KB`;
  refs.distributionValues.textContent = formatDistribution(algorithm.free_distribution);
  refs.downloadLink.href = algorithm.log_file ? `/logs/${algorithm.log_file}` : "#";
  refs.downloadLink.textContent = `下载 ${algorithm.label} CSV 日志`;
  updateMemoryColumn(refs.memoryColumn, algorithm.blocks);
}

function renderAlgorithms(algorithms) {
  ensureAlgorithmCards(algorithms);
  algorithms.forEach(updateAlgorithmCard);
}

function renderProcessQueue(processes) {
  if (!processes.length) {
    processQueue.className = "queue-list empty-state";
    processQueue.textContent = "当前没有处于生命周期内的进程。";
    return;
  }

  processQueue.className = "queue-list";
  processQueue.innerHTML = processes.map((process) => `
    <div class="queue-pill">
      <strong>${process.process_id}</strong>
      <div>${process.size_kb}KB</div>
      <div>Tick ${process.created_tick} -> ${process.end_tick}</div>
    </div>
  `).join("");
}

function renderLogTabs(algorithms) {
  logTabs.innerHTML = algorithms.map((algorithm) => `
    <button
      class="tab-button ${uiState.selectedAlgorithm === algorithm.key ? "active" : ""}"
      data-algorithm-key="${algorithm.key}"
      type="button"
    >
      ${algorithm.label}
    </button>
  `).join("");

  logTabs.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      uiState.selectedAlgorithm = button.dataset.algorithmKey;
      renderLogTabs(uiState.latest.algorithms);
      renderLogs(uiState.latest.algorithms);
    });
  });
}

function renderLogs(algorithms) {
  const selected = algorithms.find((item) => item.key === uiState.selectedAlgorithm) || algorithms[0];
  uiState.selectedAlgorithm = selected.key;

  if (!selected.recent_logs.length) {
    logBody.className = "log-body empty-state";
    logBody.textContent = "当前算法还没有产生操作日志。";
    return;
  }

  logBody.className = "log-body";
  logBody.innerHTML = selected.recent_logs.map((entry) => `
    <div class="log-entry">
      <div>
        <strong>${entry.action}</strong>
        <span>${entry.process_id}</span>
        <span>${entry.size_kb ? ` / ${entry.size_kb}KB` : ""}</span>
      </div>
      <div>${entry.timestamp} · Tick ${entry.tick} · ${entry.result}</div>
      <div>${entry.detail}</div>
    </div>
  `).join("");
}

function updateControlState(state) {
  const modeText = state.running ? "运行中" : state.paused ? "已暂停" : state.session_id ? "已停止" : "待启动";
  runStatus.textContent = modeText;
  pauseButton.disabled = !state.running;
  resumeButton.disabled = !state.paused;
  stopButton.disabled = !state.running && !state.paused && !state.session_id;
}

function getStateSignature(state) {
  if (!isRenderableState(state)) {
    return "invalid-state";
  }

  const algorithmSignature = state.algorithms
    .map((algorithm) => [
      algorithm.key,
      algorithm.failure_count,
      algorithm.success_count,
      algorithm.release_count,
      algorithm.blocks.map((block) => `${block.start_kb}-${block.size_kb}-${block.process_id || "free"}`).join(","),
    ].join(":"))
    .join("|");

  return [
    state.session_id,
    state.tick,
    state.running,
    state.paused,
    state.active_processes.map((process) => `${process.process_id}-${process.end_tick}`).join(","),
    algorithmSignature,
  ].join("::");
}

function renderState(state) {
  if (!isRenderableState(state)) {
    return;
  }

  const signature = getStateSignature(state);
  const shouldUpdate = signature !== uiState.previousSignature;

  uiState.latest = state;
  sessionId.textContent = state.session_id || "未创建";
  tickValue.textContent = String(state.tick);
  seedValue.textContent = state.seed ?? "-";
  updateControlState(state);

  if (!shouldUpdate) {
    return;
  }

  renderAlgorithms(state.algorithms);
  renderProcessQueue(state.active_processes);
  renderLogTabs(state.algorithms);
  renderLogs(state.algorithms);
  uiState.previousSignature = signature;
}

async function fetchState() {
  if (uiState.isFetching) {
    return;
  }

  uiState.isFetching = true;
  try {
    const response = await fetch("/api/state");
    if (!response.ok) {
      throw new Error(`Failed to fetch state: ${response.status}`);
    }
    const state = await response.json();
    renderState(state);
  } finally {
    uiState.isFetching = false;
  }
}

async function sendCommand(path, payload = {}) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Command failed: ${response.status}`);
  }
  const state = await response.json();
  renderState(state);
}

async function startSimulation() {
  await sendCommand("/api/start", {
    seed: seedInput.value.trim() ? Number(seedInput.value.trim()) : null,
    interval_ms: Number(speedSelect.value),
  });
}

async function pauseSimulation() {
  await sendCommand("/api/pause");
}

async function resumeSimulation() {
  await sendCommand("/api/resume");
}

async function stopSimulation() {
  await sendCommand("/api/stop");
}

startButton.addEventListener("click", startSimulation);
pauseButton.addEventListener("click", pauseSimulation);
resumeButton.addEventListener("click", resumeSimulation);
stopButton.addEventListener("click", stopSimulation);

uiState.poller = window.setInterval(() => {
  fetchState().catch(() => {});
}, 350);

fetchState().catch(() => {});
