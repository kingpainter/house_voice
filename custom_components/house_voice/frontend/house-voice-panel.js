// File: house-voice-panel.js
// Version: 2.2.0
// Description: House Voice Manager sidebar panel.
//              Tabs: Events | Groups | History
//              Design: Indeklima Designer – teal #14b8a6 / emerald #34d399

class HouseVoicePanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass         = null;
    this._events       = {};
    this._groups       = {};
    this._players      = [];
    this._history      = [];
    this._tab          = "events";       // "events" | "groups" | "history"
    this._editingId    = null;
    this._editingGroup = null;
    this._showForm     = false;
    this._showGroupForm = false;
    this._saving       = false;
    this._notification = null;
    this._notifTimer   = null;
    this._searchQuery  = "";
  }

  set hass(h) {
    const first = !this._hass;
    this._hass = h;
    if (first) this._load();
  }

  connectedCallback() { this._render(); }

  // ── Data loading ───────────────────────────────────────────────────────────

  async _load() {
    await Promise.all([
      this._loadEvents(),
      this._loadGroups(),
      this._loadPlayers(),
      this._loadHistory(),
    ]);
    this._render();
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

  // ── Event actions ──────────────────────────────────────────────────────────

  _openAdd()    { this._editingId = null; this._showForm = true; this._render(); }
  _openEdit(id) { this._editingId = id;   this._showForm = true; this._render(); }
  _closeForm()  { this._showForm = false; this._editingId = null; this._render(); }

  async _save() {
    const root = this.shadowRoot;
    const eventId   = root.querySelector(".f-event-id")?.value?.trim();
    const message   = root.querySelector(".f-message")?.value?.trim();
    const priority  = root.querySelector(".f-priority")?.value;
    const volume    = parseFloat(root.querySelector(".f-volume")?.value || "0.35");
    const condition = root.querySelector(".f-condition")?.value?.trim() || "";
    const speakers  = [...root.querySelectorAll(".f-speaker:checked")].map(el => el.value);

    if (!eventId)         return this._notify("Event ID mangler.", "error");
    if (!message)         return this._notify("Besked mangler.", "error");
    if (!speakers.length) return this._notify("Vælg mindst én højttaler eller gruppe.", "error");

    this._saving = true; this._render();
    try {
      await this._hass.callWS({
        type: "house_voice/save_event",
        event_id: eventId, message, speakers, priority, volume, condition,
      });
      await this._loadEvents();
      this._closeForm();
      this._notify(`Event '${eventId}' gemt ✓`);
    } catch (e) {
      this._notify(`Fejl: ${e.message || e}`, "error");
    } finally { this._saving = false; this._render(); }
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

    this._saving = true; this._render();
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
    } finally { this._saving = false; this._render(); }
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
        let count = 0;
        for (const [id, ev] of Object.entries(parsed)) {
          await this._hass.callWS({
            type: "house_voice/save_event",
            event_id: id, message: ev.message,
            speakers: Array.isArray(ev.speakers) ? ev.speakers : [ev.speakers],
            priority: ev.priority || "normal", volume: ev.volume || 0.35,
            condition: ev.condition || "",
          });
          count++;
        }
        await this._loadEvents();
        this._notify(`${count} events importeret ✓`);
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
      const condBadge = ev.condition
        ? `<span class="badge badge-cond" title="${this._esc(ev.condition)}">⚡ Betingelse</span>`
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

  _historyHTML() {
    if (!this._history.length)
      return `<div class="empty">Ingen historik endnu.<br>Afspil et event for at se det her.</div>`;

    return `
      <div class="history-list">
        ${this._history.map(h => {
          const s    = this._statusLabel(h.status);
          const time = h.timestamp
            ? new Date(h.timestamp).toLocaleTimeString("da-DK", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
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

  _formHTML() {
    const isEdit  = this._editingId !== null;
    const ev      = isEdit ? (this._events[this._editingId] || {}) : {};
    const eventId = isEdit ? this._editingId : "";
    const msg     = ev.message   || "";
    const pri     = ev.priority  || "normal";
    const vol     = ev.volume    !== undefined ? ev.volume : 0.35;
    const cond    = ev.condition || "";
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
              <input class="f-event-id input" type="text" value="${this._esc(eventId)}"
                placeholder="f.eks. dishwasher_done" ${isEdit ? "readonly" : ""}>
              <span class="hint">Bruges i automationer: house_voice.say → event: dishwasher_done</span>
            </div>
            <div class="field">
              <label class="field-label">Besked <span class="req">*</span></label>
              <input class="f-message input" type="text" value="${this._esc(msg)}"
                placeholder="f.eks. Opvaskeren er færdig">
            </div>
            <div class="field">
              <label class="field-label">Betingelse <span class="hint-inline">(Jinja2 – valgfrit)</span></label>
              <input class="f-condition input" type="text" value="${this._esc(cond)}"
                placeholder="{{ is_state('person.flemming', 'home') }}">
              <span class="hint">Eventet afspilles kun hvis betingelsen er sand. Lad stå tomt for altid at afspille.</span>
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
            <div class="field">
              <label class="field-label">Højttalere / Grupper <span class="req">*</span></label>
              <div class="speakers-list">${this._speakerCheckboxesHTML(selSpk)}</div>
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
                <button class="btn btn-add" id="btn-add">＋ Tilføj event</button>
              ` : isGroups ? `
                <button class="btn btn-refresh" id="btn-refresh">↺ Opdater</button>
                <button class="btn btn-add" id="btn-add-group">＋ Tilføj gruppe</button>
              ` : `
                <button class="btn btn-refresh" id="btn-refresh">↺ Opdater</button>
              `}
            </div>
          </div>
          <div class="tab-bar">
            <button class="tab ${isEvents  ? 'active' : ''}" data-tab="events">📋 Events</button>
            <button class="tab ${isGroups  ? 'active' : ''}" data-tab="groups">🔈 Grupper</button>
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
            ${isGroups  ? this._groupListHTML() : ""}
            ${isHistory ? this._historyHTML()   : ""}
          </div>
        </div>

        ${this._showForm      ? this._formHTML()      : ""}
        ${this._showGroupForm ? this._groupFormHTML() : ""}

      </div>`;

    this._bind();
  }

  // ── Event binding ──────────────────────────────────────────────────────────

  _bind() {
    const root = this.shadowRoot;

    root.querySelectorAll(".tab").forEach(el =>
      el.addEventListener("click", () => { this._tab = el.dataset.tab; this._render(); })
    );

    root.getElementById("btn-add")?.addEventListener("click",       () => this._openAdd());
    root.getElementById("btn-add-group")?.addEventListener("click", () => this._openAddGroup());
    root.getElementById("btn-refresh")?.addEventListener("click",   () => this._load());
    root.getElementById("btn-export")?.addEventListener("click",    () => this._exportEvents());
    root.getElementById("btn-import")?.addEventListener("click",    () => this._importEvents());

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
    root.getElementById("cancel-form")?.addEventListener("click", () => this._closeForm());
    root.getElementById("save-form")?.addEventListener("click",   () => this._save());

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

    /* ── Form overlay ── */
    .form-overlay {
      position: fixed; inset: 0; background: rgba(0,0,0,.6);
      display: flex; align-items: center; justify-content: center;
      z-index: 9999; padding: 20px;
    }
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
    .f-volume { width: 100%; accent-color: var(--accent); cursor: pointer; margin-top: 4px; }

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
