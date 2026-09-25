// File: house-voice-panel.js
// Version: 3.7.0
// Description: House Voice Manager sidebar panel.
//              Tabs: Events | Groups | History
//              Design: Indeklima Designer – teal #14b8a6 / emerald #34d399

class HouseVoicePanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._version       = "3.7.0";
    this._hass          = null;
    this._events        = {};
    this._groups        = {};
    this._conditions    = {};      // { id: { label, entity_id, state } }
    this._players       = [];
    this._history       = [];
    this._tab           = "events";       // "events" | "groups" | "history" | "chains"
    this._editingId     = null;
    this._editingGroup  = null;
    this._editingCond   = null;    // condition_id being edited
    this._showForm      = false;
    this._showGroupForm = false;
    this._showCondForm  = false;   // condition library flyout
    this._saving        = false;
    this._notification  = null;
    this._notifTimer    = null;
    this._debounceTimer = null;    // for search debounce
    this._searchQuery   = "";
    this._loading       = false;
    this._lastRenderKey = null;  // for render memoization   // global loading state for WS calls
    this._errors        = {};      // { fieldName: 'error message' }
    this._dialog        = null;    // { type: 'export'|'import'|'name', data: {...} }
    this._chains        = {};      // { chainId: { name, status, steps, ... } }
    this._templates     = {};      // { templateId: { name, description, steps } }
    this._currentChain  = null;    // currently active chain
    this._execHistory   = [];      // [ { chainId, timestamp, steps, success, duration } ]
    this._historyFilters = {
      chainId: null,
      status: null,
      startDate: null,
      endDate: null,
      searchText: ""
    };
    this._selectedExecDetail = null;  // for expanded view
  }

  set hass(h) {
    const first = !this._hass;
    this._hass = h;
    if (first) this._load();
  }

  connectedCallback() { this._render(); }

  disconnectedCallback() {
    // Cleanup timers on component unmount to prevent memory leaks
    if (this._notifTimer) clearTimeout(this._notifTimer);
    if (this._debounceTimer) clearTimeout(this._debounceTimer);
  }

  // ── Data loading ───────────────────────────────────────────────────────────

  async _load() {
    this._loading = true; this._updateUI();
    try {
      await Promise.all([
        this._loadTemplates(),
        this._loadChains(),
        this._loadExecutionHistory(),
        this._loadEvents(),
        this._loadGroups(),
        this._loadConditions(),
        this._loadPlayers(),
        this._loadHistory(),
      ]);
    } finally {
      this._loading = false;
      this._lastRenderKey = null;  // for render memoization
      this._render();
    }
  }

  async _loadEvents() {
    try {
      const res = await this._hass.callWS({ type: "house_voice/get_events" });
      this._events = res.events || {};
    } catch (e) { console.error("House Voice: load events", e); this._events = {}; }
  }

  async _loadGroups() {
    try {
      const res = await this._hass.callWS({ type: "house_voice/get_groups" });
      this._groups = res.groups || {};
    } catch (e) { console.error("House Voice: load groups", e); this._groups = {}; }
  }

  async _loadConditions() {
    try {
      const res = await this._hass.callWS({ type: "house_voice/get_conditions" });
      this._conditions = res.conditions || {};
    } catch (e) { console.error("House Voice: load conditions", e); this._conditions = {}; }
  }

  async _loadPlayers() {
    try {
      const res = await this._hass.callWS({ type: "house_voice/get_media_players" });
      this._players = res.media_players || [];
    } catch (e) { console.error("House Voice: load players", e); this._players = []; }
  }

  async _loadHistory() {
    try {
      const res = await this._hass.callWS({ type: "house_voice/get_history" });
      this._history = res.history || [];
    } catch (e) { console.error("House Voice: load history", e); this._history = []; }
  }

  // ── Notifications ──────────────────────────────────────────────────────────

  _notify(text, type = "success") {
    clearTimeout(this._notifTimer);
    this._notification = { text, type };
    this._render();
    this._notifTimer = setTimeout(() => { this._notification = null; this._render(); }, 3500);
  }

  async _reload() {
    if (!confirm("Genindlæs House Voice Manager?")) return;
    try {
      // Find our own config entry ID via the entity registry.
      // NOTE: there is intentionally no fallback service call here — an
      // earlier version fell back to `reload_custom_templates`, which
      // reloads Jinja2 templates, not this integration. Silently calling
      // the wrong service looked like success but did nothing, so we now
      // fail loudly and point the user to the manual reload path instead.
      const entityId = "sensor.house_voice_today";
      const entryId  = this._hass.entities?.[entityId]?.config_entry_id;

      if (!entryId) {
        this._notify(
          "Kunne ikke finde config entry — genindlæs manuelt via Indstillinger → Enheder & tjenester.",
          "error"
        );
        return;
      }

      await this._hass.callService("homeassistant", "reload_config_entry", {
        entry_id: entryId,
      });
      this._notify("♻️ House Voice genindlæst");
      setTimeout(() => this._load(), 1500);
    } catch (e) {
      this._notify(`Fejl ved genindlæsning: ${e.message || e}`, "error");
    }
  }

  // ── Event actions ──────────────────────────────────────────────────────────

  _openAdd()    { this._editingId = null; this._errors = {}; this._showForm = true; this._render(); }
  _openEdit(id) { this._editingId = id;   this._errors = {}; this._showForm = true; this._render(); }
  _closeForm()  { this._showForm = false; this._editingId = null; this._render(); }

  // ── Dialog methods ─────────────────────────────────────────────────────────

  _openDialog(type, data = {}) {
    this._dialog = { type, data };
    this._render();
  }

  _closeDialog() {
    this._dialog = null;
    this._render();
  }

  // ── Chain Templates (predefined) ────────────────────────────────────────────
  // These are starter templates for new chains
  _getChainTemplates() {
    return {
      "simple_announce": {
        name: "Simpel meddelelse",
        description: "Afspil besked på alle højttalere",
        steps: [{ type: "tts", message: "{{ message }}", speakers: ["group:all"], priority: "normal" }]
      },
      "conditional_tts": {
        name: "Betinget meddelelse",
        description: "Afspil kun hvis betingelse er opfyldt",
        steps: [
          { type: "condition", entity_id: "input_boolean.someone_home" },
          { type: "tts", message: "{{ message }}", speakers: ["group:all"], priority: "normal" }
        ]
      },
      "volume_ducking": {
        name: "Musik med volume ducking",
        description: "Sænk musik, afspil meddelelse, hæv musik",
        steps: [
          { type: "volume", speakers: ["group:all"], volume: 0.3, duration: 1 },
          { type: "tts", message: "{{ message }}", speakers: ["group:all"], priority: "normal" },
          { type: "delay", seconds: 1 },
          { type: "volume", speakers: ["group:all"], volume: 0.7 }
        ]
      },
      "occupancy_aware": {
        name: "Kun hvis der er nogen hjemme",
        description: "Check occupancy før announcement",
        steps: [
          { type: "condition", entity_id: "binary_sensor.someone_home" },
          { type: "tts", message: "{{ message }}", speakers: ["group:all"], priority: "normal" }
        ]
      }
    };
  }

  async _createChainFromTemplate(templateId, chainName) {
    const templates = this._getChainTemplates();
    const template = templates[templateId];
    if (!template) {
      this._notify("Skabelon ikke fundet.", "error");
      return;
    }
    // TODO: Save chain to backend via WebSocket
    this._notify(`Chain '${chainName}' oprettet fra skabelon ✓`);
  }

  _openExportDialog(chainId) {
    // TODO: Get chain data and show JSON export
    this._openDialog("export", { chainId });
  }

  _openImportDialog() {
    this._openDialog("import", {});
  }

  _openChainNameDialog(templateId) {
    this._openDialog("chainName", { templateId });
  }

  async _save() {
    const root = this.shadowRoot;
    const eventId   = root.querySelector(".f-event-id")?.value?.trim();
    const message   = root.querySelector(".f-message")?.value?.trim();
    const priority  = root.querySelector(".f-priority")?.value;
    const volume    = parseFloat(root.querySelector(".f-volume")?.value || "0.35");
    const speakers  = [...root.querySelectorAll(".f-speaker:checked")].map(el => el.value);

    const conditions = [...root.querySelectorAll(".f-condition-cb:checked")].map(el => el.value);

    // Validate and collect errors
    this._errors = {};
    if (!eventId)         this._errors.eventId = "Event ID mangler.";
    if (!message)         this._errors.message = "Besked mangler.";
    if (!speakers.length) this._errors.speakers = "Vælg mindst én højttaler eller gruppe.";
    
    if (Object.keys(this._errors).length > 0) {
      this._render();  // Re-render to show inline errors
      return;
    }

    this._saving = true; this._updateUI();
    
    // Fallback timeout to prevent stuck state (30s)
    const timeout = setTimeout(() => {
      this._saving = false;
      this._notify("Timeout: Please try again.", "error");
      this._render();
    }, 30000);
    
    try {
      await this._hass.callWS({
        type: "house_voice/save_event",
        event_id: eventId, message, speakers, priority, volume, conditions,
      });
      clearTimeout(timeout);
      await this._loadEvents();
      this._closeForm();
      this._notify(`Event '${eventId}' gemt ✓`);
    } catch (e) {
      clearTimeout(timeout);
      this._notify(`Fejl: ${e.message || e}`, "error");
    } finally { this._saving = false; this._updateUI(); }
  }

  async _delete(id) {
    if (!confirm(`Slet event '${id}'?`)) return;
    try {
      await this._hass.callWS({ type: "house_voice/delete_event", event_id: id });
      await this._loadEvents();
      this._notify(`Event '${id}' slettet.`);
    } catch (e) { this._notify(`Fejl: ${e.message || e}`, "error"); }
  }

  async _test(id) {
    try {
      await this._hass.callWS({ type: "house_voice/test_event", event_id: id });
      this._notify(`▶ '${id}' afspilles...`);
    } catch (e) { this._notify(`Fejl: ${e.message || e}`, "error"); }
  }

  // ── Condition actions ─────────────────────────────────────────────────────

  _openAddCond()    { this._editingCond = null; this._showCondForm = true; this._render(); }
  _openEditCond(id) { this._editingCond = id;   this._showCondForm = true; this._render(); }
  _closeCondForm()  { this._showCondForm = false; this._editingCond = null; this._render(); }

  async _saveCond() {
    const root = this.shadowRoot;
    const condId   = root.querySelector(".fc-cond-id")?.value?.trim();
    const label    = root.querySelector(".fc-label")?.value?.trim();
    const entityId = root.querySelector(".fc-entity-id")?.value?.trim();
    const state    = root.querySelector(".fc-state")?.value?.trim() || "on";

    if (!condId)   return this._notify("Betingelse ID mangler.", "error");
    if (!label)    return this._notify("Navn mangler.", "error");
    if (!entityId) return this._notify("Entity ID mangler.", "error");
    // Validate entity_id format: "domain.entity"
    const entityIdRegex = /^[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*$/i;
    if (!entityIdRegex.test(entityId)) {
      return this._notify("Entity ID skal være på format 'domain.entity' (fx 'sensor.stue_temp').", "error");
    }

    this._saving = true; this._updateUI();
    try {
      await this._hass.callWS({
        type: "house_voice/save_condition",
        condition_id: condId, label, entity_id: entityId, state,
      });
      await this._loadConditions();
      this._closeCondForm();
      this._notify(`Betingelse '${label}' gemt ✓`);
    } catch (e) {
      this._notify(`Fejl: ${e.message || e}`, "error");
    } finally { this._saving = false; this._updateUI(); }
  }

  async _deleteCond(id) {
    const label = this._conditions[id]?.label || id;
    if (!confirm(`Slet betingelse '${label}'?`)) return;
    try {
      await this._hass.callWS({ type: "house_voice/delete_condition", condition_id: id });
      await this._loadConditions();
      this._notify(`Betingelse '${label}' slettet.`);
    } catch (e) { this._notify(`Fejl: ${e.message || e}`, "error"); }
  }

  // ── Group actions ──────────────────────────────────────────────────────────

  _openAddGroup()    { this._editingGroup = null; this._showGroupForm = true; this._render(); }
  _openEditGroup(id) { this._editingGroup = id;   this._showGroupForm = true; this._render(); }
  _closeGroupForm()  { this._showGroupForm = false; this._editingGroup = null; this._render(); }

  async _saveGroup() {
    const root = this.shadowRoot;
    const groupId  = root.querySelector(".fg-group-id")?.value?.trim();
    const name     = root.querySelector(".fg-name")?.value?.trim();
    const speakers = [...root.querySelectorAll(".fg-speaker:checked")].map(el => el.value);

    if (!groupId)         return this._notify("Gruppe ID mangler.", "error");
    if (!name)            return this._notify("Navn mangler.", "error");
    if (!speakers.length) return this._notify("Vælg mindst én højttaler.", "error");

    this._saving = true; this._updateUI();
    try {
      await this._hass.callWS({
        type: "house_voice/save_group",
        group_id: groupId, name, speakers,
      });
      await this._loadGroups();
      this._closeGroupForm();
      this._notify(`Gruppe '${name}' gemt ✓`);
    } catch (e) {
      this._notify(`Fejl: ${e.message || e}`, "error");
    } finally { this._saving = false; this._updateUI(); }
  }

  async _deleteGroup(id) {
    if (!confirm(`Slet gruppe '${id}'?`)) return;
    try {
      await this._hass.callWS({ type: "house_voice/delete_group", group_id: id });
      await this._loadGroups();
      this._notify(`Gruppe '${id}' slettet.`);
    } catch (e) { this._notify(`Fejl: ${e.message || e}`, "error"); }
  }

  // ── Search ─────────────────────────────────────────────────────────────────

  _onSearch(value) { this._searchQuery = value.toLowerCase(); this._render(); }

  _filteredEvents() {
    if (!this._searchQuery) return this._events;
    return Object.fromEntries(
      Object.entries(this._events).filter(([id, ev]) =>
        id.toLowerCase().includes(this._searchQuery) ||
        (ev.message || "").toLowerCase().includes(this._searchQuery)
      )
    );
  }

  // ── Export / Import ────────────────────────────────────────────────────────

  _exportEvents() {
    const json = JSON.stringify(this._events, null, 2);
    const blob = new Blob([json], { type: "application/json" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url; a.download = "house_voice_events.json"; a.click();
    URL.revokeObjectURL(url);
    this._notify("Events eksporteret ✓");
  }

  _importEvents() {
    const input = document.createElement("input");
    input.type = "file"; input.accept = ".json,application/json";
    input.onchange = async (e) => {
      const file = e.target.files[0]; if (!file) return;
      try {
        const parsed = JSON.parse(await file.text());
        if (typeof parsed !== "object" || Array.isArray(parsed))
          return this._notify("Ugyldig fil – forventet JSON objekt.", "error");
        for (const [id, ev] of Object.entries(parsed)) {
          if (!ev.message || !ev.speakers || !ev.priority)
            return this._notify(`Ugyldig event '${id}' – mangler felter.`, "error");
        }
        let count = 0, failed = 0;
        const promises = Object.entries(parsed).map(([id, ev]) =>
          this._hass.callWS({
            type: "house_voice/save_event",
            event_id: id, message: ev.message,
            speakers: Array.isArray(ev.speakers) ? ev.speakers : [ev.speakers],
            priority: ev.priority || "normal", volume: ev.volume || 0.35,
            conditions: ev.conditions || [],
          })
        );
        const results = await Promise.allSettled(promises);
        results.forEach(r => { if (r.status === "fulfilled") count++; else failed++; });
        await this._loadEvents();
        const msg = failed > 0 ? `${count} importeret, ${failed} fejlede ⚠️` : `${count} events importeret ✓`;
        this._notify(msg);
      } catch (err) { this._notify(`Import fejlede: ${err.message || err}`, "error"); }
    };
    input.click();
  }

  // ── Helpers ────────────────────────────────────────────────────────────────

  _esc(s) {
    return String(s || "")
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  _priorityLabel(p) {
    return { info: "🎵 Info", normal: "🔔 Normal", critical: "🚨 Critical" }[p] || p;
  }

  _priorityColor(p) {
    return { info: "#3b82f6", normal: "#10b981", critical: "#ef4444" }[p] || "#6b7280";
  }

  _statusLabel(s) {
    return {
      spoken:              { label: "Afspillet",    color: "#10b981" },
      blocked_spam:        { label: "Spam-filter",  color: "#f59e0b" },
      blocked_quiet_hours: { label: "Stille timer", color: "#8b5cf6" },
      blocked_condition:   { label: "Betingelse",   color: "#6b7280" },
    }[s] || { label: s, color: "#94a3b8" };
  }

  _isQuietHours() {
    const h = new Date().getHours();
    return h >= 22 || h < 7;
  }

  // ── Stats bar ──────────────────────────────────────────────────────────────

  _statsBarHTML() {
    const eventCount  = Object.keys(this._events).length;
    const groupCount  = Object.keys(this._groups).length;
    const quietActive = this._isQuietHours();
    const sensorState = this._hass?.states?.["sensor.house_voice_today"];
    const todayCount  = sensorState ? sensorState.state : "–";
    const quietLabel  = quietActive
      ? `<span class="stat-pill pill-quiet">🌙 Stille timer aktiv</span>`
      : `<span class="stat-pill pill-ok">☀️ Aktiv</span>`;

    return `
      <div class="stats-bar">
        <span class="stat-pill pill-neutral">📦 ${eventCount} events</span>
        <span class="stat-pill pill-neutral">🔈 ${groupCount} grupper</span>
        <span class="stat-pill pill-accent">📊 ${todayCount} i dag</span>
        ${quietLabel}
      </div>`;
  }

  // ── Notification HTML ──────────────────────────────────────────────────────

  _notifHTML() {
    if (!this._notification) return "";
    const { text, type } = this._notification;
    const bg  = type === "success"
      ? "linear-gradient(135deg, rgba(20,184,166,0.18) 0%, rgba(20,184,166,0.06) 100%)"
      : "linear-gradient(135deg, rgba(239,68,68,0.18) 0%, rgba(239,68,68,0.06) 100%)";
    const col = type === "success" ? "#14b8a6" : "#ef4444";
    const bdr = type === "success" ? "rgba(20,184,166,0.35)" : "rgba(239,68,68,0.35)";
    return `<div class="notif" style="background:${bg};color:${col};border:1px solid ${bdr}">${this._esc(text)}</div>`;
  }

  // ── Events tab ─────────────────────────────────────────────────────────────

  _eventListHTML() {
    const filtered = this._filteredEvents();
    const ids = Object.keys(filtered);
    if (!Object.keys(this._events).length)
      return `<div class="empty">Ingen voice events endnu.<br>Tryk <strong>＋ Tilføj event</strong> for at komme i gang.</div>`;
    if (!ids.length)
      return `<div class="empty">Ingen events matcher "<strong>${this._esc(this._searchQuery)}</strong>".</div>`;

    return ids.map(id => {
      const ev = filtered[id];
      const speakers = (ev.speakers || []).map(s =>
        s.startsWith("group:") ? `🔈 ${s.replace("group:", "")}` : s
      ).join(", ");
      const priColor  = this._priorityColor(ev.priority);
      const condBadge = (ev.conditions && ev.conditions.length)
        ? `<span class="badge badge-cond" title="${ev.conditions.map(c => this._conditions[c]?.label || c).join(' ∧ ')}">⚡ ${ev.conditions.length} betingelse${ev.conditions.length > 1 ? 'r' : ''}</span>`
        : "";
      return `
        <div class="event-card">
          <div class="event-top">
            <div class="event-id">${this._esc(id)}</div>
            <span class="badge" style="background:${priColor}1a;color:${priColor};border:1px solid ${priColor}44">
              ${this._priorityLabel(ev.priority)}
            </span>
            ${condBadge}
          </div>
          <div class="event-message">${this._esc(ev.message)}</div>
          <div class="event-meta">
            <span class="event-speakers">📢 ${this._esc(speakers || "–")}</span>
            <span class="event-volume">🔊 ${Math.round((ev.volume || 0.35) * 100)}%</span>
          </div>
          <div class="event-actions">
            <button class="btn btn-test"   data-id="${this._esc(id)}">▶ Test</button>
            <button class="btn btn-edit"   data-id="${this._esc(id)}">✎ Rediger</button>
            <button class="btn btn-delete" data-id="${this._esc(id)}">✕ Slet</button>
          </div>
        </div>`;
    }).join("");
  }

  // ── Groups tab ─────────────────────────────────────────────────────────────

  _groupListHTML() {
    const ids = Object.keys(this._groups);
    if (!ids.length)
      return `<div class="empty">Ingen grupper endnu.<br>Tryk <strong>＋ Tilføj gruppe</strong> for at oprette en.</div>`;

    return ids.map(id => {
      const g = this._groups[id];
      const speakers = (g.speakers || []).join(", ");
      return `
        <div class="event-card">
          <div class="event-top">
            <div class="event-id">group:${this._esc(id)}</div>
            <span class="badge" style="background:rgba(20,184,166,0.12);color:#14b8a6;border:1px solid rgba(20,184,166,0.3)">
              🔈 ${this._esc(g.name || id)}
            </span>
          </div>
          <div class="event-meta">
            <span class="event-speakers">📢 ${this._esc(speakers || "–")}</span>
          </div>
          <div class="event-actions">
            <button class="btn btn-edit btn-edit-group"    data-id="${this._esc(id)}">✎ Rediger</button>
            <button class="btn btn-delete btn-delete-group" data-id="${this._esc(id)}">✕ Slet</button>
          </div>
        </div>`;
    }).join("");
  }

  // ── History tab ────────────────────────────────────────────────────────────


  // ── Chain management ───────────────────────────────────────────────────────

  async _loadChains() {
    try {
      this._chains = await this._hass.callWS({
        type: "house_voice/list_chains",
      }) || {};
      if (Object.keys(this._chains).length > 0) {
        this._currentChain = Object.keys(this._chains)[0];
      }
    } catch (e) {
      console.error("[House Voice] Error loading chains:", e);
      this._chains = {};
    }
  }



  _switchChain(chainId) {
  async _loadExecutionHistory() {
    try {
      // Load execution history with filters
      const result = await this._hass.callWS({
        type: "house_voice/query_executions",
        chain_id: this._historyFilters.chainId,
        status: this._historyFilters.status,
        start_date: this._historyFilters.startDate,
        end_date: this._historyFilters.endDate,
        search_text: this._historyFilters.searchText,
        limit: 100,
      });
      this._execHistory = result.executions || [];
    } catch (e) {
      console.error("[House Voice] Error loading execution history:", e);
      this._execHistory = [];
    }
  }

  async _getExecutionDetail(execId) {
    try {
      const result = await this._hass.callWS({
        type: "house_voice/get_execution_detail",
        exec_id: execId,
      });
      return result.execution;
    } catch (e) {
      console.error("[House Voice] Error loading execution detail:", e);
      return null;
    }
  }

  async _applyHistoryFilters() {
    await this._loadExecutionHistory();
    this._selectedExecDetail = null;  // Clear detail view
    this._render();
  }
    if (this._chains[chainId]) {
      this._currentChain = chainId;
      this._render();
    }
  }

  _getChainStatus(chainId) {
    const chain = this._chains[chainId];
    if (!chain) return "unknown";
    if (chain.status === "active") return "active";
    if (chain.status === "published") return "published";
    return "draft";
  }

  _formatTimestamp(timestamp) {
    if (!timestamp) return "–";
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) return "–";
    
    const now = new Date();
    const diff = now - date;
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (seconds < 60) return "lige nu";
    if (minutes < 60) return `${minutes} min siden`;
    if (hours < 24) return `${hours} t siden`;
    if (days < 7) return `${days} d siden`;
    
    return date.toLocaleDateString("da-DK");
  }

  _chainsHTML() {
    const chainIds = Object.keys(this._chains);
    if (!chainIds.length)
      return `<div class="empty">Ingen kæder endnu. Opret en ny kæde ved at klikke på 'Nyt Chain'.</div>`;

    return `
      <div class="chains-container">
        <div class="chains-header">
          <h3>Announcement Chains</h3>
          <button class="btn btn-primary" id="btn-new-chain">+ Nyt Chain</button>
        </div>
        
        <div class="chain-switcher">
          <label class="chain-selector-label">Aktivt Chain:</label>
          <select id="chain-selector" class="chain-selector">
            <option value="">-- Vælg et chain --</option>
            ${chainIds.map(id => `
              <option value="${this._esc(id)}" ${this._currentChain === id ? 'selected' : ''}>
                ${this._esc(this._chains[id].name || id)}
              </option>
            `).join("")}
          </select>
        </div>

        <div class="chains-list">
          ${chainIds.map(id => {
            const chain = this._chains[id];
            const status = this._getChainStatus(id);
            const statusColors = { active: "#10b981", published: "#3b82f6", draft: "#8b5cf6" };
            const recentExecs = this._execHistory.filter(e => e.chainId === id).slice(0, 5);

            return `
              <div class="chain-card">
                <div class="chain-header">
                  <div class="chain-info">
                    <h4 class="chain-name">${this._esc(chain.name || id)}</h4>
                    <span class="chain-status status-${status}" style="background-color: ${statusColors[status]}">
                      ${status}
                    </span>
                  </div>
                  <div class="chain-steps">
                    <small>${chain.steps ? chain.steps.length : 0} steps</small>
                  </div>
                </div>
                
                ${recentExecs.length > 0 ? `
                  <div class="chain-recent-execs">
                    <small>Recent executions:</small>
                    ${recentExecs.map(exec => `
                      <span class="exec-badge ${exec.success ? 'success' : 'error'}">
                        ${exec.success ? '✓' : '✗'} ${this._formatTimestamp(exec.timestamp)}
                      </span>
                    `).join("")}
                  </div>
                ` : ""}
                
                <div class="chain-actions">
                  <button class="btn btn-small" data-chain-id="${this._esc(id)}">Edit</button>
                  <button class="btn btn-small" data-chain-id="${this._esc(id)}">Test</button>
                  <button class="btn btn-small btn-danger" data-chain-id="${this._esc(id)}">Delete</button>
                </div>
              </div>
            `;
          }).join("")}
        </div>
      </div>
    `;
  }


    _historyHTML() {
    const { chainId, status, searchText } = this._historyFilters;
    
    return `
      <div class="history-container">
        <!-- Filter Panel -->
        <div class="history-filters">
          <div class="filter-row">
            <div class="filter-group">
              <label>Kæde:</label>
              <select id="history-filter-chain" class="filter-select">
                <option value="">-- Alle kæder --</option>
                ${Object.keys(this._chains).map(id => `
                  <option value="${id}" ${chainId === id ? 'selected' : ''}>
                    ${this._esc(this._chains[id].name)}
                  </option>
                `).join('')}
              </select>
            </div>
            
            <div class="filter-group">
              <label>Status:</label>
              <select id="history-filter-status" class="filter-select">
                <option value="">-- Alle --</option>
                <option value="completed" ${status === 'completed' ? 'selected' : ''}>✓ Afsluttet</option>
                <option value="failed" ${status === 'failed' ? 'selected' : ''}>✗ Fejl</option>
                <option value="in_progress" ${status === 'in_progress' ? 'selected' : ''}>⟳ I gang</option>
                <option value="blocked_condition" ${status === 'blocked_condition' ? 'selected' : ''}>⊘ Blokeret</option>
              </select>
            </div>
            
            <div class="filter-group">
              <label>Søg:</label>
              <input type="text" id="history-filter-search" class="filter-input" 
                placeholder="Søg i trinnavne..." value="${this._esc(searchText)}">
            </div>
            
            <button id="history-apply-filters" class="btn btn-small">Anvend</button>
            <button id="history-reset-filters" class="btn btn-small">Nulstil</button>
          </div>
        </div>

        <!-- Execution History Table -->
        <div class="history-table-wrapper">
          ${this._execHistory.length > 0 ? `
            <table class="history-table">
              <thead>
                <tr>
                  <th>Tid</th>
                  <th>Kæde</th>
                  <th>Status</th>
                  <th>Trin</th>
                  <th>Varighed</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                ${this._execHistory.map(exec => {
                  const isSelected = this._selectedExecDetail === exec.id;
                  const statusIcon = this._getStatusIcon(exec.status);
                  const chainName = exec.chain_id && this._chains[exec.chain_id] 
                    ? this._chains[exec.chain_id].name 
                    : exec.chain_id || 'Ukendt';
                  const duration = exec.duration_seconds 
                    ? Math.round(exec.duration_seconds * 1000) + 'ms'
                    : '–';
                  const stepCount = exec.steps ? exec.steps.length : 0;
                  
                  return `
                    <tr class="history-row ${isSelected ? 'selected' : ''}" data-exec-id="${exec.id}">
                      <td class="col-time">${this._formatTimestamp(exec.started)}</td>
                      <td class="col-chain">${this._esc(chainName)}</td>
                      <td class="col-status"><span class="status-badge ${exec.status}">${statusIcon} ${exec.status}</span></td>
                      <td class="col-steps">${stepCount} trin</td>
                      <td class="col-duration">${duration}</td>
                      <td class="col-expand">
                        <button class="btn-expand" data-exec-id="${exec.id}" title="Vis detaljer">▼</button>
                      </td>
                    </tr>
                    ${isSelected && exec.steps ? `
                      <tr class="detail-row">
                        <td colspan="6">
                          <div class="execution-detail">
                            <div class="detail-header">
                              <h4>Udførelsesdetaljer</h4>
                              <button class="btn btn-small" id="btn-export-exec-${exec.id}">📥 Eksporter JSON</button>
                            </div>
                            <div class="steps-table">
                              <table>
                                <thead>
                                  <tr>
                                    <th>#</th>
                                    <th>Trin-ID</th>
                                    <th>Type</th>
                                    <th>Status</th>
                                    <th>Varighed</th>
                                    <th>Besked</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  ${exec.steps.map((step, idx) => `
                                    <tr class="step-detail-row">
                                      <td>${idx + 1}</td>
                                      <td class="step-id">${this._esc(step.id || '–')}</td>
                                      <td>${this._esc(step.type || 'action')}</td>
                                      <td><span class="step-status ${step.status || 'unknown'}">${step.status || '?'}</span></td>
                                      <td>${step.duration_ms ? Math.round(step.duration_ms) + 'ms' : '–'}</td>
                                      <td class="step-message">${this._esc(step.message || step.error || '–')}</td>
                                    </tr>
                                  `).join('')}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        </td>
                      </tr>
                    ` : ''}
                  `;
                }).join('')}
              </tbody>
            </table>
          ` : `
            <div class="empty-state">
              <p>Ingen udførelseshistorik fundet</p>
            </div>
          `}
        </div>
      </div>
    `;
  }

  _getStatusIcon(status) {
    const icons = {
      'completed': '✓',
      'failed': '✗',
      'in_progress': '⟳',
      'blocked_condition': '⊘'
    };
    return icons[status] || '?';
  }

  _speakerCheckboxesHTML(selected) {
    const groupItems = Object.entries(this._groups).map(([gid, g]) => {
      const val     = `group:${gid}`;
      const checked = selected.includes(val) ? "checked" : "";
      return `
        <label class="speaker-label">
          <input type="checkbox" class="f-speaker" value="${this._esc(val)}" ${checked}>
          <span class="speaker-name">🔈 ${this._esc(g.name || gid)}</span>
          <span class="speaker-entity">group:${this._esc(gid)}</span>
        </label>`;
    });

    const playerItems = this._players.map(p => {
      const checked = selected.includes(p.entity_id) ? "checked" : "";
      return `
        <label class="speaker-label">
          <input type="checkbox" class="f-speaker" value="${this._esc(p.entity_id)}" ${checked}>
          <span class="speaker-name">${this._esc(p.friendly_name)}</span>
          <span class="speaker-entity">${this._esc(p.entity_id)}</span>
        </label>`;
    });

    if (!groupItems.length && !playerItems.length)
      return `<div class="no-players">Ingen media_player entities fundet i Home Assistant.</div>`;

    return [
      groupItems.length  ? `<div class="speaker-section-label">Grupper</div>${groupItems.join("")}`   : "",
      playerItems.length ? `<div class="speaker-section-label">Højttalere</div>${playerItems.join("")}` : "",
    ].join("");
  }

  // ── Speaker checkboxes (groups form) ──────────────────────────────────────


  // ── Condition checkboxes (event form) ─────────────────────────────────────

  _conditionCheckboxesHTML(selectedIds) {
    const ids = Object.keys(this._conditions);
    if (!ids.length)
      return `<div class="no-players">Ingen betingelser i biblioteket endnu — tilføj via 'Betingelsesbibliotek' herunder.</div>`;
    return `<div class="cond-list">${ids.map(id => {
      const c = this._conditions[id];
      const checked = selectedIds.includes(id) ? "checked" : "";
      return `
        <label class="speaker-label">
          <input type="checkbox" class="f-condition-cb" value="${this._esc(id)}" ${checked}>
          <span class="speaker-name">${this._esc(c.label)}</span>
          <span class="speaker-entity">${this._esc(c.entity_id)} = ${this._esc(c.state)}</span>
        </label>`;
    }).join("")}</div>`;
  }

  // ── Condition library section (events tab) ─────────────────────────────────

  _condLibHTML() {
    const ids = Object.keys(this._conditions);
    return `
      <div class="cond-lib-section">
        <div class="cond-lib-header">
          <span class="section-title">⚡ Betingelsesbibliotek</span>
          <button class="btn btn-add-sm" id="btn-add-cond">+ Tilføj betingelse</button>
        </div>
        ${!ids.length
          ? `<div class="cond-lib-empty">Ingen betingelser endnu — klik + for at tilføje en.</div>`
          : `<div class="cond-lib-list">${ids.map(id => {
              const c = this._conditions[id];
              return `
                <div class="cond-row">
                  <div class="cond-row-info">
                    <span class="cond-label">${this._esc(c.label)}</span>
                    <span class="cond-meta">${this._esc(c.entity_id)} = <code class="cond-code">${this._esc(c.state)}</code></span>
                  </div>
                  <div class="cond-row-actions">
                    <button class="btn btn-edit btn-edit-cond" data-id="${this._esc(id)}">✎</button>
                    <button class="btn btn-delete btn-delete-cond" data-id="${this._esc(id)}">×</button>
                  </div>
                </div>`;
            }).join("")}</div>`
        }
      </div>`;
  }

  // ── Condition form overlay ─────────────────────────────────────────────────

  _condFormHTML() {
    const isEdit = this._editingCond !== null;
    const c      = isEdit ? (this._conditions[this._editingCond] || {}) : {};
    const condId = isEdit ? this._editingCond : "";
    const label  = c.label     || "";
    const eid    = c.entity_id || "";
    const state  = c.state     || "on";
    const title  = isEdit ? `Rediger: ${condId}` : "Ny betingelse";
    return `
      <div class="form-overlay">
        <div class="form-card">
          <div class="form-header">
            <span class="form-title">${this._esc(title)}</span>
            <button class="close-btn" id="close-cond-form">✕</button>
          </div>
          <div class="form-body">
            <div class="field">
              <label class="field-label">Betingelse ID <span class="req">*</span></label>
              <input class="fc-cond-id input" type="text" value="${this._esc(condId)}"
                placeholder="f.eks. nogen_hjemme" ${isEdit ? "readonly" : ""}>
              <span class="hint">Bruges internt til at koble betingelsen på events.</span>
            </div>
            <div class="field">
              <label class="field-label">Navn <span class="req">*</span></label>
              <input class="fc-label input" type="text" value="${this._esc(label)}"
                placeholder="f.eks. Nogen er hjemme">
            </div>
            <div class="field">
              <label class="field-label">Entity ID <span class="req">*</span></label>
              <input class="fc-entity-id input" type="text" value="${this._esc(eid)}"
                placeholder="f.eks. binary_sensor.nogen_hjemme">
              <span class="hint">Entity der skal være i den forventede tilstand.</span>
            </div>
            <div class="field">
              <label class="field-label">Forventet tilstand</label>
              <select class="fc-state input">
                <option value="on"       ${state === "on"       ? "selected" : ""}>on</option>
                <option value="off"      ${state === "off"      ? "selected" : ""}>off</option>
                <option value="home"     ${state === "home"     ? "selected" : ""}>home</option>
                <option value="not_home" ${state === "not_home" ? "selected" : ""}>not_home</option>
              </select>
              <span class="hint">Betingelsen er opfyldt når entityen har denne værdi.</span>
            </div>
          </div>
          <div class="form-footer">
            <button class="btn btn-cancel" id="cancel-cond-form">Annuller</button>
            <button class="btn btn-save" id="save-cond-form" ${this._saving ? "disabled" : ""}>
              ${this._saving ? "Gemmer..." : "💾 Gem"}
            </button>
          </div>
        </div>
      </div>`;
  }

  _groupSpeakerCheckboxesHTML(selected) {
    if (!this._players.length)
      return `<div class="no-players">Ingen media_player entities fundet i Home Assistant.</div>`;
    return this._players.map(p => {
      const checked = selected.includes(p.entity_id) ? "checked" : "";
      return `
        <label class="speaker-label">
          <input type="checkbox" class="fg-speaker" value="${this._esc(p.entity_id)}" ${checked}>
          <span class="speaker-name">${this._esc(p.friendly_name)}</span>
          <span class="speaker-entity">${this._esc(p.entity_id)}</span>
        </label>`;
    }).join("");
  }

  // ── Event form ─────────────────────────────────────────────────────────────

  _dialogHTML() {
    if (!this._dialog) return '';
    const { type, data } = this._dialog;
    
    if (type === 'export') {
      const chainData = data.chainId ? JSON.stringify({}, null, 2) : '{}';
      return `
        <div class="dialog-overlay">
          <div class="dialog-card">
            <div class="dialog-header">
              <span>Eksporter Chain</span>
              <button class="dialog-close" id="dialog-close">✕</button>
            </div>
            <div class="dialog-body">
              <label style="font-size: 12px; font-weight: 600; color: var(--sub);">JSON:</label>
              <textarea id="export-json" readonly style="width: 100%; height: 300px; padding: 12px; border: 1px solid var(--div); border-radius: 8px; background: var(--bg3); color: var(--text); font-family: 'DM Mono', monospace; font-size: 12px; resize: none;">${chainData}</textarea>
            </div>
            <div class="dialog-footer">
              <button class="btn btn-cancel" id="dialog-cancel">Luk</button>
              <button class="btn btn-save" id="dialog-copy">📋 Kopier JSON</button>
            </div>
          </div>
        </div>`;
    }
    
    if (type === 'import') {
      return `
        <div class="dialog-overlay">
          <div class="dialog-card">
            <div class="dialog-header">
              <span>Importér Chain</span>
              <button class="dialog-close" id="dialog-close">✕</button>
            </div>
            <div class="dialog-body">
              <label style="font-size: 12px; font-weight: 600; color: var(--sub);">JSON:</label>
              <textarea id="import-json" placeholder='Indsæt chain JSON her...' style="width: 100%; height: 300px; padding: 12px; border: 1px solid var(--div); border-radius: 8px; background: var(--bg3); color: var(--text); font-family: 'DM Mono', monospace; font-size: 12px; resize: none;"></textarea>
              <span id="import-error" style="display: none; color: var(--red); font-size: 12px; margin-top: 8px;"></span>
            </div>
            <div class="dialog-footer">
              <button class="btn btn-cancel" id="dialog-cancel">Annuller</button>
              <button class="btn btn-save" id="dialog-import">📥 Importér</button>
            </div>
          </div>
        </div>`;
    }
    
    if (type === 'chainName') {
      return `
        <div class="dialog-overlay">
          <div class="dialog-card">
            <div class="dialog-header">
              <span>Nyt Chain fra skabelon</span>
              <button class="dialog-close" id="dialog-close">✕</button>
            </div>
            <div class="dialog-body">
              <div class="field">
                <label class="field-label">Chain Navn <span class="req">*</span></label>
                <input id="chain-name-input" class="input" type="text" placeholder="f.eks. Morning Greeting" autofocus>
                <span class="hint">Bruges til at identificere chain'et</span>
              </div>
            </div>
            <div class="dialog-footer">
              <button class="btn btn-cancel" id="dialog-cancel">Annuller</button>
              <button class="btn btn-save" id="dialog-create-chain">✨ Opret Chain</button>
            </div>
          </div>
        </div>`;
    }
    
    return '';
  }

  _formHTML() {
    const isEdit  = this._editingId !== null;
    const ev      = isEdit ? (this._events[this._editingId] || {}) : {};
    const eventId = isEdit ? this._editingId : "";
    const msg     = ev.message   || "";
    const pri     = ev.priority  || "normal";
    const vol     = ev.volume    !== undefined ? ev.volume : 0.35;
    const cond    = ev.conditions || [];
    const selSpk  = ev.speakers  || [];
    const title   = isEdit ? `Rediger: ${eventId}` : "Nyt voice event";

    return `
      <div class="form-overlay">
        <div class="form-card">
          <div class="form-header">
            <span class="form-title">${this._esc(title)}</span>
            <button class="close-btn" id="close-form">✕</button>
          </div>
          <div class="form-body">
            <div class="field ${this._errors.eventId ? 'error' : ''}">
              <label class="field-label">Event ID <span class="req">*</span></label>
              <input class="f-event-id input" type="text" value="${this._esc(eventId)}"
                placeholder="f.eks. dishwasher_done" ${isEdit ? "readonly" : ""}>
              ${this._errors.eventId ? `<span class="error-message">${this._esc(this._errors.eventId)}</span>` : '<span class="hint">Bruges i automationer: house_voice.say → event: dishwasher_done</span>'}
            </div>
            <div class="field ${this._errors.message ? 'error' : ''}">
              <label class="field-label">Besked <span class="req">*</span></label>
              <input class="f-message input" type="text" value="${this._esc(msg)}"
                placeholder="f.eks. Opvaskeren er færdig">
              ${this._errors.message ? `<span class="error-message">${this._esc(this._errors.message)}</span>` : ''}
            </div>
            <div class="field">
              <label class="field-label">Betingelser <span class="hint-inline">(valgfrit – alle skal være opfyldt)</span></label>
              ${this._conditionCheckboxesHTML(cond)}
              <span class="hint">Eventet afspilles kun når ALLE valgte betingelser er sande. Lad stå tomt for altid at afspille.</span>
            </div>
            <div class="field">
              <label class="field-label">Prioritet</label>
              <select class="f-priority input">
                <option value="info"     ${pri === "info"     ? "selected" : ""}>🎵 Info – duck musik</option>
                <option value="normal"   ${pri === "normal"   ? "selected" : ""}>🔔 Normal</option>
                <option value="critical" ${pri === "critical" ? "selected" : ""}>🚨 Critical – altid igennem</option>
              </select>
            </div>
            <div class="field">
              <label class="field-label">Volumen: <span id="vol-display">${Math.round(vol * 100)}%</span></label>
              <input class="f-volume" type="range" min="0.05" max="1.0" step="0.05" value="${vol}" id="vol-slider">
            </div>
            <div class="field ${this._errors.speakers ? 'error' : ''}">
              <label class="field-label">Højttalere / Grupper <span class="req">*</span></label>
              <div class="speakers-list">${this._speakerCheckboxesHTML(selSpk)}</div>
              ${this._errors.speakers ? `<span class="error-message">${this._esc(this._errors.speakers)}</span>` : ''}
            </div>
          </div>
          <div class="form-footer">
            <button class="btn btn-cancel" id="cancel-form">Annuller</button>
            <button class="btn btn-save" id="save-form" ${this._saving ? "disabled" : ""}>
              ${this._saving ? "Gemmer..." : "💾 Gem"}
            </button>
          </div>
        </div>
      </div>`;
  }

  // ── Group form ─────────────────────────────────────────────────────────────

  _groupFormHTML() {
    const isEdit  = this._editingGroup !== null;
    const g       = isEdit ? (this._groups[this._editingGroup] || {}) : {};
    const groupId = isEdit ? this._editingGroup : "";
    const name    = g.name || "";
    const selSpk  = g.speakers || [];
    const title   = isEdit ? `Rediger: ${groupId}` : "Ny højttalergruppe";

    return `
      <div class="form-overlay">
        <div class="form-card">
          <div class="form-header">
            <span class="form-title">${this._esc(title)}</span>
            <button class="close-btn" id="close-group-form">✕</button>
          </div>
          <div class="form-body">
            <div class="field">
              <label class="field-label">Gruppe ID <span class="req">*</span></label>
              <input class="fg-group-id input" type="text" value="${this._esc(groupId)}"
                placeholder="f.eks. alle_rum" ${isEdit ? "readonly" : ""}>
              <span class="hint">Bruges i events som 'group:alle_rum'</span>
            </div>
            <div class="field">
              <label class="field-label">Navn <span class="req">*</span></label>
              <input class="fg-name input" type="text" value="${this._esc(name)}"
                placeholder="f.eks. Alle rum">
            </div>
            <div class="field">
              <label class="field-label">Højttalere <span class="req">*</span></label>
              <div class="speakers-list">${this._groupSpeakerCheckboxesHTML(selSpk)}</div>
            </div>
          </div>
          <div class="form-footer">
            <button class="btn btn-cancel" id="cancel-group-form">Annuller</button>
            <button class="btn btn-save" id="save-group-form" ${this._saving ? "disabled" : ""}>
              ${this._saving ? "Gemmer..." : "💾 Gem"}
            </button>
          </div>
        </div>
      </div>`;
  }

  // ── Main render ────────────────────────────────────────────────────────────

  _updateUI() {
    // Fast path: update UI elements without full re-render
    const root = this.shadowRoot;
    
    // Update button disabled states based on _saving and _loading
    root.querySelectorAll(".btn-save, .btn-load, .btn-import").forEach(btn => {
      btn.disabled = this._saving || this._loading;
    });
    
    // Update loading indicator
    const loader = root.querySelector(".loader");
    if (loader) loader.style.display = this._loading ? "flex" : "none";
    
    // Update tab content visibility without full re-render
    const eventsTab = root.querySelector(".events-tab");
    if (eventsTab) eventsTab.style.display = this._tab === "events" ? "block" : "none";
    const groupsTab = root.querySelector(".groups-tab");
    if (groupsTab) groupsTab.style.display = this._tab === "groups" ? "block" : "none";
    const historyTab = root.querySelector(".history-tab");
    if (historyTab) historyTab.style.display = this._tab === "history" ? "block" : "none";
  }


  _render() {
    const isEvents  = this._tab === "events";
    const isGroups  = this._tab === "groups";
    const isChains  = this._tab === "chains";
    const isHistory = this._tab === "history";

    this.shadowRoot.innerHTML = `
      <style>${this._css()}</style>
      <div class="panel">

        <div class="panel-topbar">
          <div class="topbar">
            <div class="topbar-title">
              <div class="header-icon"><img src="data:image/png;base64,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" alt="House Voice" class="logo-img"/></div>
              <div class="header-text">
                <span class="header-name">House Voice</span>
                <span class="header-sub">Voice Event Manager</span>
                <span class="header-version">v${this._version}</span>
              </div>
            </div>
            <div class="topbar-actions">
              ${isEvents ? `
                <button class="btn btn-import" id="btn-import">📥 Import</button>
                <button class="btn btn-export" id="btn-export">📤 Export</button>
                <button class="btn btn-refresh" id="btn-refresh">↺ Opdater</button>
                <button class="btn btn-reload" id="btn-reload">⟳ Reload</button>
                <button class="btn btn-add" id="btn-add">＋ Tilføj event</button>
              ` : isGroups ? `
                <button class="btn btn-refresh" id="btn-refresh">↺ Opdater</button>
                <button class="btn btn-reload" id="btn-reload">⟳ Reload</button>
                <button class="btn btn-add" id="btn-add-group">＋ Tilføj gruppe</button>
              ` : `
                <button class="btn btn-refresh" id="btn-refresh">↺ Opdater</button>
                <button class="btn btn-reload" id="btn-reload">⟳ Reload</button>
              `}
            </div>
          </div>
          <div class="tab-bar">
            <button class="tab ${isEvents  ? 'active' : ''}" data-tab="events">📋 Events</button>
            <button class="tab ${isGroups  ? 'active' : ''}" data-tab="groups">🔈 Grupper</button>
            <button class="tab ${isChains  ? 'active' : ''}" data-tab="chains">⛓️ Kæder</button>
            <button class="tab ${isHistory ? 'active' : ''}" data-tab="history">🕐 Historik</button>
          </div>
        </div>

        <div class="panel-scroll">
          ${isEvents ? `
            <div class="searchbar">
              <input class="search-input" id="search-input" type="search"
                placeholder="🔍 Søg på event ID eller besked..."
                value="${this._esc(this._searchQuery)}">
            </div>
          ` : ""}

          ${this._statsBarHTML()}
          ${this._notifHTML()}

          <div class="content-area">
            ${isEvents  ? this._eventListHTML() : ""}
            ${isEvents  ? this._condLibHTML()   : ""}
            ${isGroups  ? this._groupListHTML() : ""}
            ${isChains  ? this._chainsHTML()    : ""}
            ${isHistory ? this._historyHTML()   : ""}
          </div>
        </div>

        ${this._showForm      ? this._formHTML()      : ""}
        ${this._showGroupForm ? this._groupFormHTML() : ""}
        ${this._showCondForm  ? this._condFormHTML()  : ""}

      </div>`;

    this._bind();
  }

  // ── Event binding ──────────────────────────────────────────────────────────

  _bind() {
    const root = this.shadowRoot;

    root.querySelectorAll(".tab").forEach(el =>
      el.addEventListener("click", () => { 
        this._tab = el.dataset.tab;
        this._searchQuery = "";  // Clear search when switching tabs
        this._render(); 
      })
    );

    root.getElementById("btn-add")?.addEventListener("click",       () => this._openAdd());
    root.getElementById("btn-add-group")?.addEventListener("click", () => this._openAddGroup());
    root.getElementById("btn-refresh")?.addEventListener("click",   () => this._load());
    root.getElementById("btn-reload")?.addEventListener("click",    () => this._reload());
    root.getElementById("btn-export")?.addEventListener("click",    () => this._exportEvents());
    root.getElementById("btn-import")?.addEventListener("click",    () => this._importEvents());

    // Chain switcher listener
    const chainSelector = root.getElementById("chain-selector");
    if (chainSelector) {
      chainSelector.addEventListener("change", (e) => {
        if (e.target.value) this._switchChain(e.target.value);
      });
    }

    // Chain action buttons listeners
    root.querySelectorAll("[data-chain-id]").forEach(el => {
      const chainId = el.dataset.chainId;
      if (el.textContent.includes("Edit")) {
        el.addEventListener("click", () => {
          // TODO: Open chain editor
          console.log("Edit chain:", chainId);
        });
      }
      if (el.textContent.includes("Test")) {
        el.addEventListener("click", () => {
          // TODO: Test chain execution
          console.log("Test chain:", chainId);
        });
      }
      if (el.textContent.includes("Delete")) {
        el.addEventListener("click", () => {
          // TODO: Delete chain
          console.log("Delete chain:", chainId);
        });
      }
    });

    // New chain button
    root.getElementById("btn-new-chain")?.addEventListener("click", () => {
      // Show template selector to create new chain
      this._showTemplateSelector();
    });


    // History filter listeners
    root.getElementById("history-filter-chain")?.addEventListener("change", (e) => {
      this._historyFilters.chainId = e.target.value || null;
    });
    root.getElementById("history-filter-status")?.addEventListener("change", (e) => {
      this._historyFilters.status = e.target.value || null;
    });
    root.getElementById("history-filter-search")?.addEventListener("input", (e) => {
      this._historyFilters.searchText = e.target.value;
    });
    root.getElementById("history-apply-filters")?.addEventListener("click", () => {
      this._applyHistoryFilters();
    });
    root.getElementById("history-reset-filters")?.addEventListener("click", () => {
      this._historyFilters = { chainId: null, status: null, startDate: null, endDate: null, searchText: "" };
      this._selectedExecDetail = null;
      this._applyHistoryFilters();
    });
    
    // Execution detail row expand/collapse
    root.querySelectorAll(".btn-expand").forEach(el => {
      el.addEventListener("click", async (e) => {
        const execId = e.target.dataset.execId;
        if (this._selectedExecDetail === execId) {
          this._selectedExecDetail = null;
        } else {
          const detail = await this._getExecutionDetail(execId);
          if (detail) {
            this._selectedExecDetail = execId;
            // Update execution record with full details
            const idx = this._execHistory.findIndex(e => e.id === execId);
            if (idx >= 0) this._execHistory[idx] = detail;
          }
        }
        this._render();
      });
    });
    
    // Export execution as JSON
    root.querySelectorAll("[id^='btn-export-exec-']").forEach(el => {
      el.addEventListener("click", (e) => {
        const execId = e.target.id.replace('btn-export-exec-', '');
        const exec = this._execHistory.find(e => e.id === execId);
        if (exec) {
          const json = JSON.stringify(exec, null, 2);
          const blob = new Blob([json], { type: 'application/json' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `execution-${execId}.json`;
          a.click();
          URL.revokeObjectURL(url);
        }
      });
    });
    root.querySelectorAll(".btn-test").forEach(el =>
      el.addEventListener("click", () => this._test(el.dataset.id)));
    root.querySelectorAll(".btn-edit:not(.btn-edit-group)").forEach(el =>
      el.addEventListener("click", () => this._openEdit(el.dataset.id)));
    root.querySelectorAll(".btn-delete:not(.btn-delete-group)").forEach(el =>
      el.addEventListener("click", () => this._delete(el.dataset.id)));

    root.querySelectorAll(".btn-edit-group").forEach(el =>
      el.addEventListener("click", () => this._openEditGroup(el.dataset.id)));
    root.querySelectorAll(".btn-delete-group").forEach(el =>
      el.addEventListener("click", () => this._deleteGroup(el.dataset.id)));

    root.getElementById("close-form")?.addEventListener("click",  () => this._closeForm());
    
    // Dialog listeners
    root.getElementById("dialog-close")?.addEventListener("click", () => this._closeDialog());
    root.getElementById("dialog-cancel")?.addEventListener("click", () => this._closeDialog());
    
    root.getElementById("dialog-copy")?.addEventListener("click", () => {
      const textarea = root.getElementById("export-json");
      textarea.select();
      document.execCommand("copy");
      this._notify("JSON kopieret til clipboard ✓");
    });
    
    root.getElementById("dialog-import")?.addEventListener("click", async () => {
      const textarea = root.getElementById("import-json");
      const errorEl = root.getElementById("import-error");
      try {
        const data = JSON.parse(textarea.value);
        // TODO: Validate and import chain
        this._notify("Chain importeret ✓");
        this._closeDialog();
      } catch (e) {
        errorEl.textContent = "Ugyldig JSON: " + e.message;
        errorEl.style.display = "block";
      }
    });
    
    root.getElementById("dialog-create-chain")?.addEventListener("click", () => {
      const input = root.getElementById("chain-name-input");
      const name = input?.value?.trim();
      if (!name) {
        this._notify("Chain navn mangler.", "error");
        return;
      }
      this._createChainFromTemplate(this._dialog.data.templateId, name);
      this._closeDialog();
    });
    root.getElementById("cancel-form")?.addEventListener("click", () => this._closeForm());
    root.getElementById("save-form")?.addEventListener("click",   () => this._save());

    root.getElementById("close-cond-form")?.addEventListener("click",  () => this._closeCondForm());
    root.getElementById("cancel-cond-form")?.addEventListener("click", () => this._closeCondForm());
    root.getElementById("save-cond-form")?.addEventListener("click",   () => this._saveCond());

    root.getElementById("btn-add-cond")?.addEventListener("click", () => this._openAddCond());
    root.querySelectorAll(".btn-edit-cond").forEach(el =>
      el.addEventListener("click", () => this._openEditCond(el.dataset.id)));
    root.querySelectorAll(".btn-delete-cond").forEach(el =>
      el.addEventListener("click", () => this._deleteCond(el.dataset.id)));

    root.getElementById("close-group-form")?.addEventListener("click",  () => this._closeGroupForm());
    root.getElementById("cancel-group-form")?.addEventListener("click", () => this._closeGroupForm());
    root.getElementById("save-group-form")?.addEventListener("click",   () => this._saveGroup());

    const searchInput = root.getElementById("search-input");
    searchInput?.addEventListener("input", (e) => this._onSearch(e.target.value));
    if (searchInput && this._searchQuery) {
      searchInput.focus();
      searchInput.setSelectionRange(searchInput.value.length, searchInput.value.length);
    }

    const slider = root.getElementById("vol-slider");
    const label  = root.getElementById("vol-display");
    slider?.addEventListener("input", () => {
      if (label) label.textContent = Math.round(parseFloat(slider.value) * 100) + "%";
    });
  }

  // ── CSS ────────────────────────────────────────────────────────────────────

  _css() {
    return `
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

    :host {
      display: flex; flex-direction: column; height: 100%;
      --accent:      #14b8a6;
      --accent2:     #34d399;
      --accent-glow: rgba(20,184,166,0.15);
      --bg:   var(--primary-background-color,   #0f1923);
      --bg2:  var(--secondary-background-color, #1a2535);
      --bg3:  #243044;
      --text: var(--primary-text-color,   #e2e8f0);
      --sub:  var(--secondary-text-color, #94a3b8);
      --div:  var(--divider-color, rgba(148,163,184,0.12));
      --green:  #10b981; --orange: #f59e0b; --red: #ef4444;
      --card-radius: 18px;
      font-family: 'DM Sans', var(--paper-font-body1_-_font-family, sans-serif);
      font-size: 14px; color: var(--text);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }

    .panel { display: flex; flex-direction: column; min-height: 100%; background: var(--bg); }
    .panel-topbar { flex-shrink: 0; }
    .panel-scroll { flex: 1; min-height: 0; overflow-y: auto; overflow-x: hidden; }

    /* ── Topbar ── */
    .topbar { display: flex; align-items: center; justify-content: space-between;
      padding: 16px 24px 12px; background: var(--bg);
      border-bottom: 1px solid var(--div); flex-wrap: wrap; gap: 12px; }
    .topbar-title { display: flex; align-items: center; gap: 12px; }
    .header-icon {
      width: 42px; height: 42px; flex-shrink: 0;
      background: linear-gradient(135deg, var(--accent), var(--accent2));
      border-radius: 12px; display: flex; align-items: center;
      justify-content: center; font-size: 22px;
      box-shadow: 0 4px 12px var(--accent-glow);
    }
    .logo-img {
      width: 85%; height: 85%; object-fit: contain; object-position: center;
    }
    .header-text { display: flex; flex-direction: column; gap: 1px; }
    .header-name { font-size: 18px; font-weight: 700; color: var(--text); }
    .header-sub  { font-size: 11px; font-weight: 500; color: var(--sub);
      text-transform: uppercase; letter-spacing: 0.06em; }
    .topbar-actions { display: flex; gap: 8px; flex-wrap: wrap; }
    .header-version { font-size: 9px; font-weight: 400; color: var(--sub); opacity: 0.7; margin-top: 2px; }

    /* ── Tab bar ── */
    .tab-bar { display: flex; gap: 4px; padding: 8px 24px 0;
      background: var(--bg); border-bottom: 1px solid var(--div); }
    .tab {
      padding: 7px 16px; border-radius: 8px 8px 0 0;
      font-family: 'DM Sans', sans-serif; font-size: 13px; font-weight: 500;
      cursor: pointer; color: var(--sub); background: transparent; border: none;
      border-bottom: 2px solid transparent; transition: color .15s, border-color .15s;
    }
    .tab:hover { color: var(--text); }
    .tab.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }

    /* ── Search ── */
    .searchbar { padding: 10px 24px; background: var(--bg); border-bottom: 1px solid var(--div); }
    .search-input {
      width: 100%; padding: 9px 14px;
      border: 1px solid var(--div); border-radius: 10px;
      background: var(--bg2); color: var(--text);
      font-family: 'DM Sans', sans-serif; font-size: 14px; transition: border-color .15s;
    }
    .search-input:focus { outline: none; border-color: var(--accent); }
    .search-input::placeholder { color: var(--sub); }

    /* ── Stats bar ── */
    .stats-bar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
      padding: 10px 24px; background: var(--bg); border-bottom: 1px solid var(--div); }
    .stat-pill { font-size: 12px; font-weight: 600; padding: 4px 12px; border-radius: 20px; white-space: nowrap; }
    .pill-neutral { background: var(--bg2); color: var(--sub); border: 1px solid var(--div); }
    .pill-accent  { background: rgba(20,184,166,0.12); color: var(--accent); border: 1px solid rgba(20,184,166,0.25); }
    .pill-ok      { background: rgba(16,185,129,0.12); color: var(--green); border: 1px solid rgba(16,185,129,0.25); }
    .pill-quiet   { background: rgba(245,158,11,0.12); color: var(--orange); border: 1px solid rgba(245,158,11,0.25); }

    /* ── Notification ── */
    .notif { margin: 14px 24px 0; padding: 11px 16px; border-radius: 10px; font-size: 13px; font-weight: 500; }

    /* ── Content area ── */
    .content-area { padding: 16px 24px; display: flex; flex-direction: column; gap: 10px; }
    .empty { text-align: center; color: var(--sub); padding: 60px 20px; font-size: 15px; line-height: 1.8; }
    .empty strong { color: var(--accent); }

    /* ── Cards ── */
    .event-card {
      background: var(--bg2); border-radius: var(--card-radius);
      padding: 16px 18px; border: 1px solid var(--div);
      display: flex; flex-direction: column; gap: 8px; transition: border-color 0.2s;
    }
    .event-card:hover { border-color: rgba(148,163,184,0.28); }
    .event-top { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .event-id { font-size: 14px; font-weight: 600; font-family: 'DM Mono', monospace; color: var(--accent); }
    .badge { font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 20px; white-space: nowrap; }
    .badge-cond { background: rgba(139,92,246,0.12); color: #8b5cf6; border: 1px solid rgba(139,92,246,0.25); }
    .event-message { font-size: 14px; color: var(--text); }
    .event-meta { display: flex; gap: 16px; flex-wrap: wrap; }
    .event-speakers, .event-volume { font-size: 12px; color: var(--sub); font-family: 'DM Mono', monospace; }
    .event-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 4px; }

    /* ── History ── */
    .history-list { display: flex; flex-direction: column; gap: 6px; }
    .history-row {
      display: grid; grid-template-columns: 80px 140px 1fr 90px;
      align-items: center; gap: 12px;
      background: var(--bg2); border-radius: 10px;
      padding: 10px 14px; border: 1px solid var(--div); font-size: 12px;
    }
    .history-time   { color: var(--sub); font-family: 'DM Mono', monospace; }
    .history-id     { color: var(--accent); font-family: 'DM Mono', monospace; font-weight: 600;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .history-msg    { color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .history-status { font-weight: 600; font-size: 11px; text-align: right; }

    /* ── Buttons ── */
    .btn {
      padding: 7px 14px; border: none; border-radius: 8px;
      font-family: 'DM Sans', sans-serif; font-size: 13px; font-weight: 600;
      cursor: pointer; transition: opacity .15s, transform .1s;
    }
    .btn:hover   { opacity: .85; transform: translateY(-1px); }
    .btn:active  { transform: translateY(0); }
    .btn:disabled { opacity: .4; cursor: not-allowed; transform: none; }
    .btn-add     { background: var(--accent); color: #0f1923; }
    .btn-refresh { background: var(--bg2); color: var(--sub); border: 1px solid var(--div); }
    .btn-test    { background: rgba(20,184,166,0.12); color: var(--accent); border: 1px solid rgba(20,184,166,0.25); }
    .btn-edit    { background: rgba(245,158,11,0.12); color: var(--orange); border: 1px solid rgba(245,158,11,0.25); }
    .btn-delete  { background: rgba(239,68,68,0.10); color: var(--red); border: 1px solid rgba(239,68,68,0.25); }
    .btn-save    { background: var(--accent); color: #0f1923; }
    .btn-cancel  { background: transparent; color: var(--sub); border: 1px solid var(--div); }
    .btn-export  { background: rgba(20,184,166,0.08); color: var(--accent); border: 1px solid rgba(20,184,166,0.2); }
    .btn-import  { background: rgba(52,211,153,0.08); color: var(--accent2); border: 1px solid rgba(52,211,153,0.2); }
    .btn-reload  { background: rgba(99,102,241,0.10); color: #818cf8; border: 1px solid rgba(99,102,241,0.25); }

    /* ── Dialog system ── */
    .dialog-overlay, .form-overlay {
      position: fixed; inset: 0; background: rgba(0,0,0,.6);
      display: flex; align-items: center; justify-content: center;
      z-index: 9999; padding: 20px;
    }
    .dialog-card, .form-card {
      background: var(--bg2); border-radius: var(--card-radius);
      width: 100%; max-width: 560px; max-height: 90vh;
      display: flex; flex-direction: column; overflow: hidden;
      border: 1px solid var(--div);
      box-shadow: 0 24px 56px rgba(0,0,0,.5), 0 0 0 1px rgba(20,184,166,0.08);
    }
    .dialog-header, .form-header {
      display: flex; align-items: center; justify-content: space-between;
      padding: 18px 20px; border-bottom: 1px solid var(--div);
    }
    .dialog-header span, .form-title {
      font-size: 16px; font-weight: 700; color: var(--text);
    }
    .dialog-close, .close-btn {
      background: transparent; border: none; font-size: 16px;
      cursor: pointer; color: var(--sub); padding: 5px 9px; border-radius: 8px; transition: background .15s;
    }
    .dialog-close:hover, .close-btn:hover {
      background: var(--bg3); color: var(--text);
    }
    .dialog-body, .form-body {
      overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 18px; flex: 1;
    }
    .dialog-footer, .form-footer {
      display: flex; gap: 10px; justify-content: flex-end; padding: 16px 20px; border-top: 1px solid var(--div);
    }

    /* ── Form overlay ── */
    .form-overlay {
    .form-card {
      background: var(--bg2); border-radius: var(--card-radius);
      width: 100%; max-width: 560px; max-height: 90vh;
      display: flex; flex-direction: column; overflow: hidden;
      border: 1px solid var(--div);
      box-shadow: 0 24px 56px rgba(0,0,0,.5), 0 0 0 1px rgba(20,184,166,0.08);
    }
    .form-header { display: flex; align-items: center; justify-content: space-between;
      padding: 18px 20px; border-bottom: 1px solid var(--div); }
    .form-title { font-size: 16px; font-weight: 700; color: var(--text); }
    .close-btn { background: transparent; border: none; font-size: 16px;
      cursor: pointer; color: var(--sub); padding: 5px 9px; border-radius: 8px; transition: background .15s; }
    .close-btn:hover { background: var(--bg3); color: var(--text); }
    .form-body { overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 18px; flex: 1; }
    .form-footer { display: flex; gap: 10px; justify-content: flex-end; padding: 16px 20px; border-top: 1px solid var(--div); }

    /* ── Form fields ── */
    .field { display: flex; flex-direction: column; gap: 6px; }
    .field-label { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--sub); }
    .hint-inline { font-weight: 400; text-transform: none; letter-spacing: 0; font-size: 10px; }
    .req  { color: var(--red); }
    .hint { font-size: 11px; color: var(--sub); margin-top: 2px; }
    .input {
      width: 100%; padding: 9px 12px;
      border: 1px solid var(--div); border-radius: 8px;
      background: var(--bg3); color: var(--text);
      font-family: 'DM Sans', sans-serif; font-size: 14px; transition: border-color .15s;
    }
    .input:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-glow); }
    input[readonly] { opacity: .5; cursor: default; }
    
    /* ── Error states ── */
    .field.error .input { border-color: var(--red); background: rgba(239,68,68,0.05); }
    .field.error .input:focus { border-color: var(--red); box-shadow: 0 0 0 2px rgba(239,68,68,0.15); }
    .error-message { font-size: 12px; color: var(--red); font-weight: 500; margin-top: 2px; }
    .f-volume { width: 100%; accent-color: var(--accent); cursor: pointer; margin-top: 4px; }

    /* ── Condition library ── */
    .cond-lib-section {
      margin-top: 20px;
      border-top: 1px solid var(--div);
      padding-top: 16px;
    }
    .cond-lib-header {
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 10px;
    }
    .section-title {
      font-size: 11px; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.08em; color: var(--sub);
    }
    .btn-add-sm {
      padding: 5px 12px; border: none; border-radius: 7px;
      font-family: 'DM Sans', sans-serif; font-size: 12px; font-weight: 600;
      cursor: pointer; background: rgba(20,184,166,0.12);
      color: var(--accent); border: 1px solid rgba(20,184,166,0.25);
      transition: opacity .15s;
    }
    .btn-add-sm:hover { opacity: .8; }
    .cond-lib-empty { font-size: 13px; color: var(--sub); padding: 8px 0; }
    .cond-lib-list { display: flex; flex-direction: column; gap: 6px; }
    .cond-row {
      display: flex; align-items: center; justify-content: space-between;
      background: var(--bg2); border-radius: 10px;
      padding: 10px 14px; border: 1px solid var(--div);
    }
    .cond-row-info { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    .cond-label { font-size: 13px; font-weight: 600; color: var(--text); }
    .cond-meta  { font-size: 11px; color: var(--sub); font-family: 'DM Mono', monospace; }
    .cond-code  {
      background: rgba(20,184,166,0.12); color: var(--accent);
      padding: 1px 5px; border-radius: 4px; font-size: 10px;
    }
    .cond-row-actions { display: flex; gap: 6px; flex-shrink: 0; margin-left: 12px; }
    .cond-list {
      display: flex; flex-direction: column; gap: 4px;
      border: 1px solid var(--div); border-radius: 10px;
      padding: 8px 12px; background: var(--bg3);
    }

    /* ── Speaker list ── */
    .speakers-list {
      display: flex; flex-direction: column; gap: 4px;
      max-height: 220px; overflow-y: auto;
      border: 1px solid var(--div); border-radius: 10px;
      padding: 10px 12px; background: var(--bg3);
    }
    .speaker-section-label {
      font-size: 10px; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.08em; color: var(--sub); padding: 6px 0 2px; margin-top: 4px;
    }
    .speaker-section-label:first-child { margin-top: 0; }
    .speaker-label { display: flex; align-items: center; gap: 10px; cursor: pointer; padding: 5px 0; }
    .speaker-label input[type=checkbox] { width: 16px; height: 16px; accent-color: var(--accent); cursor: pointer; flex-shrink: 0; }
    .speaker-name   { font-size: 14px; font-weight: 500; flex: 1; color: var(--text); }
    .speaker-entity { font-size: 11px; color: var(--sub); font-family: 'DM Mono', monospace; }
    .no-players { color: var(--sub); font-size: 13px; padding: 8px 0; }


    /* ── Chain UI ── */
    .chains-container { padding: 20px; }
    .chains-header {
      display: flex; justify-content: space-between; align-items: center;
      margin-bottom: 20px;
    }
    .chains-header h3 {
      margin: 0; font-size: 18px; color: var(--text);
    }
    .chain-switcher {
      display: flex; align-items: center; gap: 12px;
      margin-bottom: 20px; padding: 12px;
      background: var(--bg2); border-radius: 10px;
    }
    .chain-selector-label {
      font-size: 12px; font-weight: 600; color: var(--sub);
      text-transform: uppercase; letter-spacing: 0.05em;
    }
    .chain-selector {
      flex: 1; padding: 8px 12px; border: 1px solid var(--div);
      border-radius: 8px; background: var(--bg3); color: var(--text);
      font-family: 'DM Sans', sans-serif; font-size: 14px; cursor: pointer;
    }
    .chains-list {
      display: flex; flex-direction: column; gap: 12px;
    }
    .chain-card {
      background: var(--bg2); border: 1px solid var(--div); border-radius: 12px;
      padding: 16px; transition: box-shadow 0.2s;
    }
    .chain-card:hover { box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); }
    .chain-header {
      display: flex; justify-content: space-between; align-items: flex-start;
      margin-bottom: 12px;
    }
    .chain-info {
      display: flex; gap: 10px; align-items: center;
    }
    .chain-name {
      margin: 0; font-size: 16px; font-weight: 600; color: var(--text);
    }
    .chain-status {
      display: inline-block; padding: 4px 10px; border-radius: 20px;
      font-size: 11px; font-weight: 600; color: white;
    }
    .status-active { background-color: #10b981; }
    .status-published { background-color: #3b82f6; }
    .status-draft { background-color: #8b5cf6; }
    .chain-steps {
      text-align: right;
    }
    .chain-recent-execs {
      display: flex; flex-direction: column; gap: 6px;
      margin: 10px 0; padding: 10px; background: rgba(0, 0, 0, 0.05);
      border-radius: 8px;
    }
    .exec-badge {
      display: inline-block; padding: 4px 8px; border-radius: 6px;
      font-size: 11px; font-weight: 600; background: rgba(200, 200, 200, 0.2);
      width: fit-content;
    }
    .exec-badge.success { background: rgba(16, 185, 129, 0.2); color: #10b981; }
    .exec-badge.error { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
    .chain-actions {
      display: flex; gap: 8px; justify-content: flex-end;
    }

    /* ── Execution History ── */
    .execution-history {
      display: flex; flex-direction: column; gap: 16px; padding: 20px;
    }
    .exec-history-header {
      display: flex; justify-content: space-between; align-items: center;
      margin-bottom: 12px;
    }
    .exec-history-header h3 {
      margin: 0; font-size: 18px; color: var(--text);
    }
    .execution-card {
      background: var(--bg2); border: 1px solid var(--div);
      border-radius: 12px; padding: 14px; overflow: hidden;
    }
    .exec-header {
      display: grid; grid-template-columns: 1fr auto auto;
      gap: 12px; align-items: center; margin-bottom: 12px;
    }
    .exec-info h4 {
      margin: 0 0 4px; font-size: 14px; color: var(--text);
    }
    .exec-info small {
      color: var(--sub); font-size: 12px;
    }
    .exec-status-badge {
      padding: 6px 12px; border-radius: 6px; font-size: 12px;
      font-weight: 600; text-align: center; min-width: 100px;
    }
    .exec-status-badge.success {
      background: rgba(16, 185, 129, 0.2); color: #10b981;
    }
    .exec-status-badge.error {
      background: rgba(239, 68, 68, 0.2); color: #ef4444;
    }
    .exec-duration {
      text-align: right; font-size: 12px; color: var(--sub);
    }
    .steps-detail {
      display: flex; flex-direction: column; gap: 6px;
      padding: 10px; background: rgba(0, 0, 0, 0.05);
      border-radius: 8px;
    }
    .steps-label {
      font-size: 11px; font-weight: 600; color: var(--sub);
      text-transform: uppercase; letter-spacing: 0.05em;
    }
    .step-row {
      display: grid; grid-template-columns: 30px 1fr 40px 60px;
      gap: 8px; align-items: center; padding: 6px;
      background: var(--bg3); border-radius: 6px; font-size: 12px;
    }
    .step-index {
      text-align: center; font-weight: 600; color: var(--sub);
    }
    .step-type {
      color: var(--text); font-family: 'DM Mono', monospace;
    }
    .step-status {
      text-align: center; font-weight: 600;
    }
    .step-status.ok { color: #10b981; }
    .step-status.fail { color: #ef4444; }
    .step-time {
      text-align: right; color: var(--sub); font-size: 11px;
    }


    /* ── Template Selector Modal ── */
    .modal {
      position: fixed; top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0,0,0,0.6); display: flex; align-items: center;
      justify-content: center; z-index: 1000;
    }
    .template-selector-modal {
      background: var(--bg2); border-radius: var(--card-radius);
      border: 1px solid var(--div); padding: 24px;
      max-width: 500px; width: 90%; max-height: 80vh;
      overflow-y: auto;
    }
    .template-selector-modal h3 { margin-bottom: 16px; color: var(--text); }
    .template-list {
      display: grid; grid-template-columns: 1fr; gap: 12px; margin-bottom: 16px;
    }
    .template-card {
      background: var(--bg3); border: 1px solid var(--div); border-radius: 10px;
      padding: 12px; cursor: pointer; transition: all 0.2s;
    }
    .template-card:hover {
      border-color: var(--accent); background: rgba(20,184,166,0.08);
    }
    .template-card h4 { color: var(--text); margin-bottom: 4px; font-size: 14px; }
    .template-card p { color: var(--sub); font-size: 12px; margin-bottom: 8px; }
    .template-card small { color: var(--accent); font-weight: 500; }
    .modal-actions {
      display: flex; gap: 8px; justify-content: flex-end;
    }

        /* ── Responsive ── */
    @media (max-width: 600px) {
      .topbar      { padding: 12px 16px 8px; }
      .tab-bar     { padding: 6px 16px 0; }
      .searchbar   { padding: 10px 16px; }
      .stats-bar   { padding: 8px 16px; }
      .content-area { padding: 12px 16px; }
      .notif       { margin: 12px 16px 0; }
      .history-row { grid-template-columns: 70px 1fr 80px; }
      .history-id  { display: none; }
    }
    `;
  }
}

if (!customElements.get("house-voice-panel")) {
  customElements.define("house-voice-panel", HouseVoicePanel);
}

  async _loadTemplates() {
    try {
      const result = await this._hass.callWS({
        type: "house_voice/get_chain_templates",
      });
      this._templates = result.templates || {};
    } catch (e) {
      console.error("[House Voice] Error loading chain templates:", e);
      this._templates = {};
    }
  }

  _showTemplateSelector() {
    const templateIds = Object.keys(this._templates || {});
    if (!templateIds.length) {
      alert("Ingen templates tilgængelige");
      return;
    }

    const html = `
      <div class="template-selector-modal">
        <h3>Vælg Chain Template</h3>
        <div class="template-list">
          ${templateIds.map(id => {
            const tmpl = this._templates[id];
            return `
              <div class="template-card" data-template-id="${this._esc(id)}">
                <h4>${this._esc(tmpl.name)}</h4>
                <p>${this._esc(tmpl.description)}</p>
                <small>${tmpl.step_count} steps</small>
              </div>
            `;
          }).join("")}
        </div>
        <div class="modal-actions">
          <button class="btn btn-secondary" id="btn-cancel-template">Annuller</button>
        </div>
      </div>
    `;

    const modal = document.createElement("div");
    modal.className = "modal";
    modal.innerHTML = html;
    this.shadowRoot.appendChild(modal);

    // Event listeners
    document.querySelectorAll(".template-card").forEach(card => {
      card.addEventListener("click", () => {
        const templateId = card.dataset.templateId;
        this._createChainFromTemplate(templateId);
        modal.remove();
      });
    });

    document.getElementById("btn-cancel-template").addEventListener("click", () => {
      modal.remove();
    });
  }

  async _createChainFromTemplate(templateId) {
    const template = this._templates[templateId];
    if (!template) return;

    const chainName = prompt(`Navn på nyt chain fra "${template.name}":`, template.name);
    if (!chainName) return;

    try {
      const chainId = `chain_${Date.now()}`;
      const chainData = {
        id: chainId,
        name: chainName,
        status: "draft",
        steps: JSON.parse(JSON.stringify(template.steps)), // Deep copy
        created: new Date().toISOString(),
        modified: new Date().toISOString(),
      };

      await this._hass.callWS({
        type: "house_voice/chain/create",
        ...chainData,
      });

      this._showNotification(`✓ Chain '${chainName}' oprettet fra template`, "success");
      await this._loadChains();
      this._render();
    } catch (e) {
      console.error("[House Voice] Error creating chain from template:", e);
      this._showNotification("✗ Fejl ved oprettelse af chain", "error");
    }
  }
