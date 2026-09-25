// File: house-voice-panel.js
// Version: 3.2.0
// Description: House Voice Manager sidebar panel.
//              Tabs: Events | Groups | History
//              Design: Indeklima Designer – teal #14b8a6 / emerald #34d399

class HouseVoicePanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
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
    this._currentChain  = null;    // currently active chain
    this._execHistory   = [];      // [ { chainId, timestamp, steps, success, duration } ]
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

  async _loadExecutionHistory() {
    try {
      this._execHistory = await this._hass.callWS({
        type: "house_voice/list_execution_history",
        limit: 50,
      }) || [];
    } catch (e) {
      console.error("[House Voice] Error loading execution history:", e);
      this._execHistory = [];
    }
  }

  _switchChain(chainId) {
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
    // Show chain execution history if available, otherwise show event history
    if (this._execHistory && this._execHistory.length > 0) {
      return `
        <div class="execution-history">
          <div class="exec-history-header">
            <h3>Chain Execution History</h3>
            <small>${this._execHistory.length} executions</small>
          </div>
          ${this._execHistory.map(exec => {
            const statusBadgeClass = exec.success ? 'success' : 'error';
            const statusLabel = exec.success ? '✓ Success' : '✗ Failed';
            const duration = exec.duration ? `${Math.round(exec.duration)}ms` : '–';
            const chainName = exec.chainId && this._chains[exec.chainId] 
              ? this._chains[exec.chainId].name 
              : exec.chainId;
            
            return `
              <div class="execution-card">
                <div class="exec-header">
                  <div class="exec-info">
                    <h4>${this._esc(chainName || 'Unknown Chain')}</h4>
                    <small>${this._formatTimestamp(exec.timestamp)}</small>
                  </div>
                  <div class="exec-status-badge ${statusBadgeClass}">
                    ${statusLabel}
                  </div>
                  <div class="exec-duration">
                    <small>${duration}</small>
                  </div>
                </div>
                
                ${exec.steps && exec.steps.length > 0 ? `
                  <div class="steps-detail">
                    <small class="steps-label">Steps (${exec.steps.length}):</small>
                    ${exec.steps.map((step, idx) => {
                      const stepStatus = step.success ? '✓' : '✗';
                      const stepTime = step.duration ? `${Math.round(step.duration)}ms` : '–';
                      return `
                        <div class="step-row">
                          <span class="step-index">${idx + 1}</span>
                          <span class="step-type">${this._esc(step.type || 'action')}</span>
                          <span class="step-status ${step.success ? 'ok' : 'fail'}">${stepStatus}</span>
                          <span class="step-time">${stepTime}</span>
                        </div>
                      `;
                    }).join("")}
                  </div>
                ` : ""}
              </div>
            `;
          }).join("")}
        </div>
      `;
    }

    // Fallback to event history
    if (!this._history.length)
      return `<div class="empty">Ingen historik endnu.<br>Afspil et event for at se det her.</div>`;

    return `
      <div class="history-list">
        ${this._history.map(h => {
          const s    = this._statusLabel(h.status);
          const date = h.timestamp ? new Date(h.timestamp) : null;
          const time = (date && !isNaN(date.getTime()))
            ? date.toLocaleTimeString("da-DK", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
            : "–";
          return `
            <div class="history-row">
              <span class="history-time">${time}</span>
              <span class="history-id">${this._esc(h.event_id)}</span>
              <span class="history-msg">${this._esc(h.message)}</span>
              <span class="history-status" style="color:${s.color}">${s.label}</span>
            </div>`;
        }).join("")}
      </div>`;
  }

  // ── Speaker checkboxes (events form) ──────────────────────────────────────

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
    const isHistory = this._tab === "history";

    this.shadowRoot.innerHTML = `
      <style>${this._css()}</style>
      <div class="panel">

        <div class="panel-topbar">
          <div class="topbar">
            <div class="topbar-title">
              <div class="header-icon">🎙️</div>
              <div class="header-text">
                <span class="header-name">House Voice</span>
                <span class="header-sub">Voice Event Manager</span>
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
      // TODO: Open chain creation dialog
      console.log("Create new chain");
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
    .header-text { display: flex; flex-direction: column; gap: 1px; }
    .header-name { font-size: 18px; font-weight: 700; color: var(--text); }
    .header-sub  { font-size: 11px; font-weight: 500; color: var(--sub);
      text-transform: uppercase; letter-spacing: 0.06em; }
    .topbar-actions { display: flex; gap: 8px; flex-wrap: wrap; }

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
