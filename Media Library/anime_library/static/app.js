const DEFAULT_BODY_FONT = '"Trebuchet MS", "Segoe UI", sans-serif';
const DEFAULT_DISPLAY_FONT = '"Bahnschrift", "Segoe UI", sans-serif';

const state = {
  config: null,
  catalog: { items: [], issues: [] },
  sourceAvailability: [],
  search: "",
  selectedYears: new Set(),
  selectedTags: new Set(),
  uiSections: { years: true, tags: true, advanced: false },
  selectedSeasonKeys: {},
  metadataCandidatesByItem: {},
  metadataMatchMessages: {},
  manualBangumiUrls: {},
  setupPaths: [],
  lastFinishedAt: null,
  scanStatus: {},
  logPath: "",
  logLines: [],
  detailMessage: "",
};

const elements = {};
let detailOverlayHideTimer = 0;

document.addEventListener("DOMContentLoaded", () => {
  captureElements();
  bindEvents();
  loadBootstrap();
  setInterval(pollScanStatus, 3000);
});

function captureElements() {
  elements.layoutShell = document.getElementById("layoutShell");
  elements.setupView = document.getElementById("setupView");
  elements.libraryView = document.getElementById("libraryView");
  elements.heroCard = document.getElementById("heroCard");
  elements.setupPathList = document.getElementById("setupPathList");
  elements.yearChips = document.getElementById("yearChips");
  elements.tagChips = document.getElementById("tagChips");
  elements.posterGrid = document.getElementById("posterGrid");
  elements.emptyState = document.getElementById("emptyState");
  elements.libraryStats = document.getElementById("libraryStats");
  elements.sourceAvailability = document.getElementById("sourceAvailability");
  elements.scanMessage = document.getElementById("scanMessage");
  elements.secondaryStatusLabel = document.getElementById("secondaryStatusLabel");
  elements.visibleCount = document.getElementById("visibleCount");
  elements.heroTitle = document.getElementById("heroTitle");
  elements.heroSubtitle = document.getElementById("heroSubtitle");
  elements.searchInput = document.getElementById("searchInput");
  elements.diagnosticsCard = document.getElementById("diagnosticsCard");
  elements.diagnosticsSummary = document.getElementById("diagnosticsSummary");
  elements.scanErrorText = document.getElementById("scanErrorText");
  elements.diagnosticsLogs = document.getElementById("diagnosticsLogs");
  elements.advancedSummary = document.getElementById("advancedSummary");
  elements.advancedBody = document.getElementById("advancedBody");
  elements.advancedToggleButton = document.getElementById("advancedToggleButton");
  elements.advancedToggleIndicator = document.getElementById("advancedToggleIndicator");
  elements.yearsToggleButton = document.getElementById("yearsToggleButton");
  elements.yearsToggleIndicator = document.getElementById("yearsToggleIndicator");
  elements.yearsGroupBody = document.getElementById("yearsGroupBody");
  elements.tagsToggleButton = document.getElementById("tagsToggleButton");
  elements.tagsToggleIndicator = document.getElementById("tagsToggleIndicator");
  elements.tagsGroupBody = document.getElementById("tagsGroupBody");
  elements.detailOverlay = document.getElementById("detailOverlay");
  elements.detailBackdrop = document.getElementById("detailBackdrop");
  elements.detailModal = document.getElementById("detailModal");
}

function bindEvents() {
  document.addEventListener("click", (event) => {
    const button = event.target.closest(
      ".pill-button, .segment-button, .icon-button, .episode-button, .episode-tile, .season-selector-button, .candidate-action, .filter-group-toggle, .advanced-toggle"
    );
    if (button) {
      triggerButtonAnimation(button);
    }
  });
  document.getElementById("filterToggle").addEventListener("click", (event) => {
    const collapsed = elements.layoutShell.classList.toggle("drawer-collapsed");
    event.currentTarget.setAttribute("aria-expanded", String(!collapsed));
  });
  elements.yearsToggleButton.addEventListener("click", () => {
    toggleSection("years");
  });
  elements.tagsToggleButton.addEventListener("click", () => {
    toggleSection("tags");
  });
  elements.advancedToggleButton.addEventListener("click", () => {
    toggleSection("advanced");
  });
  document.getElementById("settingsButton").addEventListener("click", () => {
    window.open("/settings", "anime-library-settings", "popup=yes,width=1040,height=920");
  });
  document.getElementById("scanButton").addEventListener("click", async () => {
    await api("/api/scan/start", { method: "POST", body: { refresh_metadata: false } });
    await pollScanStatus();
  });
  document.getElementById("setupAddPathButton").addEventListener("click", addSetupPath);
  document.getElementById("setupStartButton").addEventListener("click", saveSetup);
  document.getElementById("clearYearsButton").addEventListener("click", () => {
    state.selectedYears.clear();
    renderLibrary();
  });
  document.getElementById("clearTagsButton").addEventListener("click", () => {
    state.selectedTags.clear();
    renderLibrary();
  });
  elements.searchInput.addEventListener("input", (event) => {
    state.search = event.target.value.trim().toLowerCase();
    renderLibrary();
  });
  elements.detailBackdrop.addEventListener("click", closeDetailOverlay);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !elements.detailOverlay.classList.contains("hidden")) {
      closeDetailOverlay();
    }
  });
  window.addEventListener("hashchange", renderDetailOverlay);
  window.addEventListener("focus", () => {
    loadBootstrap({ quiet: true });
  });
  window.addEventListener("message", (event) => {
    if (event.data && event.data.type === "settings-saved") {
      loadBootstrap({ quiet: true });
    }
  });
}

async function loadBootstrap(options = {}) {
  try {
    const data = await api("/api/bootstrap");
    state.config = data.config;
    state.catalog = data.catalog || { items: [], issues: [] };
    state.sourceAvailability = data.source_availability || [];
    state.setupPaths = [...(data.config.library_paths || [])];
    state.lastFinishedAt = data.scan_status?.last_finished_at || state.lastFinishedAt;
    state.scanStatus = data.scan_status || {};
    state.logPath = data.log_path || "";
    applyAppearance();
    renderSetup(data.needs_setup);
    renderLibrary();
    updateScanStatus(state.scanStatus);
    renderDetailOverlay();
    if (shouldShowDiagnostics()) {
      await loadDiagnostics({ quiet: true });
    }
  } catch (error) {
    if (!options.quiet) {
      elements.heroSubtitle.textContent = error.message || "Unable to load the library.";
    }
  }
}

function applyAppearance() {
  const appearance = state.config?.appearance || {};
  const mode = appearance.theme_mode || "system";
  const accent = appearance.accent || "sunrise";
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const resolvedTheme = mode === "system" ? (prefersDark ? "dark" : "light") : mode;
  const backgroundStart = appearance.background_start || "#fff5ef";
  const backgroundEnd = appearance.background_end || "#fff0e6";
  const colors = buildBackgroundPalette(backgroundStart, backgroundEnd);
  document.documentElement.dataset.theme = resolvedTheme;
  document.body.dataset.theme = resolvedTheme;
  document.documentElement.dataset.accent = accent;
  document.documentElement.style.setProperty("--font-body", appearance.font_body || DEFAULT_BODY_FONT);
  document.documentElement.style.setProperty("--font-display", appearance.font_display || DEFAULT_DISPLAY_FONT);
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
  document.documentElement.style.setProperty("--surface", colors.surface);
  document.documentElement.style.setProperty("--surface-strong", colors.surfaceStrong);
  document.documentElement.style.setProperty("--surface-subtle", colors.surfaceSubtle);
  document.documentElement.style.setProperty("--line", colors.line);
  document.documentElement.style.setProperty("--surface-dark", colors.surfaceDark);
  document.documentElement.style.setProperty("--surface-strong-dark", colors.surfaceStrongDark);
  document.documentElement.style.setProperty("--surface-subtle-dark", colors.surfaceSubtleDark);
  document.documentElement.style.setProperty("--line-dark", colors.lineDark);
  document.documentElement.style.setProperty("--overlay-backdrop", colors.overlayBackdrop);
  document.documentElement.style.setProperty("--overlay-backdrop-dark", colors.overlayBackdropDark);
}

function renderSetup(needsSetup) {
  elements.setupView.classList.toggle("hidden", !needsSetup);
  elements.libraryView.classList.toggle("hidden", !!needsSetup);
  renderPathList(elements.setupPathList, state.setupPaths, (index) => {
    state.setupPaths.splice(index, 1);
    renderSetup(true);
  });
}

function renderPathList(container, paths, onRemove) {
  container.innerHTML = "";
  if (!paths.length) {
    container.innerHTML = `<div class="path-row"><p>No folders selected yet.</p></div>`;
    return;
  }
  paths.forEach((path, index) => {
    const row = document.createElement("div");
    row.className = "path-row";
    row.innerHTML = `
      <div>
        <strong>${escapeHtml(path)}</strong>
      </div>
      <button class="text-button">Remove</button>
    `;
    row.querySelector("button").addEventListener("click", () => onRemove(index));
    container.appendChild(row);
  });
}

async function addSetupPath() {
  const result = await api("/api/system/select-folder", { method: "POST", body: {} });
  if (!result.path) {
    return;
  }
  if (!state.setupPaths.includes(result.path)) {
    state.setupPaths.push(result.path);
    renderSetup(true);
  }
}

async function saveSetup() {
  if (!state.setupPaths.length) {
    elements.heroSubtitle.textContent = "Add at least one folder before scanning.";
    return;
  }
  await api("/api/settings/save", {
    method: "POST",
    body: {
      library_paths: state.setupPaths,
      theme_mode: state.config?.appearance?.theme_mode || "system",
      accent: state.config?.appearance?.accent || "sunrise",
      font_body: state.config?.appearance?.font_body || DEFAULT_BODY_FONT,
      font_display: state.config?.appearance?.font_display || DEFAULT_DISPLAY_FONT,
      background_start: state.config?.appearance?.background_start || "#fff5ef",
      background_end: state.config?.appearance?.background_end || "#fff0e6",
      mal_client_id: state.config?.providers?.mal_client_id || "",
      tmdb_api_key: state.config?.providers?.tmdb_api_key || "",
      tmdb_read_access_token: state.config?.providers?.tmdb_read_access_token || "",
      scan_after_save: true,
    },
  });
  await loadBootstrap();
}

function renderLibrary() {
  const items = filteredItems();
  const allItems = state.catalog.items || [];
  elements.libraryStats.textContent = `${allItems.length} titles`;

  renderScanBanner();
  renderSourceAvailability();
  renderFilterChips(allItems);
  renderPosterGrid(items);
  renderDiagnostics();
  renderAdvancedSummary();
  renderSectionVisibility();
  renderDetailOverlay();
}

function renderScanBanner() {
  const running = Boolean(state.scanStatus?.running);
  const visibleItems = filteredItems().length;
  const current = Number(state.scanStatus?.current || 0);
  const total = Number(state.scanStatus?.total || 0);
  const safeCurrent = total ? Math.min(current, total) : current;
  const scanMessage = state.scanStatus?.message || "Idle";

  elements.heroCard.classList.toggle("scan-banner-hidden", !running);
  elements.heroCard.setAttribute("aria-hidden", String(!running));
  elements.scanMessage.textContent = scanMessage;
  elements.secondaryStatusLabel.textContent = running ? "Progress" : "Visible";
  elements.visibleCount.textContent = running ? (total ? `${safeCurrent} / ${total}` : "Starting") : `${visibleItems} visible`;

  if (!running) {
    return;
  }

  elements.heroTitle.textContent = "Updating library";
  elements.heroSubtitle.textContent = total
    ? `${scanMessage}. ${safeCurrent} of ${total} folders checked so far.`
    : `${scanMessage}. Preparing folders and metadata sources.`;
}

function renderSourceAvailability() {
  elements.sourceAvailability.innerHTML = "";
  for (const source of state.sourceAvailability) {
    const badge = document.createElement("div");
    badge.className = `source-badge ${source.enabled ? "enabled" : "disabled"}`;
    badge.innerHTML = `<strong>${escapeHtml(source.name)}</strong><span class="source-note">${escapeHtml(
      source.reason || (source.enabled ? "Ready" : "Unavailable")
    )}</span>`;
    elements.sourceAvailability.appendChild(badge);
  }
}

function renderFilterChips(items) {
  const yearCounts = new Map();
  const tagCounts = new Map();
  for (const item of items) {
    if (item.year) {
      yearCounts.set(item.year, (yearCounts.get(item.year) || 0) + 1);
    }
    for (const tag of item.tags || []) {
      tagCounts.set(tag, (tagCounts.get(tag) || 0) + 1);
    }
  }

  renderChipGroup(
    elements.yearChips,
    [...yearCounts.entries()].sort((left, right) => right[0] - left[0]),
    state.selectedYears,
    (value) => toggleSetValue(state.selectedYears, String(value))
  );
  renderChipGroup(
    elements.tagChips,
    [...tagCounts.entries()].sort((left, right) => right[1] - left[1]).slice(0, 40),
    state.selectedTags,
    (value) => toggleSetValue(state.selectedTags, value)
  );
}

function renderChipGroup(container, entries, selectedSet, onToggle) {
  container.innerHTML = "";
  if (!entries.length) {
    container.innerHTML = `<div class="path-row"><p>No filters yet.</p></div>`;
    return;
  }
  for (const [value, count] of entries) {
    const button = document.createElement("button");
    button.className = `chip ${selectedSet.has(String(value)) ? "active" : ""}`;
    button.textContent = `${value} (${count})`;
    button.addEventListener("click", () => {
      onToggle(String(value));
      renderLibrary();
    });
    container.appendChild(button);
  }
}

function renderPosterGrid(items) {
  elements.posterGrid.innerHTML = "";
  elements.emptyState.classList.toggle("hidden", items.length > 0);
  if (!items.length) {
    return;
  }
  for (const item of items) {
    const card = document.createElement("article");
    card.className = "poster-card";
    card.innerHTML = `
      <div class="poster-frame">${posterMarkup(item)}</div>
      <div class="poster-copy">
        <h3>${escapeHtml(item.resolved_title || item.folder_name)}</h3>
        <p>${escapeHtml(item.year ? String(item.year) : "Year unknown")} · ${escapeHtml(
      item.episodes?.length ? `${item.episodes.length} video files` : "No episodes found"
    )}</p>
        <p>${escapeHtml((item.tags || []).slice(0, 3).join(" • ") || item.cleaned_title || item.folder_name)}</p>
      </div>
    `;
    card.addEventListener("click", () => {
      window.location.hash = `item/${item.id}`;
    });
    elements.posterGrid.appendChild(card);
  }
  wirePosterFallbacks(elements.posterGrid);
}

function renderDetailOverlay() {
  const hash = window.location.hash.replace(/^#/, "");
  if (!hash.startsWith("item/")) {
    hideDetailOverlay();
    return;
  }

  const itemId = hash.split("/")[1];
  const item = findItem(itemId);
  if (!item) {
    closeDetailOverlay();
    return;
  }

  const sourceLinks = Object.entries(item.sources || {})
    .map(
      ([name, source]) =>
        `<a class="chip" href="${escapeAttribute(source.url)}" target="_blank" rel="noreferrer">${escapeHtml(
          `${name}: ${source.title || "match"}`
        )}</a>`
    )
    .join("");
  const formDefaults = editableDefaults(item);
  const seasons = normalizeClientSeasons(item);
  const override = item.user_override || {};
  const lockedSource = formatLockedSourceLabel(override);
  const matchMessage = state.metadataMatchMessages[item.id] || "";
  const bangumiUrl =
    state.manualBangumiUrls[item.id] ||
    (override.manual_source_provider === "bangumi" && override.manual_source_id
      ? `https://bangumi.tv/subject/${override.manual_source_id}`
      : "");

  elements.detailModal.innerHTML = `
    <div class="detail-toolbar">
      <div>
        <p class="eyebrow">Details</p>
        <h2>${escapeHtml(item.resolved_title || item.folder_name)}</h2>
      </div>
      <div class="detail-toolbar-actions">
        <button class="pill-button tonal" id="closeDetailButton">Close</button>
      </div>
    </div>
    <div class="detail-layout">
      <div class="detail-stack">
        <div class="detail-poster">${posterMarkup(item)}</div>
        <div class="panel subtle cover-controls">
          <div class="section-heading">
            <h3>Cover</h3>
            <p>${escapeHtml(item.custom_cover ? "Custom cover active." : "Using online or fallback art.")}</p>
          </div>
          <div class="button-row">
            <button class="pill-button tonal" id="chooseCoverButton">Choose Cover</button>
            <button class="pill-button tonal" id="clearCoverButton" ${item.custom_cover ? "" : "disabled"}>Use Online Cover</button>
          </div>
        </div>
        <div class="panel subtle detail-editor">
          <h3>Quick Facts</h3>
          <p><strong>Year:</strong> ${escapeHtml(item.year ? String(item.year) : "Unknown")}</p>
          <p><strong>Known as:</strong> ${escapeHtml((item.known_as || item.aliases || []).join(", ") || "None")}</p>
          <p><strong>Producers:</strong> ${escapeHtml((item.producers || []).join(", ") || "Unknown")}</p>
          <p><strong>Directors:</strong> ${escapeHtml((item.directors || []).join(", ") || "Unknown")}</p>
        </div>
      </div>
      <div class="detail-stack">
        <section class="detail-meta">
          <p>${escapeHtml(item.overview || "No overview found yet for this folder.")}</p>
          <div class="meta-chip-row">
            ${(item.tags || []).map((tag) => `<span class="chip">${escapeHtml(tag)}</span>`).join("") || '<span class="chip">No tags</span>'}
          </div>
        </section>
        <section class="detail-editor panel subtle" id="episodeBrowser">
          <div class="section-heading">
            <h3>Episodes</h3>
            <p>Select a file to play</p>
          </div>
          ${renderEpisodeBrowser(item.id, seasons)}
        </section>
        <section class="detail-editor panel subtle collapsible-detail collapsed" id="modifySection">
          <button class="panel-toggle" id="modifyToggleButton" type="button" aria-expanded="false">
            <div>
              <h3>Modify</h3>
              <p>Expand to refine metadata, cover, and online matches.</p>
            </div>
            <span class="panel-toggle-indicator">▾</span>
          </button>
          <div class="panel-body hidden" id="modifyBody">
            <div class="panel subtle cover-controls">
              <div class="section-heading">
                <h3>Cover</h3>
                <p>${escapeHtml(item.custom_cover ? "Custom cover active." : "Using online or fallback art.")}</p>
              </div>
              <div class="button-row">
                <button class="pill-button tonal" id="chooseCoverButton">Choose Cover</button>
                <button class="pill-button tonal" id="clearCoverButton" ${item.custom_cover ? "" : "disabled"}>Use Online Cover</button>
              </div>
            </div>
            <section class="detail-meta">
              <h3>Cross-check</h3>
              <div class="meta-chip-row">${sourceLinks || '<span class="chip">No online match</span>'}</div>
              <p>${escapeHtml((item.cross_check?.notes || []).join(" "))}</p>
            </section>
            <section class="detail-editor panel subtle">
              <div class="section-heading">
                <h3>Custom Metadata</h3>
                <p>Reset clears edit fields but keeps a locked source or custom cover. Clear All removes every local override for this folder.</p>
              </div>
              <div class="field-grid">
                <label class="field-shell">
                  <span>Title</span>
                  <input id="editTitleInput" type="text" value="${escapeAttribute(formDefaults.title)}" />
                </label>
                <label class="field-shell">
                  <span>Known As</span>
                  <input id="editKnownAsInput" type="text" value="${escapeAttribute(formDefaults.knownAs)}" placeholder="Comma-separated names" />
                </label>
                <label class="field-shell">
                  <span>Year</span>
                  <input id="editYearInput" type="number" value="${escapeAttribute(formDefaults.year)}" placeholder="e.g. 2009" />
                </label>
                <label class="field-shell">
                  <span>Tags</span>
                  <input id="editTagsInput" type="text" value="${escapeAttribute(formDefaults.tags)}" placeholder="Comma-separated tags" />
                </label>
                <label class="field-shell">
                  <span>Producers</span>
                  <input id="editProducersInput" type="text" value="${escapeAttribute(formDefaults.producers)}" placeholder="Comma-separated studios or producers" />
                </label>
                <label class="field-shell">
                  <span>Directors</span>
                  <input id="editDirectorsInput" type="text" value="${escapeAttribute(formDefaults.directors)}" placeholder="Comma-separated directors" />
                </label>
                <label class="field-shell wide">
                  <span>Overview</span>
                  <textarea id="editOverviewInput" placeholder="Custom synopsis or notes">${escapeHtml(formDefaults.overview)}</textarea>
                </label>
              </div>
              <div class="button-row">
                <button class="pill-button tonal" id="resetMetadataButton">Reset Custom Fields</button>
                <button class="pill-button destructive tonal" id="clearMetadataButton">Clear All Metadata</button>
                <button class="pill-button tonal" id="saveMetadataButton">Save</button>
                <button class="pill-button" id="searchMetadataButton">Search Online</button>
              </div>
              <p id="detailSaveMessage">${escapeHtml(
                state.detailMessage || "Changes stay local and are applied to future searches for this folder."
              )}</p>
            </section>
            <section class="detail-meta match-section">
          <div class="section-heading">
            <h3>Manual Match</h3>
            <p>${escapeHtml(lockedSource || "Choose a source candidate or paste a Bangumi subject URL.")}</p>
          </div>
          <label class="field-shell wide">
            <span>Bangumi URL</span>
            <input
              id="bangumiUrlInput"
              type="url"
              value="${escapeAttribute(bangumiUrl)}"
              placeholder="https://bangumi.tv/subject/147068"
            />
          </label>
          <div class="button-row">
            <button class="pill-button tonal" id="findMatchesButton">Find Matches</button>
            <button class="pill-button tonal" id="fetchBangumiButton">Fetch Bangumi URL</button>
          </div>
          <p id="metadataMatchMessage">${escapeHtml(
            matchMessage || "Search results from MAL, TMDB, and Bangumi will appear here."
          )}</p>
          <div class="candidate-list">
            ${renderMetadataCandidates(item.id)}
          </div>
        </section>
      </div>
    </div>
  `;

  showDetailOverlay();
  wirePosterFallbacks(elements.detailModal);
  document.getElementById("closeDetailButton").addEventListener("click", closeDetailOverlay);
  document.getElementById("chooseCoverButton").addEventListener("click", () => chooseCustomCover(item.id));
  document.getElementById("clearCoverButton").addEventListener("click", () => clearCustomCover(item.id));
  document.getElementById("bangumiUrlInput").addEventListener("input", (event) => {
    state.manualBangumiUrls[item.id] = event.target.value.trim();
  });
  document.getElementById("findMatchesButton").addEventListener("click", () => findMetadataMatches(item.id));
  document.getElementById("fetchBangumiButton").addEventListener("click", () => applyBangumiUrl(item.id));
  document.getElementById("modifyToggleButton")?.addEventListener("click", () => {
    const section = document.getElementById("modifySection");
    const body = document.getElementById("modifyBody");
    if (!section || !body) {
      return;
    }
    const isExpanded = section.classList.toggle("collapsed");
    body.classList.toggle("hidden", isExpanded);
    document.getElementById("modifyToggleButton").setAttribute("aria-expanded", String(!isExpanded));
  });
  elements.detailModal.querySelectorAll(".season-selector-button").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedSeasonKeys[item.id] = button.dataset.seasonKey || "";
      renderDetailOverlay();
    });
  });
  elements.detailModal.querySelectorAll(".candidate-action").forEach((button) => {
    button.addEventListener("click", () => {
      applyMetadataCandidate(item.id, button.dataset.provider || "", button.dataset.sourceId || "");
    });
  });
  elements.detailModal.querySelectorAll(".episode-tile").forEach((button) => {
    button.addEventListener("click", () => {
      api("/api/play", { method: "POST", body: { path: button.dataset.path } });
    });
  });
  document.getElementById("saveMetadataButton").addEventListener("click", () => saveItemOverride(item.id));
  document.getElementById("searchMetadataButton").addEventListener("click", () => saveItemOverride(item.id, "search"));
  document.getElementById("resetMetadataButton").addEventListener("click", () => saveItemOverride(item.id, "reset-fields"));
  document.getElementById("clearMetadataButton").addEventListener("click", () => saveItemOverride(item.id, "clear-all"));
  if (state.detailMessage) {
    triggerMessageFade(document.getElementById("detailSaveMessage"));
  }
}

function renderEpisodeBrowser(itemId, seasons) {
  if (!seasons.length) {
    return '<div class="path-row"><p>No playable video files were found.</p></div>';
  }
  const activeSeason = getActiveSeason(itemId, seasons);
  const seasonButtons = seasons
    .map(
      (season) => `
        <button
          class="season-selector-button ${season.key === activeSeason.key ? "active" : ""}"
          data-season-key="${escapeAttribute(season.key)}"
        >
          ${escapeHtml(season.label)}
        </button>
      `
    )
    .join("");
  const episodeTiles = activeSeason.episodes
    .map(
      (episode) => `
        <button class="episode-tile" data-path="${escapeAttribute(episode.path)}" title="${escapeAttribute(episode.relative_path)}">
          <strong>${escapeHtml(formatEpisodeBrowseLabel(episode))}</strong>
          <span>${escapeHtml(episode.relative_path)}</span>
        </button>
      `
    )
    .join("");
  return `
    <div class="season-selector-row">${seasonButtons}</div>
    <div class="season-block">
      <div class="section-heading">
        <h4>${escapeHtml(activeSeason.label)}</h4>
        <p>${escapeHtml(`${activeSeason.episodes.length} episode${activeSeason.episodes.length === 1 ? "" : "s"}`)}</p>
      </div>
      <div class="episode-grid">${episodeTiles}</div>
    </div>
  `;
}

function normalizeClientSeasons(item) {
  if (item.seasons && item.seasons.length) {
    return item.seasons.map((season, index) => ({
      ...season,
      key: season.key || `season-${season.season_number || index + 1}`,
      label: season.label || `Season ${season.season_number || index + 1}`,
      episodes: (season.episodes || []).map((episode) => ({
        ...episode,
        browse_label: episode.browse_label || formatEpisodeBrowseLabel(episode),
      })),
    }));
  }
  if (item.episodes && item.episodes.length) {
    return [
      {
        key: "episodes",
        label: "Episodes",
        episodes: item.episodes.map((episode) => ({
          ...episode,
          browse_label: episode.browse_label || formatEpisodeBrowseLabel(episode),
        })),
      },
    ];
  }
  return [];
}

function editableDefaults(item) {
  const override = item.user_override || {};
  return {
    title: override.title || item.resolved_title || "",
    knownAs: (override.known_as || item.known_as || item.aliases || []).join(", "),
    year: override.year ?? item.year ?? "",
    tags: (override.tags || item.tags || []).join(", "),
    producers: (override.producers || item.producers || []).join(", "),
    directors: (override.directors || item.directors || []).join(", "),
    overview: override.overview || item.overview || "",
  };
}

async function saveItemOverride(itemId, mode = "save") {
  const message = document.getElementById("detailSaveMessage");
  const actionMap = {
    save: {
      activeButtonId: "saveMetadataButton",
      payload: {
        ...collectEditableMetadataPayload(),
        refresh_metadata: false,
      },
      progressMessage: "Saving custom metadata...",
      successMessage: "Custom metadata saved locally. Use Search when you want to refresh online metadata.",
    },
    search: {
      activeButtonId: "searchMetadataButton",
      payload: {
        ...collectEditableMetadataPayload(),
        refresh_metadata: true,
      },
      progressMessage: "Saving changes and searching...",
      successMessage: null,
    },
    "reset-fields": {
      activeButtonId: "resetMetadataButton",
      payload: { refresh_metadata: false, reset_fields: true },
      progressMessage: "Resetting custom fields...",
      successMessage: "Custom fields cleared. Locked source and custom cover stay in place.",
    },
    "clear-all": {
      activeButtonId: "clearMetadataButton",
      payload: { refresh_metadata: false, reset_override: true },
      progressMessage: "Clearing all local metadata...",
      successMessage: "All local metadata, manual matches, and custom cover were cleared for this folder.",
    },
  };
  const action = actionMap[mode] || actionMap.save;

  try {
    setMetadataButtonsBusy(true, action.activeButtonId);
    message.textContent = action.progressMessage;
    triggerMessageFade(message);
    const result = await api(`/api/library/${itemId}/override`, { method: "POST", body: action.payload });
    state.catalog = result.catalog || state.catalog;
    if (mode === "reset-fields" || mode === "clear-all") {
      state.metadataCandidatesByItem[itemId] = [];
      state.metadataMatchMessages[itemId] = "";
      state.manualBangumiUrls[itemId] = "";
    }
    state.detailMessage =
      mode === "search" ? buildSearchCompleteMessage(result.item || findItem(itemId)) : action.successMessage;
    renderLibrary();
  } catch (error) {
    state.detailMessage = error.message || "Unable to save custom metadata.";
    renderDetailOverlay();
  } finally {
    setMetadataButtonsBusy(false);
  }
}

function closeDetailOverlay() {
  state.detailMessage = "";
  if (window.location.hash) {
    window.location.hash = "";
    return;
  }
  hideDetailOverlay();
}

function findItem(itemId) {
  return (state.catalog.items || []).find((entry) => entry.id === itemId) || null;
}

function filteredItems() {
  const query = state.search;
  return (state.catalog.items || []).filter((item) => {
    if (state.selectedYears.size && !state.selectedYears.has(String(item.year || ""))) {
      return false;
    }
    if (state.selectedTags.size) {
      const tags = new Set((item.tags || []).map((tag) => String(tag)));
      for (const selected of state.selectedTags) {
        if (!tags.has(selected)) {
          return false;
        }
      }
    }
    if (!query) {
      return true;
    }
    const haystack = [
      item.resolved_title,
      item.folder_name,
      item.cleaned_title,
      ...(item.known_as || []),
      ...(item.aliases || []),
      ...(item.tags || []),
      ...(item.producers || []),
      ...(item.directors || []),
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });
}

function posterMarkup(item) {
  const src = item.custom_cover || item.poster_cached || item.poster_url;
  const title = item.resolved_title || item.folder_name || "Anime";
  if (!src) {
    return posterFallbackMarkup(title);
  }
  return `<img src="${escapeAttribute(src)}" alt="${escapeAttribute(title)} poster" loading="lazy" data-title="${escapeAttribute(title)}" />`;
}

function posterFallbackMarkup(title) {
  return `
    <div class="poster-placeholder">
      <div class="poster-icon" aria-hidden="true">
        <span class="poster-kana">アニメ</span>
      </div>
      <div class="poster-placeholder-title">${escapeHtml(title)}</div>
    </div>
  `;
}

function wirePosterFallbacks(scope) {
  scope.querySelectorAll("img[data-title]").forEach((image) => {
    const replace = () => {
      image.outerHTML = posterFallbackMarkup(image.dataset.title || "Anime");
    };
    image.addEventListener("error", replace, { once: true });
    if (image.complete && image.naturalWidth === 0) {
      replace();
    }
  });
}

function toggleSetValue(setRef, value) {
  if (setRef.has(String(value))) {
    setRef.delete(String(value));
  } else {
    setRef.add(String(value));
  }
}

function updateScanStatus(status) {
  state.scanStatus = status || {};
  renderScanBanner();
  if (!state.scanStatus.running && shouldShowDiagnostics()) {
    loadDiagnostics({ quiet: true });
  }
  if (
    !state.scanStatus.running &&
    state.scanStatus.last_finished_at &&
    state.scanStatus.last_finished_at !== state.lastFinishedAt
  ) {
    state.lastFinishedAt = state.scanStatus.last_finished_at;
    loadBootstrap({ quiet: true });
  }
}

async function loadDiagnostics(options = {}) {
  try {
    const logs = await api("/api/logs?limit=120");
    state.logPath = logs.path || state.logPath;
    state.logLines = logs.lines || [];
    renderDiagnostics();
  } catch (error) {
    if (!options.quiet) {
      elements.diagnosticsLogs.textContent = error.message || "Unable to load logs.";
    }
  }
}

function renderDiagnostics() {
  const issues = state.catalog.issues || [];
  const error = state.scanStatus?.error || "";
  const show = shouldShowDiagnostics();
  elements.diagnosticsCard.classList.toggle("diagnostics-quiet", !show);
  const parts = [];
  if (error) {
    parts.push("Scan failed");
  }
  if (issues.length) {
    parts.push(`${issues.length} warning${issues.length === 1 ? "" : "s"}`);
  }
  elements.diagnosticsSummary.textContent = parts.join(" · ") || "Latest scan is clean";
  elements.scanErrorText.textContent = error || issues.join(" | ") || "No warnings or scan errors were recorded.";
  elements.diagnosticsLogs.textContent = show
    ? state.logLines.length
      ? state.logLines.join("\n")
      : "No log entries captured yet."
    : "Run a scan and reopen Advanced if you need recent diagnostics.";
}

function shouldShowDiagnostics() {
  return Boolean(state.scanStatus?.error || (state.catalog.issues || []).length);
}

function renderAdvancedSummary() {
  const diagnosticsBits = [];
  const enabledSources = state.sourceAvailability.filter((source) => source.enabled).length;
  diagnosticsBits.push(`${enabledSources} source${enabledSources === 1 ? "" : "s"} ready`);
  if (state.scanStatus?.error) {
    diagnosticsBits.push("scan failed");
  } else if ((state.catalog.issues || []).length) {
    diagnosticsBits.push(`${state.catalog.issues.length} warning${state.catalog.issues.length === 1 ? "" : "s"}`);
  } else {
    diagnosticsBits.push("all clear");
  }
  elements.advancedSummary.textContent = diagnosticsBits.join(" · ");
}

function toggleSection(sectionKey) {
  state.uiSections[sectionKey] = !state.uiSections[sectionKey];
  renderSectionVisibility();
}

function renderSectionVisibility() {
  const sectionMap = [
    ["years", elements.yearsToggleButton, elements.yearsGroupBody, elements.yearsToggleIndicator],
    ["tags", elements.tagsToggleButton, elements.tagsGroupBody, elements.tagsToggleIndicator],
    ["advanced", elements.advancedToggleButton, elements.advancedBody, elements.advancedToggleIndicator],
  ];
  for (const [sectionKey, button, body, indicator] of sectionMap) {
    const open = Boolean(state.uiSections[sectionKey]);
    button?.setAttribute("aria-expanded", String(open));
    body?.classList.toggle("hidden", !open);
    indicator?.classList.toggle("is-open", open);
  }
}

function buildSearchCompleteMessage(item) {
  const count = item?.cross_check?.provider_count || 0;
  if (count > 0) {
    return `Search complete. Cross-checked ${count} source${count === 1 ? "" : "s"} with your saved hints.`;
  }
  return "Search completed. No stronger online match was found, but your saved fields remain applied.";
}

function renderMetadataCandidates(itemId) {
  const candidates = state.metadataCandidatesByItem[itemId] || [];
  if (!candidates.length) {
    return `<div class="path-row"><p>No manual matches loaded yet.</p></div>`;
  }
  return candidates
    .map(
      (candidate) => `
        <article class="candidate-card">
          <div class="candidate-copy">
            <div class="candidate-head">
              <strong>${escapeHtml(candidate.title || "Untitled")}</strong>
              <span class="chip">${escapeHtml(candidate.provider)}</span>
            </div>
            <p>${escapeHtml(
              [
                candidate.year ? String(candidate.year) : "",
                candidate.score ? `Score ${Math.round(Number(candidate.score) * 100)}%` : "",
              ]
                .filter(Boolean)
                .join(" · ") || "No year"
            )}</p>
            <p>${escapeHtml(compactText(candidate.overview || (candidate.titles || []).slice(0, 4).join(", "), 180))}</p>
            <a class="text-button candidate-link" href="${escapeAttribute(candidate.url)}" target="_blank" rel="noreferrer">Open source</a>
          </div>
          <button
            class="pill-button candidate-action"
            data-provider="${escapeAttribute(candidate.provider)}"
            data-source-id="${escapeAttribute(candidate.source_id)}"
          >
            Use This
          </button>
        </article>
      `
    )
    .join("");
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
  if (!element) {
    return;
  }
  element.classList.remove("message-fade");
  void element.offsetWidth;
  element.classList.add("message-fade");
}

function getActiveSeason(itemId, seasons) {
  const storedKey = state.selectedSeasonKeys[itemId];
  const activeSeason = seasons.find((season) => season.key === storedKey) || seasons[0];
  if (activeSeason) {
    state.selectedSeasonKeys[itemId] = activeSeason.key;
  }
  return activeSeason;
}

function formatEpisodeBrowseLabel(episode) {
  if (episode.browse_label) {
    return episode.browse_label;
  }
  if (episode.episode_number) {
    return `Ep ${String(episode.episode_number).padStart(2, "0")}`;
  }
  return episode.label || "Play";
}

function showDetailOverlay() {
  window.clearTimeout(detailOverlayHideTimer);
  elements.detailOverlay.classList.remove("hidden");
  elements.detailOverlay.classList.remove("is-closing");
  document.body.classList.add("modal-open");
  window.requestAnimationFrame(() => {
    elements.detailOverlay.classList.add("is-visible");
  });
}

function hideDetailOverlay() {
  window.clearTimeout(detailOverlayHideTimer);
  if (elements.detailOverlay.classList.contains("hidden")) {
    elements.detailModal.innerHTML = "";
    document.body.classList.remove("modal-open");
    return;
  }
  elements.detailOverlay.classList.remove("is-visible");
  elements.detailOverlay.classList.add("is-closing");
  detailOverlayHideTimer = window.setTimeout(() => {
    if (window.location.hash.replace(/^#/, "").startsWith("item/")) {
      return;
    }
    elements.detailOverlay.classList.add("hidden");
    elements.detailOverlay.classList.remove("is-closing");
    elements.detailModal.innerHTML = "";
    document.body.classList.remove("modal-open");
  }, 240);
}

function setMetadataButtonsBusy(isBusy, activeButtonId = "") {
  const buttons = [
    ["resetMetadataButton", "Resetting..."],
    ["clearMetadataButton", "Clearing..."],
    ["saveMetadataButton", "Saving..."],
    ["searchMetadataButton", "Searching..."],
  ];
  for (const [id, busyLabel] of buttons) {
    const button = document.getElementById(id);
    if (!button) {
      continue;
    }
    const originalLabel = button.dataset.label || button.textContent;
    button.dataset.label = originalLabel;
    button.disabled = isBusy;
    button.textContent = isBusy && id === activeButtonId ? busyLabel : originalLabel;
  }
}

async function findMetadataMatches(itemId) {
  const message = document.getElementById("metadataMatchMessage");
  try {
    setMatchButtonsBusy(true, "findMatchesButton");
    message.textContent = "Searching metadata candidates...";
    triggerMessageFade(message);
    const result = await api(`/api/library/${itemId}/metadata/candidates`, {
      method: "POST",
      body: collectEditableMetadataPayload(),
    });
    state.metadataCandidatesByItem[itemId] = result.candidates || [];
    state.metadataMatchMessages[itemId] = state.metadataCandidatesByItem[itemId].length
      ? "Choose the metadata entry you want to lock to this folder."
      : "No candidate matches were found from the current fields.";
    renderDetailOverlay();
  } catch (error) {
    state.metadataMatchMessages[itemId] = error.message || "Unable to search metadata candidates.";
    renderDetailOverlay();
  } finally {
    setMatchButtonsBusy(false);
  }
}

async function applyMetadataCandidate(itemId, provider, sourceId) {
  const message = document.getElementById("metadataMatchMessage");
  try {
    setMatchButtonsBusy(true);
    message.textContent = "Applying the selected metadata source...";
    triggerMessageFade(message);
    const result = await api(`/api/library/${itemId}/metadata/apply-source`, {
      method: "POST",
      body: {
        ...collectEditableMetadataPayload(),
        provider,
        source_id: sourceId,
      },
    });
    state.catalog = result.catalog || state.catalog;
    state.detailMessage = "Selected metadata source applied. Earlier custom metadata fields were replaced by the chosen source.";
    state.metadataMatchMessages[itemId] = "Manual source locked for this folder and now drives the displayed metadata.";
    renderLibrary();
  } catch (error) {
    state.metadataMatchMessages[itemId] = error.message || "Unable to apply the selected metadata source.";
    renderDetailOverlay();
  } finally {
    setMatchButtonsBusy(false);
  }
}

async function applyBangumiUrl(itemId) {
  const message = document.getElementById("metadataMatchMessage");
  try {
    setMatchButtonsBusy(true, "fetchBangumiButton");
    message.textContent = "Fetching metadata from the Bangumi URL...";
    triggerMessageFade(message);
    const result = await api(`/api/library/${itemId}/metadata/apply-source`, {
      method: "POST",
      body: {
        ...collectEditableMetadataPayload(),
        bangumi_url: document.getElementById("bangumiUrlInput").value.trim(),
      },
    });
    state.catalog = result.catalog || state.catalog;
    state.detailMessage = "Bangumi subject applied. Earlier custom metadata fields were replaced by the selected source.";
    state.metadataMatchMessages[itemId] = "Bangumi source locked for this folder and now drives the displayed metadata.";
    renderLibrary();
  } catch (error) {
    state.metadataMatchMessages[itemId] = error.message || "Unable to fetch metadata from that Bangumi URL.";
    renderDetailOverlay();
  } finally {
    setMatchButtonsBusy(false);
  }
}

function setMatchButtonsBusy(isBusy, activeButtonId = "") {
  const buttons = [
    ["findMatchesButton", "Searching..."],
    ["fetchBangumiButton", "Fetching..."],
  ];
  for (const [id, busyLabel] of buttons) {
    const button = document.getElementById(id);
    if (!button) {
      continue;
    }
    const originalLabel = button.dataset.label || button.textContent;
    button.dataset.label = originalLabel;
    button.disabled = isBusy;
    button.textContent = isBusy && id === activeButtonId ? busyLabel : originalLabel;
  }
  document.querySelectorAll(".candidate-action").forEach((button) => {
    const originalLabel = button.dataset.label || button.textContent;
    button.dataset.label = originalLabel;
    button.disabled = isBusy;
    button.textContent = isBusy ? "Applying..." : originalLabel;
  });
}

async function chooseCustomCover(itemId) {
  const message = document.getElementById("detailSaveMessage");
  try {
    setCoverButtonsBusy(true, "chooseCoverButton");
    message.textContent = "Choosing a custom cover...";
    triggerMessageFade(message);
    const result = await api(`/api/library/${itemId}/cover/select`, { method: "POST", body: {} });
    if (result.cancelled) {
      state.detailMessage = "Cover selection cancelled.";
      renderDetailOverlay();
      return;
    }
    state.catalog = result.catalog || state.catalog;
    state.detailMessage = "Custom cover saved locally.";
    renderLibrary();
  } catch (error) {
    state.detailMessage = error.message || "Unable to save the custom cover.";
    renderDetailOverlay();
  } finally {
    setCoverButtonsBusy(false);
  }
}

async function clearCustomCover(itemId) {
  const message = document.getElementById("detailSaveMessage");
  try {
    setCoverButtonsBusy(true, "clearCoverButton");
    message.textContent = "Clearing the custom cover...";
    triggerMessageFade(message);
    const result = await api(`/api/library/${itemId}/cover/clear`, { method: "POST", body: {} });
    state.catalog = result.catalog || state.catalog;
    state.detailMessage = "Custom cover cleared. Online or fallback art is active again.";
    renderLibrary();
  } catch (error) {
    state.detailMessage = error.message || "Unable to clear the custom cover.";
    renderDetailOverlay();
  } finally {
    setCoverButtonsBusy(false);
  }
}

function setCoverButtonsBusy(isBusy, activeButtonId = "") {
  const buttons = [
    ["chooseCoverButton", "Choosing..."],
    ["clearCoverButton", "Clearing..."],
  ];
  for (const [id, busyLabel] of buttons) {
    const button = document.getElementById(id);
    if (!button) {
      continue;
    }
    const originalLabel = button.dataset.label || button.textContent;
    button.dataset.label = originalLabel;
    button.disabled = isBusy || (id === "clearCoverButton" && !findItem(window.location.hash.split("/")[1])?.custom_cover);
    button.textContent = isBusy && id === activeButtonId ? busyLabel : originalLabel;
  }
}

function collectEditableMetadataPayload() {
  return {
    title: document.getElementById("editTitleInput")?.value.trim() || "",
    known_as: document.getElementById("editKnownAsInput")?.value.trim() || "",
    year: document.getElementById("editYearInput")?.value.trim() || "",
    tags: document.getElementById("editTagsInput")?.value.trim() || "",
    producers: document.getElementById("editProducersInput")?.value.trim() || "",
    directors: document.getElementById("editDirectorsInput")?.value.trim() || "",
    overview: document.getElementById("editOverviewInput")?.value.trim() || "",
  };
}

function formatLockedSourceLabel(override) {
  if (!override?.manual_source_provider || !override?.manual_source_id) {
    return "";
  }
  return `Locked source: ${override.manual_source_provider} ${override.manual_source_id}`;
}

function compactText(value, limit) {
  const text = String(value || "").trim().replace(/\s+/g, " ");
  if (text.length <= limit) {
    return text;
  }
  return `${text.slice(0, limit - 1).trim()}…`;
}

function buildBackgroundPalette(startHex, endHex) {
  const start = normalizeHexColor(startHex, "#fff5ef");
  const end = normalizeHexColor(endHex, "#fff0e6");
  const mid = mixHexColors(start, end, 0.5);
  const lightBase = mixHexColors(start, end, 0.42);
  const darkStart = darkenHex(start, 0.92);
  const darkMid = darkenHex(mid, 0.94);
  const darkEnd = darkenHex(end, 0.96);
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
    darkSpotA: hexToRgba(darkenHex(start, 0.52), 0.28),
    darkSpotB: hexToRgba(darkenHex(end, 0.56), 0.22),
    surface: hexToRgba(mixHexColors(lightBase, "#ffffff", 0.8), 0.8),
    surfaceStrong: hexToRgba(mixHexColors(lightBase, "#ffffff", 0.9), 0.9),
    surfaceSubtle: hexToRgba(mixHexColors(start, "#ffffff", 0.72), 0.62),
    line: hexToRgba(darkenHex(lightBase, 0.7), 0.16),
    surfaceDark: hexToRgba(darkBase, 0.92),
    surfaceStrongDark: hexToRgba(mixHexColors(darkStart, darkEnd, 0.35), 0.96),
    surfaceSubtleDark: hexToRgba(mixHexColors(darkMid, darkEnd, 0.4), 0.8),
    lineDark: hexToRgba(mixHexColors(start, end, 0.45), 0.12),
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
  const format = (value) => clampColor(value).toString(16).padStart(2, "0");
  return `#${format(r)}${format(g)}${format(b)}`;
}

function clampColor(value) {
  return Math.max(0, Math.min(255, value));
}

async function pollScanStatus() {
  try {
    const status = await api("/api/scan/status");
    updateScanStatus(status);
  } catch (_error) {
    return;
  }
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

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll("'", "&#39;");
}
