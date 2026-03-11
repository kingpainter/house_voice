// File: house-voice-panel.js
// Version: 2.0.0
// Description: House Voice Manager sidebar panel.
//              Lists all voice events with Add / Edit / Test / Delete actions.
//              Media players are loaded automatically from HA media_player domain.

class HouseVoicePanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass         = null;
    this._events       = {};      // { event_id: { message, speakers, priority, volume } }
    this._players      = [];      // [{ entity_id, friendly_name }]
    this._editingId    = null;    // event_id being edited, or null for new
    this._showForm     = false;
    this._saving       = false;
    this._notification = null;    // { text, type: "success"|"error" }
    this._notifTimer   = null;
    this._searchQuery  = "";      // live filter string
  }

  set hass(h) {
    const first = !this._hass;
    this._hass = h;
    if (first) this._load();
  }

  connectedCallback() {
    this._render();
  }

  // ── Data loading ───────────────────────────────────────────────────────────

  async _load() {
    await Promise.all([this._loadEvents(), this._loadPlayers()]);
    this._render();
  }

  async _loadEvents() {
    try {
      const res = await this._hass.callWS({ type: "house_voice/get_events" });
      this._events = res.events || {};
    } catch (e) {
      console.error("House Voice: failed to load events", e);
      this._events = {};
    }
  }

  async _loadPlayers() {
    try {
      const res = await this._hass.callWS({ type: "house_voice/get_media_players" });
      this._players = res.media_players || [];
    } catch (e) {
      console.error("House Voice: failed to load media players", e);
      this._players = [];
    }
  }

  // ── Notifications ──────────────────────────────────────────────────────────

  _notify(text, type = "success") {
    clearTimeout(this._notifTimer);
    this._notification = { text, type };
    this._render();
    this._notifTimer = setTimeout(() => {
      this._notification = null;
      this._render();
    }, 3500);
  }

  // ── Actions ────────────────────────────────────────────────────────────────

  _openAdd() {
    this._editingId = null;
    this._showForm  = true;
    this._render();
  }

  _openEdit(eventId) {
    this._editingId = eventId;
    this._showForm  = true;
    this._render();
  }

  _closeForm() {
    this._showForm  = false;
    this._editingId = null;
    this._render();
  }

  async _save() {
    const root = this.shadowRoot;

    const eventId  = root.querySelector(".f-event-id")?.value?.trim();
    const message  = root.querySelector(".f-message")?.value?.trim();
    const priority = root.querySelector(".f-priority")?.value;
    const volume   = parseFloat(root.querySelector(".f-volume")?.value || "0.35");
    const speakers = [...root.querySelectorAll(".f-speaker:checked")].map(el => el.value);

    if (!eventId)          return this._notify("Event ID mangler.", "error");
    if (!message)          return this._notify("Besked mangler.", "error");
    if (speakers.length === 0) return this._notify("Vælg mindst én højttaler.", "error");

    this._saving = true;
    this._render();

    try {
      await this._hass.callWS({
        type:     "house_voice/save_event",
        event_id: eventId,
        message,
        speakers,
        priority,
        volume,
      });
      await this._loadEvents();
      this._closeForm();
      this._notify(`Event '${eventId}' gemt ✓`);
    } catch (e) {
      this._notify(`Fejl: ${e.message || e}`, "error");
    } finally {
      this._saving = false;
      this._render();
    }
  }

  async _delete(eventId) {
    if (!confirm(`Slet event '${eventId}'?`)) return;
    try {
      await this._hass.callWS({ type: "house_voice/delete_event", event_id: eventId });
      await this._loadEvents();
      this._notify(`Event '${eventId}' slettet.`);
    } catch (e) {
      this._notify(`Fejl: ${e.message || e}`, "error");
    }
  }

  async _test(eventId) {
    try {
      await this._hass.callWS({ type: "house_voice/test_event", event_id: eventId });
      this._notify(`🔊 '${eventId}' afspilles...`);
    } catch (e) {
      this._notify(`Fejl: ${e.message || e}`, "error");
    }
  }


  // ── Search ─────────────────────────────────────────────────────────────────

  _onSearch(value) {
    this._searchQuery = value.toLowerCase();
    this._render();
  }

  _filteredEvents() {
    if (!this._searchQuery) return this._events;
    return Object.fromEntries(
      Object.entries(this._events).filter(([id, ev]) =>
        id.toLowerCase().includes(this._searchQuery) ||
        (ev.message || "").toLowerCase().includes(this._searchQuery)
      )
    );
  }

  // ── Export ─────────────────────────────────────────────────────────────────

  _exportEvents() {
    const json = JSON.stringify(this._events, null, 2);
    const blob = new Blob([json], { type: "application/json" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = "house_voice_events.json";
    a.click();
    URL.revokeObjectURL(url);
    this._notify("Events eksporteret ✓");
  }

  // ── Import ─────────────────────────────────────────────────────────────────

  _importEvents() {
    const input = document.createElement("input");
    input.type  = "file";
    input.accept = ".json,application/json";
    input.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      try {
        const text   = await file.text();
        const parsed = JSON.parse(text);

        // Validate top-level structure
        if (typeof parsed !== "object" || Array.isArray(parsed)) {
          return this._notify("Ugyldig fil – forventet JSON objekt.", "error");
        }

        // Validate each event
        for (const [id, ev] of Object.entries(parsed)) {
          if (!ev.message || !ev.speakers || !ev.priority) {
            return this._notify(`Ugyldig event '${id}' – mangler felter.`, "error");
          }
        }

        // Save all events via WebSocket
        let count = 0;
        for (const [id, ev] of Object.entries(parsed)) {
          await this._hass.callWS({
            type:     "house_voice/save_event",
            event_id: id,
            message:  ev.message,
            speakers: Array.isArray(ev.speakers) ? ev.speakers : [ev.speakers],
            priority: ev.priority || "normal",
            volume:   ev.volume   || 0.35,
          });
          count++;
        }

        await this._loadEvents();
        this._notify(`${count} events importeret ✓`);
      } catch (err) {
        this._notify(`Import fejlede: ${err.message || err}`, "error");
      }
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

  // ── HTML builders ──────────────────────────────────────────────────────────

  _notifHTML() {
    if (!this._notification) return "";
    const { text, type } = this._notification;
    const bg  = type === "success" ? "#d1fae5" : "#fee2e2";
    const col = type === "success" ? "#065f46" : "#991b1b";
    return `<div class="notif" style="background:${bg};color:${col}">${this._esc(text)}</div>`;
  }

  _eventListHTML() {
    const filtered = this._filteredEvents();
    const ids = Object.keys(filtered);
    if (Object.keys(this._events).length === 0) {
      return `<div class="empty">Ingen voice events endnu.<br>Tryk <strong>+ Tilføj event</strong> for at komme i gang.</div>`;
    }
    if (ids.length === 0) {
      return `<div class="empty">Ingen events matcher "<strong>${this._esc(this._searchQuery)}</strong>".</div>`;
    }
    return ids.map(id => {
      const ev       = filtered[id];
      const speakers = (ev.speakers || []).join(", ");
      const priColor = this._priorityColor(ev.priority);
      return `
        <div class="event-card">
          <div class="event-top">
            <div class="event-id">${this._esc(id)}</div>
            <span class="badge" style="background:${priColor}22;color:${priColor};border:1px solid ${priColor}44">
              ${this._priorityLabel(ev.priority)}
            </span>
          </div>
          <div class="event-message">${this._esc(ev.message)}</div>
          <div class="event-speakers">📢 ${this._esc(speakers || "–")}</div>
          <div class="event-volume">🔊 Volumen: ${Math.round((ev.volume || 0.35) * 100)}%</div>
          <div class="event-actions">
            <button class="btn btn-test"   data-id="${this._esc(id)}">🧪 Test</button>
            <button class="btn btn-edit"   data-id="${this._esc(id)}">✏️ Rediger</button>
            <button class="btn btn-delete" data-id="${this._esc(id)}">🗑️ Slet</button>
          </div>
        </div>`;
    }).join("");
  }

  _speakerCheckboxesHTML(selectedSpeakers) {
    if (this._players.length === 0) {
      return `<div class="no-players">Ingen media_player entities fundet i Home Assistant.</div>`;
    }
    return this._players.map(p => {
      const checked = selectedSpeakers.includes(p.entity_id) ? "checked" : "";
      return `
        <label class="speaker-label">
          <input type="checkbox" class="f-speaker" value="${this._esc(p.entity_id)}" ${checked}>
          <span class="speaker-name">${this._esc(p.friendly_name)}</span>
          <span class="speaker-entity">${this._esc(p.entity_id)}</span>
        </label>`;
    }).join("");
  }

  _formHTML() {
    const isEdit  = this._editingId !== null;
    const ev      = isEdit ? (this._events[this._editingId] || {}) : {};
    const eventId = isEdit ? this._editingId : "";
    const msg     = ev.message   || "";
    const pri     = ev.priority  || "normal";
    const vol     = ev.volume    !== undefined ? ev.volume : 0.35;
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

            <div class="field">
              <label class="field-label">Event ID <span class="req">*</span></label>
              <input class="f-event-id input" type="text"
                value="${this._esc(eventId)}"
                placeholder="f.eks. dishwasher_open"
                ${isEdit ? "readonly" : ""}>
              <span class="hint">Bruges i automationer: house_voice.say → event: dishwasher_open</span>
            </div>

            <div class="field">
              <label class="field-label">Besked <span class="req">*</span></label>
              <input class="f-message input" type="text"
                value="${this._esc(msg)}"
                placeholder="f.eks. Opvaskeren er færdig">
            </div>

            <div class="field">
              <label class="field-label">Prioritet</label>
              <select class="f-priority input">
                <option value="info"     ${pri === "info"     ? "selected" : ""}>🎵 Info – duck musik</option>
                <option value="normal"   ${pri === "normal"   ? "selected" : ""}>🔔 Normal</option>
                <option value="critical" ${pri === "critical" ? "selected" : ""}>🚨 Critical – stopper altid igennem</option>
              </select>
            </div>

            <div class="field">
              <label class="field-label">Volumen: <span id="vol-display">${Math.round(vol * 100)}%</span></label>
              <input class="f-volume" type="range" min="0.05" max="1.0" step="0.05"
                value="${vol}" id="vol-slider">
            </div>

            <div class="field">
              <label class="field-label">Højttalere <span class="req">*</span></label>
              <div class="speakers-list">
                ${this._speakerCheckboxesHTML(selSpk)}
              </div>
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

  // ── Stats bar ──────────────────────────────────────────────────────────────

  _isQuietHours() {
    const h = new Date().getHours();
    return h >= 22 || h < 7;
  }

  _statsBarHTML() {
    const eventCount  = Object.keys(this._events).length;
    const quietActive = this._isQuietHours();
    const sensorState = this._hass?.states?.["sensor.house_voice_today"];
    const todayCount  = sensorState ? sensorState.state : "–";

    const quietLabel = quietActive
      ? `<span class="stat-pill pill-quiet">🌙 Quiet hours aktiv</span>`
      : `<span class="stat-pill pill-ok">☀️ Quiet hours inaktiv</span>`;

    return `
      <div class="stats-bar">
        <span class="stat-pill pill-neutral">📦 ${eventCount} events</span>
        <span class="stat-pill pill-neutral">📊 ${todayCount} i dag</span>
        ${quietLabel}
      </div>`;
  }

  // ── Main render ────────────────────────────────────────────────────────────

  _render() {
    this.shadowRoot.innerHTML = `
      <style>${this._css()}</style>
      <div class="panel">

        <div class="topbar">
          <div class="topbar-title">
            <span class="topbar-icon">🎙️</span>
            House Voice
          </div>
          <div class="topbar-actions">
            <button class="btn btn-import"  id="btn-import">📥 Import</button>
            <button class="btn btn-export"  id="btn-export">📤 Export</button>
            <button class="btn btn-refresh" id="btn-refresh">🔄 Opdater</button>
            <button class="btn btn-add"     id="btn-add">+ Tilføj event</button>
          </div>
        </div>

        <div class="searchbar">
          <input class="search-input" id="search-input" type="search"
            placeholder="🔍 Søg på event ID eller besked..."
            value="${this._esc(this._searchQuery)}">
        </div>

        ${this._statsBarHTML()}

        ${this._notifHTML()}

        <div class="event-list">
          ${this._eventListHTML()}
        </div>

        ${this._showForm ? this._formHTML() : ""}

      </div>`;

    this._bind();
  }

  // ── Event binding ──────────────────────────────────────────────────────────

  _bind() {
    const root = this.shadowRoot;

    root.getElementById("btn-add")?.addEventListener("click",     () => this._openAdd());
    root.getElementById("btn-refresh")?.addEventListener("click",  () => this._load());
    root.getElementById("btn-export")?.addEventListener("click",   () => this._exportEvents());
    root.getElementById("btn-import")?.addEventListener("click",   () => this._importEvents());

    // Live search
    const searchInput = root.getElementById("search-input");
    searchInput?.addEventListener("input", (e) => this._onSearch(e.target.value));
    // Keep cursor at end after re-render
    if (searchInput && this._searchQuery) {
      searchInput.focus();
      searchInput.setSelectionRange(searchInput.value.length, searchInput.value.length);
    }

    root.querySelectorAll(".btn-test").forEach(el =>
      el.addEventListener("click", () => this._test(el.dataset.id)));
    root.querySelectorAll(".btn-edit").forEach(el =>
      el.addEventListener("click", () => this._openEdit(el.dataset.id)));
    root.querySelectorAll(".btn-delete").forEach(el =>
      el.addEventListener("click", () => this._delete(el.dataset.id)));

    root.getElementById("close-form")?.addEventListener("click",  () => this._closeForm());
    root.getElementById("cancel-form")?.addEventListener("click", () => this._closeForm());
    root.getElementById("save-form")?.addEventListener("click",   () => this._save());

    // Live volume label
    const slider = root.getElementById("vol-slider");
    const label  = root.getElementById("vol-display");
    slider?.addEventListener("input", () => {
      if (label) label.textContent = Math.round(parseFloat(slider.value) * 100) + "%";
    });
  }

  // ── CSS ────────────────────────────────────────────────────────────────────

  _css() {
    return `
    :host {
      display: block;
      --accent: var(--primary-color, #6366f1);
      --text:   var(--primary-text-color, #1f2937);
      --sub:    var(--secondary-text-color, #6b7280);
      --card:   var(--card-background-color, #ffffff);
      --bg:     var(--secondary-background-color, #f3f4f6);
      --div:    var(--divider-color, #e5e7eb);
      font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
      font-size: 14px;
      color: var(--text);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }

    /* ── Layout ── */
    .panel { display: flex; flex-direction: column; min-height: 100vh;
      background: var(--bg); }

    /* ── Top bar ── */
    .topbar { display: flex; align-items: center; justify-content: space-between;
      padding: 16px 20px; background: var(--card);
      border-bottom: 1px solid var(--div); flex-wrap: wrap; gap: 10px; }
    .topbar-title { display: flex; align-items: center; gap: 10px;
      font-size: 20px; font-weight: 700; }
    .topbar-icon { font-size: 26px; }
    .topbar-actions { display: flex; gap: 8px; }

    /* ── Search bar ── */
    .searchbar { padding: 10px 20px; background: var(--card);
      border-bottom: 1px solid var(--div); }
    .search-input { width: 100%; padding: 8px 14px; border: 1px solid var(--div);
      border-radius: 8px; background: var(--bg); color: var(--text);
      font-size: 14px; transition: border-color .15s; }
    .search-input:focus { outline: none; border-color: var(--accent); }

    /* ── Stats bar ── */
    .stats-bar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
      padding: 10px 20px; background: var(--card);
      border-bottom: 1px solid var(--div); }
    .stat-pill { font-size: 12px; font-weight: 600; padding: 4px 12px;
      border-radius: 20px; white-space: nowrap; }
    .pill-neutral { background: var(--bg); color: var(--sub);
      border: 1px solid var(--div); }
    .pill-ok      { background: #d1fae5; color: #065f46; border: 1px solid #6ee7b7; }
    .pill-quiet   { background: #ede9fe; color: #5b21b6; border: 1px solid #c4b5fd; }

    /* ── Notification ── */
    .notif { margin: 16px 20px 0; padding: 12px 16px; border-radius: 10px;
      font-size: 13px; font-weight: 500; }

    /* ── Event list ── */
    .event-list { padding: 16px 20px; display: flex; flex-direction: column; gap: 12px; }
    .empty { text-align: center; color: var(--sub); padding: 60px 20px;
      font-size: 15px; line-height: 1.7; }

    /* ── Event card ── */
    .event-card { background: var(--card); border-radius: 14px;
      padding: 16px 18px; border: 1px solid var(--div);
      display: flex; flex-direction: column; gap: 8px; }
    .event-top { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    .event-id { font-size: 15px; font-weight: 700; font-family: monospace;
      color: var(--accent); }
    .badge { font-size: 11px; font-weight: 600; padding: 3px 10px;
      border-radius: 20px; white-space: nowrap; }
    .event-message { font-size: 14px; color: var(--text); }
    .event-speakers, .event-volume { font-size: 12px; color: var(--sub); }
    .event-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 4px; }

    /* ── Buttons ── */
    .btn { padding: 7px 14px; border: none; border-radius: 8px;
      font-size: 13px; font-weight: 600; cursor: pointer; transition: opacity .15s; }
    .btn:hover { opacity: .85; }
    .btn:disabled { opacity: .5; cursor: not-allowed; }
    .btn-add     { background: var(--accent); color: white; }
    .btn-refresh { background: var(--bg); color: var(--sub);
      border: 1px solid var(--div); }
    .btn-test    { background: #dbeafe; color: #1d4ed8; }
    .btn-edit    { background: #fef9c3; color: #854d0e; }
    .btn-delete  { background: #fee2e2; color: #991b1b; }
    .btn-save    { background: var(--accent); color: white; }
    .btn-cancel  { background: transparent; color: var(--sub);
      border: 1px solid var(--div); }
    .btn-export  { background: #e0f2fe; color: #0369a1;
      border: 1px solid #bae6fd; }
    .btn-import  { background: #f0fdf4; color: #166534;
      border: 1px solid #bbf7d0; }

    /* ── Form overlay ── */
    .form-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.45);
      display: flex; align-items: center; justify-content: center;
      z-index: 9999; padding: 20px; }
    .form-card { background: var(--card); border-radius: 18px;
      width: 100%; max-width: 540px; max-height: 90vh;
      display: flex; flex-direction: column; overflow: hidden;
      box-shadow: 0 24px 48px rgba(0,0,0,.25); }
    .form-header { display: flex; align-items: center; justify-content: space-between;
      padding: 18px 20px; border-bottom: 1px solid var(--div); }
    .form-title { font-size: 16px; font-weight: 700; }
    .close-btn { background: transparent; border: none; font-size: 18px;
      cursor: pointer; color: var(--sub); padding: 4px 8px; border-radius: 6px; }
    .close-btn:hover { background: var(--bg); }
    .form-body { overflow-y: auto; padding: 20px; display: flex;
      flex-direction: column; gap: 18px; flex: 1; }
    .form-footer { display: flex; gap: 10px; justify-content: flex-end;
      padding: 16px 20px; border-top: 1px solid var(--div); }

    /* ── Form fields ── */
    .field { display: flex; flex-direction: column; gap: 6px; }
    .field-label { font-size: 12px; font-weight: 700; text-transform: uppercase;
      letter-spacing: .5px; color: var(--sub); }
    .req { color: #ef4444; }
    .hint { font-size: 11px; color: var(--sub); }
    .input { width: 100%; padding: 9px 12px; border: 1px solid var(--div);
      border-radius: 8px; background: var(--bg); color: var(--text);
      font-size: 14px; transition: border-color .15s; }
    .input:focus { outline: none; border-color: var(--accent); }
    input[readonly] { opacity: .65; cursor: default; }

    /* ── Volume slider ── */
    .f-volume { width: 100%; accent-color: var(--accent); cursor: pointer; }

    /* ── Speaker checkboxes ── */
    .speakers-list { display: flex; flex-direction: column; gap: 8px;
      max-height: 200px; overflow-y: auto;
      border: 1px solid var(--div); border-radius: 8px; padding: 10px 12px; }
    .speaker-label { display: flex; align-items: center; gap: 10px; cursor: pointer;
      padding: 4px 0; }
    .speaker-label input[type=checkbox] { width: 16px; height: 16px;
      accent-color: var(--accent); cursor: pointer; flex-shrink: 0; }
    .speaker-name { font-size: 14px; font-weight: 500; flex: 1; }
    .speaker-entity { font-size: 11px; color: var(--sub); font-family: monospace; }
    .no-players { color: var(--sub); font-size: 13px; padding: 8px 0; }
    `;
  }
}

if (!customElements.get("house-voice-panel")) {
  customElements.define("house-voice-panel", HouseVoicePanel);
}
