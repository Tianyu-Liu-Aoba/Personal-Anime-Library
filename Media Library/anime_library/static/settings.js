const settingsState = {
  config: null,
  paths: [],
  themeMode: "system",
  accent: "sunrise",
  fontBody: '"Trebuchet MS", "Segoe UI", sans-serif',
  fontDisplay: '"Bahnschrift", "Segoe UI", sans-serif',
  backgroundStart: "#fff5ef",
  backgroundEnd: "#fff0e6",
  backgroundStartDark: "#0f0f0f",
  backgroundEndDark: "#252525",
};

const themeOptions = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

const accentOptions = [
  { value: "sunrise", label: "Sunrise" },
  { value: "ocean", label: "Ocean" },
  { value: "forest", label: "Forest" },
];

document.addEventListener("DOMContentLoaded", () => {
  document.addEventListener("click", (event) => {
    const button = event.target.closest(".pill-button, .segment-button, .icon-button");
    if (button) {
      triggerButtonAnimation(button);
    }
  });
  document.getElementById("closeButton").addEventListener("click", () => window.close());
  document.getElementById("addPathButton").addEventListener("click", addPath);
  document.getElementById("saveButton").addEventListener("click", saveSettings);
  document.getElementById("scanNowButton").addEventListener("click", () => saveSettings(true));
  document.getElementById("refreshLogsButton").addEventListener("click", loadLogs);
  document.getElementById("bodyFontInput").addEventListener("input", (event) => {
    settingsState.fontBody = event.target.value.trim() || '"Trebuchet MS", "Segoe UI", sans-serif';
    applyAppearance();
  });
  document.getElementById("displayFontInput").addEventListener("input", (event) => {
    settingsState.fontDisplay = event.target.value.trim() || '"Bahnschrift", "Segoe UI", sans-serif';
    applyAppearance();
  });
  document.getElementById("backgroundStartInput").addEventListener("input", (event) => {
    settingsState.backgroundStart = event.target.value || "#fff5ef";
    applyAppearance();
  });
  document.getElementById("backgroundEndInput").addEventListener("input", (event) => {
    settingsState.backgroundEnd = event.target.value || "#fff0e6";
    applyAppearance();
  });
  document.getElementById("backgroundStartDarkInput").addEventListener("input", (event) => {
    settingsState.backgroundStartDark = event.target.value || "#0f0f0f";
    applyAppearance();
  });
  document.getElementById("backgroundEndDarkInput").addEventListener("input", (event) => {
    settingsState.backgroundEndDark = event.target.value || "#252525";
    applyAppearance();
  });
  loadSettings();
});

async function loadSettings() {
  const payload = await api("/api/settings");
  settingsState.config = payload.config;
  settingsState.paths = [...(payload.config.library_paths || [])];
  settingsState.themeMode = payload.config.appearance?.theme_mode || "system";
  settingsState.accent = payload.config.appearance?.accent || "sunrise";
  settingsState.fontBody = payload.config.appearance?.font_body || settingsState.fontBody;
  settingsState.fontDisplay = payload.config.appearance?.font_display || settingsState.fontDisplay;
  settingsState.backgroundStart = payload.config.appearance?.background_start || settingsState.backgroundStart;
  settingsState.backgroundEnd = payload.config.appearance?.background_end || settingsState.backgroundEnd;
  settingsState.backgroundStartDark = payload.config.appearance?.background_start_dark || settingsState.backgroundStartDark;
  settingsState.backgroundEndDark = payload.config.appearance?.background_end_dark || settingsState.backgroundEndDark;
  applyAppearance();
  renderSegments();
  renderPaths();
  document.getElementById("bodyFontInput").value = settingsState.fontBody;
  document.getElementById("displayFontInput").value = settingsState.fontDisplay;
  document.getElementById("backgroundStartInput").value = settingsState.backgroundStart;
  document.getElementById("backgroundEndInput").value = settingsState.backgroundEnd;
  document.getElementById("backgroundStartDarkInput").value = settingsState.backgroundStartDark;
  document.getElementById("backgroundEndDarkInput").value = settingsState.backgroundEndDark;
  document.getElementById("malClientIdInput").value = payload.config.providers?.mal_client_id || "";
  document.getElementById("tmdbApiKeyInput").value = payload.config.providers?.tmdb_api_key || "";
  document.getElementById("tmdbTokenInput").value = payload.config.providers?.tmdb_read_access_token || "";
  document.getElementById("logPathLabel").textContent = payload.logs?.path || "No log file yet.";
  renderLogLines(payload.logs?.lines || []);
}

function applyAppearance() {
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const theme = settingsState.themeMode === "system" ? (prefersDark ? "dark" : "light") : settingsState.themeMode;
  const colors = buildBackgroundPalette(
    settingsState.backgroundStart,
    settingsState.backgroundEnd,
    settingsState.backgroundStartDark,
    settingsState.backgroundEndDark
  );
  document.documentElement.dataset.theme = theme;
  document.body.dataset.theme = theme;
  document.documentElement.dataset.accent = settingsState.accent;
  document.documentElement.style.setProperty("--font-body", settingsState.fontBody);
  document.documentElement.style.setProperty("--font-display", settingsState.fontDisplay);
  document.documentElement.style.setProperty("--bg-start", colors.start);
  document.documentElement.style.setProperty("--bg-mid", colors.mid);
  document.documentElement.style.setProperty("--bg-end", colors.end);
  document.documentElement.style.setProperty("--bg-spot-a", colors.spotA);
  document.documentElement.style.setProperty("--bg-spot-b", colors.spotB);
  document.documentElement.style.setProperty("--bg-start-dark", colors.darkStart);
  document.documentElement.style.setProperty("--bg-mid-dark", colors.darkMid);
  document.documentElement.style.setProperty("--bg-end-dark", colors.darkEnd);
  document.documentElement.style.setProperty("--bg-spot-a-dark", colors.darkSpotA);
  document.documentElement.style.setProperty("--bg-spot-b-dark", colors.darkSpotB);
  const isDarkTheme = theme === "dark";
  document.documentElement.style.setProperty("--surface", isDarkTheme ? colors.surfaceDark : colors.surface);
  document.documentElement.style.setProperty("--surface-strong", isDarkTheme ? colors.surfaceStrongDark : colors.surfaceStrong);
  document.documentElement.style.setProperty("--surface-subtle", isDarkTheme ? colors.surfaceSubtleDark : colors.surfaceSubtle);
  document.documentElement.style.setProperty("--line", isDarkTheme ? colors.lineDark : colors.line);
  document.documentElement.style.setProperty("--surface-dark", colors.surfaceDark);
  document.documentElement.style.setProperty("--surface-strong-dark", colors.surfaceStrongDark);
  document.documentElement.style.setProperty("--surface-subtle-dark", colors.surfaceSubtleDark);
  document.documentElement.style.setProperty("--line-dark", colors.lineDark);
  document.documentElement.style.setProperty("--overlay-backdrop", isDarkTheme ? colors.overlayBackdropDark : colors.overlayBackdrop);
  document.documentElement.style.setProperty("--overlay-backdrop-dark", colors.overlayBackdropDark);
}

function renderSegments() {
  renderSegmentGroup("themeModeSegment", themeOptions, settingsState.themeMode, (value) => {
    settingsState.themeMode = value;
    applyAppearance();
    renderSegments();
  });
  renderSegmentGroup("accentSegment", accentOptions, settingsState.accent, (value) => {
    settingsState.accent = value;
    applyAppearance();
    renderSegments();
  });
}

function renderSegmentGroup(elementId, options, activeValue, onSelect) {
  const shell = document.getElementById(elementId);
  shell.innerHTML = "";
  options.forEach((option) => {
    const button = document.createElement("button");
    button.className = `segment-button ${option.value === activeValue ? "active" : ""}`;
    button.textContent = option.label;
    button.addEventListener("click", () => onSelect(option.value));
    shell.appendChild(button);
  });
}

function renderPaths() {
  const container = document.getElementById("settingsPathList");
  container.innerHTML = "";
  if (!settingsState.paths.length) {
    container.innerHTML = `<div class="path-row"><p>No library paths configured yet.</p></div>`;
    return;
  }
  settingsState.paths.forEach((path, index) => {
    const row = document.createElement("div");
    row.className = "path-row";
    row.innerHTML = `
      <div>
        <strong>${escapeHtml(path)}</strong>
      </div>
      <button class="text-button">Remove</button>
    `;
    row.querySelector("button").addEventListener("click", () => {
      settingsState.paths.splice(index, 1);
      renderPaths();
    });
    container.appendChild(row);
  });
}

async function addPath() {
  const result = await api("/api/system/select-folder", { method: "POST", body: {} });
  if (result.path && !settingsState.paths.includes(result.path)) {
    settingsState.paths.push(result.path);
    renderPaths();
  }
}

async function saveSettings(forceScan = false) {
  settingsState.fontBody = document.getElementById("bodyFontInput").value.trim() || settingsState.fontBody;
  settingsState.fontDisplay = document.getElementById("displayFontInput").value.trim() || settingsState.fontDisplay;
  const originalPaths = settingsState.config?.library_paths || [];
  const pathsChanged = JSON.stringify(settingsState.paths) !== JSON.stringify(originalPaths);
  const payload = {
    library_paths: settingsState.paths,
    theme_mode: settingsState.themeMode,
    accent: settingsState.accent,
    font_body: settingsState.fontBody,
    font_display: settingsState.fontDisplay,
    background_start: settingsState.backgroundStart,
    background_end: settingsState.backgroundEnd,
    background_start_dark: settingsState.backgroundStartDark,
    background_end_dark: settingsState.backgroundEndDark,
    mal_client_id: document.getElementById("malClientIdInput").value.trim(),
    tmdb_api_key: document.getElementById("tmdbApiKeyInput").value.trim(),
    tmdb_read_access_token: document.getElementById("tmdbTokenInput").value.trim(),
    scan_after_save: forceScan,
    refresh_metadata: forceScan,
  };
  const result = await api("/api/settings/save", { method: "POST", body: payload });
  settingsState.config = result.config || settingsState.config;
  const message = document.getElementById("saveMessage");
  message.textContent = forceScan
    ? "Settings saved and a refresh scan started."
    : "Settings saved.";
  triggerMessageFade(message);
  if (window.opener) {
    window.opener.postMessage({ type: "settings-saved" }, "*");
  }
  await loadLogs();
}

async function loadLogs() {
  const payload = await api("/api/logs?limit=160");
  document.getElementById("logPathLabel").textContent = payload.path || "No log file yet.";
  renderLogLines(payload.lines || []);
}

function renderLogLines(lines) {
  document.getElementById("logPanel").textContent = lines.length ? lines.join("\n") : "No log entries yet.";
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    method: options.method || "GET",
    headers: { "Content-Type": "application/json" },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || `Request failed: ${response.status}`);
  }
  return payload;
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function triggerButtonAnimation(button) {
  button.classList.remove("button-animated");
  void button.offsetWidth;
  button.classList.add("button-animated");
  window.setTimeout(() => {
    button.classList.remove("button-animated");
  }, 380);
}

function triggerMessageFade(element) {
  element.classList.remove("message-fade");
  void element.offsetWidth;
  element.classList.add("message-fade");
}

function buildBackgroundPalette(startHex, endHex, darkStartHex, darkEndHex) {
  const start = normalizeHexColor(startHex, "#fff5ef");
  const end = normalizeHexColor(endHex, "#fff0e6");
  const mid = mixHexColors(start, end, 0.5);
  const lightBase = mixHexColors(start, end, 0.42);
  const darkStart = normalizeHexColor(darkStartHex, darkenHex(start, 0.92));
  const darkEnd = normalizeHexColor(darkEndHex, darkenHex(end, 0.96));
  const darkMid = mixHexColors(darkStart, darkEnd, 0.5);
  const darkBase = mixHexColors(darkStart, darkEnd, 0.45);
  return {
    start,
    mid,
    end,
    spotA: hexToRgba(start, 0.78),
    spotB: hexToRgba(end, 0.7),
    darkStart,
    darkMid,
    darkEnd,
    darkSpotA: hexToRgba(darkenHex(darkStart, 0.52), 0.28),
    darkSpotB: hexToRgba(darkenHex(darkEnd, 0.56), 0.22),
    surface: hexToRgba(mixHexColors(lightBase, "#ffffff", 0.8), 0.8),
    surfaceStrong: hexToRgba(mixHexColors(lightBase, "#ffffff", 0.9), 0.9),
    surfaceSubtle: hexToRgba(mixHexColors(start, "#ffffff", 0.72), 0.62),
    line: hexToRgba(darkenHex(lightBase, 0.7), 0.16),
    surfaceDark: hexToRgba(darkBase, 0.92),
    surfaceStrongDark: hexToRgba(mixHexColors(darkStart, darkEnd, 0.35), 0.96),
    surfaceSubtleDark: hexToRgba(mixHexColors(darkMid, darkEnd, 0.4), 0.8),
    lineDark: hexToRgba(mixHexColors(darkStart, darkEnd, 0.45), 0.12),
    overlayBackdrop: hexToRgba(darkenHex(lightBase, 0.78), 0.34),
    overlayBackdropDark: hexToRgba(mixHexColors(darkStart, darkEnd, 0.5), 0.68),
  };
}

function normalizeHexColor(value, fallback) {
  const text = String(value || "").trim();
  return /^#?[0-9a-fA-F]{6}$/.test(text) ? `#${text.replace("#", "")}` : fallback;
}

function mixHexColors(leftHex, rightHex, ratio) {
  const left = hexToRgb(leftHex);
  const right = hexToRgb(rightHex);
  const mix = (leftValue, rightValue) => Math.round(leftValue * (1 - ratio) + rightValue * ratio);
  return rgbToHex(mix(left.r, right.r), mix(left.g, right.g), mix(left.b, right.b));
}

function darkenHex(hex, factor) {
  const rgb = hexToRgb(hex);
  return rgbToHex(
    Math.round(rgb.r * (1 - factor)),
    Math.round(rgb.g * (1 - factor)),
    Math.round(rgb.b * (1 - factor))
  );
}

function hexToRgba(hex, alpha) {
  const rgb = hexToRgb(hex);
  return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${alpha})`;
}

function hexToRgb(hex) {
  const normalized = normalizeHexColor(hex, "#000000").slice(1);
  return {
    r: Number.parseInt(normalized.slice(0, 2), 16),
    g: Number.parseInt(normalized.slice(2, 4), 16),
    b: Number.parseInt(normalized.slice(4, 6), 16),
  };
}

function rgbToHex(r, g, b) {
  const format = (value) => Math.max(0, Math.min(255, value)).toString(16).padStart(2, "0");
  return `#${format(r)}${format(g)}${format(b)}`;
}
