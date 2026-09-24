# Sprint 6: Option A Implementation — Frontend Event Chain Builder (v3.6.0)

> **Status:** Ready to Start  
> **Target Version:** 3.6.0  
> **Priority:** High (User-facing feature, foundation for other options)  
> **Estimated Duration:** 3-4 weeks (110-140 hours)  
> **Start Date:** 2026-09-24  

---

## Overview

**Goal:** Build a visual, drag-drop interface for creating and editing event chains in the sidebar panel.

**Current State:**
- House Voice v3.5.1 (Sprint 5 complete)
- Backend event chaining system mature and tested (218+ tests)
- Sidebar panel exists but only has 3 tabs (Events, Groups, History)
- No visual chain builder — users must manually create events

**Problem We're Solving:**
- Chains are backend structures, not visible to users
- No way to design/test chains visually
- Complex chains require deep backend understanding
- No export/import mechanism for sharing chains

**Outcome:**
- Users can drag-drop to build chains visually
- Chains saved to HA Storage API
- Test execution with mock events
- Export/import for backup and sharing

---

## Detailed Task Breakdown

### PHASE 1: Foundation (Weeks 1-2) — 40-50 hours

#### Week 1: Storage & Validation

##### Task 1.1: Chain Storage Layer (8 hours)
**File:** `custom_components/house_voice/storage.py`

```python
class HouseVoiceChains:
    """Manage event chains in .storage/house_voice_chains"""
    
    async def async_create_chain(self, chain_data: dict) -> str:
        """Create new chain, return chain_id"""
        
    async def async_update_chain(self, chain_id: str, chain_data: dict) -> bool:
        """Update existing chain"""
        
    async def async_delete_chain(self, chain_id: str) -> bool:
        """Delete chain"""
        
    async def async_get_chain(self, chain_id: str) -> dict:
        """Get single chain"""
        
    async def async_list_chains(self, status: str = "active") -> list:
        """List all chains, optionally filtered by status"""
        
    async def async_publish_chain(self, chain_id: str) -> bool:
        """Move chain from draft to active"""
```

**Storage Schema:**
```python
{
    "version": 1,
    "entries": {
        "chain_001": {
            "id": "chain_001",
            "name": "Alert on motion",
            "description": "Send alert when motion detected while away",
            "created": "2026-09-24T10:00:00Z",
            "modified": "2026-09-24T15:30:00Z",
            "status": "active",  # active | draft | archived
            "trigger": {  # What triggers this chain
                "type": "manual",  # manual | sensor | time | etc
                "entity_id": None,
                "event_type": None
            },
            "steps": [
                {
                    "id": "step_1",
                    "name": "Check away mode",
                    "action": "condition_check",
                    "target": "input_boolean.away_mode",
                    "parameters": {"state": "on"},
                    "filter": None,
                    "route_expression": None,
                    "transform": None,
                    "retry": {"max_attempts": 3, "backoff": "exponential"},
                    "circuit_breaker": {"enabled": False}
                },
                {
                    "id": "step_2",
                    "name": "Send alert",
                    "action": "announce",
                    "target": "media_player.living_room",
                    "parameters": {"message": "Motion detected"},
                    "filter": None,
                    "route_expression": None,
                    "transform": None,
                    "retry": {"max_attempts": 1},
                    "circuit_breaker": {"enabled": False}
                }
            ],
            "execution_config": {
                "parallel": False,  # Sequential or parallel execution
                "timeout": 300,     # Max seconds for entire chain
                "on_failure": "stop"  # stop | continue | rollback
            }
        }
    }
}
```

**Acceptance Criteria:**
- ✅ Storage reads/writes work correctly
- ✅ Chain CRUD operations tested (5 unit tests)
- ✅ Schema validation (version, required fields)
- ✅ Async operations all use `async/await`

##### Task 1.2: Chain Validation Engine (8 hours)
**File:** `custom_components/house_voice/events/chain_validator.py`

```python
class ChainValidator:
    """Validate chain structure and contents"""
    
    def validate_chain(self, chain: dict) -> ValidationResult:
        """
        Check for:
        - Structural errors (missing fields, invalid types)
        - Entity resolution (do targets exist?)
        - Expression syntax (valid Jinja2?)
        - DAG cycle detection (no loops)
        - Step dependency validity
        """
        
    def validate_jinja2(self, expression: str) -> bool:
        """Check if Jinja2 expression is valid"""
        
    def check_entity_exists(self, entity_id: str, hass) -> bool:
        """Verify entity exists in HA"""
        
    def detect_cycles(self, steps: list) -> list:
        """Find if chain has loops, return cycle path if found"""
```

**Validation Rules:**
1. All required fields present
2. Entity IDs valid (exist in HA)
3. Actions are registered (announce, delay, condition_check, etc.)
4. Jinja2 expressions compile without errors
5. No cycles in step dependencies
6. Parameter types match action expectations

**Error Messages (user-friendly):**
- "Entity 'media_player.unknown' does not exist"
- "Invalid Jinja2 in message: 'condition }} is missing opening {{'"
- "Circular dependency detected: step_1 → step_2 → step_1"
- "Unknown action type 'invalid_action'"

**Acceptance Criteria:**
- ✅ All 6 validation rules implemented
- ✅ Clear, actionable error messages
- ✅ 10+ unit tests covering edge cases
- ✅ Performance: validation <100ms for typical chain

##### Task 1.3: WebSocket Commands for CRUD (10 hours)
**Files:** `custom_components/house_voice/websocket.py` (extend existing)

Add to existing WebSocket handler:

```python
async def websocket_chain_create(hass, connection, msg):
    """house_voice/chain/create"""
    # Validate chain structure
    # Call HouseVoiceChains.async_create_chain()
    # Return chain_id or error
    
async def websocket_chain_update(hass, connection, msg):
    """house_voice/chain/update"""
    # Validate chain structure
    # Call HouseVoiceChains.async_update_chain()
    # Return success or error
    
async def websocket_chain_delete(hass, connection, msg):
    """house_voice/chain/delete"""
    # Check if chain exists
    # Call HouseVoiceChains.async_delete_chain()
    # Return success or error
    
async def websocket_chain_get(hass, connection, msg):
    """house_voice/chain/get"""
    # Retrieve single chain by ID
    
async def websocket_chain_list(hass, connection, msg):
    """house_voice/chain/list"""
    # List all chains with optional filters
    
async def websocket_chain_publish(hass, connection, msg):
    """house_voice/chain/publish"""
    # Move chain from draft to active
    
async def websocket_chain_validate(hass, connection, msg):
    """house_voice/chain/validate"""
    # Validate chain and return errors
```

**Command Syntax Examples:**
```javascript
// Create
connection.sendMessage({
  type: "house_voice/chain/create",
  id: 1,
  chain: {
    name: "Alert on motion",
    description: "...",
    steps: [...]
  }
});
// Response: { type: "result", success: true, chain_id: "chain_001" }

// Update
connection.sendMessage({
  type: "house_voice/chain/update",
  id: 2,
  chain_id: "chain_001",
  chain: {...}
});
// Response: { type: "result", success: true }

// Delete
connection.sendMessage({
  type: "house_voice/chain/delete",
  id: 3,
  chain_id: "chain_001"
});
// Response: { type: "result", success: true }

// Validate
connection.sendMessage({
  type: "house_voice/chain/validate",
  id: 4,
  chain: {...}
});
// Response: { type: "result", success: true, errors: [] }
```

**Acceptance Criteria:**
- ✅ All 7 WebSocket commands implemented
- ✅ Error handling for invalid requests
- ✅ Proper async/await for all operations
- ✅ 8+ unit tests for command handlers

##### Task 1.4: Chain Serialization (6 hours)
**File:** `custom_components/house_voice/events/chain_serializer.py`

```python
class ChainSerializer:
    """Convert between visual model and execution model"""
    
    def serialize_for_storage(self, visual_model: dict) -> dict:
        """Convert frontend visual model to storage format"""
        # Normalize field names
        # Validate all required fields
        # Add timestamps
        
    def serialize_for_execution(self, stored_chain: dict) -> list:
        """Convert storage format to EventChainManager execution format"""
        # Convert steps to EventChainManager ChainStep objects
        # Include retry/circuit_breaker configs
        
    def deserialize_from_storage(self, stored_chain: dict) -> dict:
        """Convert storage format to frontend visual model"""
        # Add UI-specific fields (ui_position, color, etc.)
```

**Acceptance Criteria:**
- ✅ Bidirectional conversion works (store → ui → store)
- ✅ No data loss in round-trip
- ✅ 6+ unit tests

---

#### Week 2: Validation Enhancements

##### Task 1.5: Entity & Action Resolver (6 hours)
**File:** `custom_components/house_voice/events/chain_resolver.py`

```python
class ChainResolver:
    """Resolve and validate chain references at edit time"""
    
    async def async_get_available_entities(
        self, 
        hass,
        domain: str = None,
        capabilities: list = None
    ) -> list:
        """Get entities matching criteria for target selection"""
        # Return: [{"entity_id": "...", "name": "...", "icon": "..."}]
        
    async def async_get_available_actions(self) -> list:
        """Get registered action types"""
        # Return: [{"id": "announce", "name": "Announce", "icon": "..."}]
        
    async def async_resolve_expression(
        self,
        expression: str,
        context: dict
    ) -> Any:
        """Evaluate expression with given context"""
        # Used for validation and testing
```

**Use Cases:**
1. User adds new step — UI calls `get_available_actions()` to show action palette
2. User selects "announce" — UI calls `get_available_entities(domain="media_player")` to show speaker list
3. User types Jinja2 expression — validate syntax real-time

**Acceptance Criteria:**
- ✅ Action list populated from registered handlers
- ✅ Entity lookup filters by domain
- ✅ Expression resolution works with mock context
- ✅ 4+ unit tests

##### Task 1.6: DAG Cycle Detection (8 hours)
**File:** `custom_components/house_voice/events/chain_graph.py`

```python
class ChainGraph:
    """Analyze chain structure for issues"""
    
    def build_graph(self, steps: list) -> dict:
        """Create adjacency list from steps"""
        # Each step can have multiple outputs (routing, conditions)
        
    def detect_cycles(self, graph: dict) -> list:
        """Find any cycles using DFS"""
        # Return: [[step_1, step_2, step_1], ...]  # cycle paths
        
    def topological_sort(self, graph: dict) -> list:
        """Get execution order if no cycles"""
        # Used for validation UI (show suggested order)
        
    def get_dependencies(self, step_id: str, graph: dict) -> list:
        """Get all steps that depend on this step"""
        # Used for impact analysis (delete = affect which steps)
```

**Algorithm:**
- Build directed graph from step connections
- Use depth-first search (DFS) to detect back edges
- Return all cycles found

**Acceptance Criteria:**
- ✅ Detects all cycle types
- ✅ Performance <50ms for 100-step chain
- ✅ 6+ unit tests (including complex cases)

##### Task 1.7: Integration Tests (8 hours)
**File:** `tests/components/house_voice/test_chain_builder_foundation.py`

Test coverage:
1. Create → Validate → Serialize → Store (full pipeline)
2. Retrieve → Deserialize → Validate
3. Update → Validate → Publish
4. Delete chain
5. Concurrent operations (two chains edited simultaneously)
6. Large chain (100+ steps) performance

**Acceptance Criteria:**
- ✅ 15+ integration tests
- ✅ All tests pass
- ✅ Coverage >90% for new code

---

### PHASE 2: UI Components (Weeks 2-4) — 50-70 hours

#### Week 2-3: Visual Builder Canvas

##### Task 2.1: Canvas Component (12 hours)
**File:** `custom_components/house_voice/frontend/house-voice-panel-chains-builder.js`

New web component class:

```javascript
class ChainBuilderCanvas extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    
    // SVG canvas for visual editing
    // Zoom/pan controls
    // Snap-to-grid
  }
  
  // Drag-drop event handlers
  handleDragOver(e) { ... }
  handleDrop(e) { ... }
  
  // Canvas rendering
  render() { ... }
  renderStep(step) { ... }
  renderConnection(from, to) { ... }
  
  // Interaction
  selectStep(stepId) { ... }
  deleteStep(stepId) { ... }
  connectSteps(fromId, toId) { ... }
}

customElements.define('hv-chain-builder-canvas', ChainBuilderCanvas);
```

**Features:**
1. **SVG-based rendering** — steps as boxes, connections as arrows
2. **Drag-drop support** — move steps on canvas
3. **Pan & zoom** — mouse wheel to zoom, space+drag to pan
4. **Snap-to-grid** — steps align to 20px grid
5. **Connection drawing** — drag from output of one step to input of next
6. **Right-click menu** — delete, duplicate, properties

**Visual Design (from Indeklima Designer):**
- Background: `var(--bg)`
- Step box: `var(--bg2)` with `var(--accent)` border when selected
- Connections: `var(--accent)` with `var(--accent2)` for hover
- Grid: light `var(--div)` grid

**Acceptance Criteria:**
- ✅ Steps drag and snap to grid
- ✅ Connections draw without crossing (or cross gracefully)
- ✅ Zoom (20-200%) works smoothly
- ✅ Pan works with space+drag
- ✅ Performance: <16ms render time (60fps) for 50-step chain

##### Task 2.2: Action Palette (8 hours)
**File:** `custom_components/house_voice/frontend/house-voice-panel-chains-palette.js`

```javascript
class ChainBuilderPalette extends HTMLElement {
  // Left sidebar with available actions
  // Group by category: TTS, Control, Logic, Delay
  // Drag action onto canvas to add step
  
  async connectedCallback() {
    this.actions = await this.getAvailableActions();
    this.render();
  }
  
  async getAvailableActions() {
    // Query backend for registered actions
    // Return: [
    //   { id: "announce", name: "Announce", category: "TTS", icon: "mdi:speaker" },
    //   { id: "delay", name: "Delay", category: "Flow", icon: "mdi:timer" },
    //   ...
    // ]
  }
  
  render() {
    // Category headers
    // Action chips with icons
    // Hover shows description
  }
  
  handleDragStart(e, action) {
    e.dataTransfer.effectAllowed = 'copy';
    e.dataTransfer.setData('action', JSON.stringify(action));
  }
}
```

**Actions to Show:**
1. **Announce** — TTS message to speakers
2. **Delay** — Wait N seconds
3. **Condition Check** — Evaluate condition
4. **Call Service** — Generic HA service call
5. **Set State** — Modify entity state
6. **Notify** — Send notification
7. **Log** — Log to system

**Acceptance Criteria:**
- ✅ Drag action onto canvas adds step
- ✅ Actions grouped by category
- ✅ Icons and descriptions
- ✅ 4+ actions available

##### Task 2.3: Step Node Component (10 hours)
**File:** `custom_components/house_voice/frontend/house-voice-panel-chains-step.js`

```javascript
class ChainStepNode extends HTMLElement {
  // Represents single step on canvas
  
  constructor(step) {
    super();
    this.step = step;
    this.attachShadow({ mode: 'open' });
  }
  
  render() {
    // Box with:
    // - Step icon (action type)
    // - Step name
    // - Status indicator (valid, error, warning)
    // - Output connectors (bottom)
    // - Input connector (top)
  }
  
  // Editing
  editProperties() {
    // Show property panel
  }
  
  // Validation display
  showErrors(errors) {
    // Red border, tooltip with errors
  }
  
  // Drag handling
  handleDragStart(e) {
    // Allow dragging to canvas
  }
}
```

**Visual Design:**
- Box: 120×80px, rounded corners, `var(--accent)` border when selected
- Icon: `mdi:<action>` from Material Design Icons
- Name: 12px text, DM Sans, truncated if too long
- Status indicator: small dot (top-right) — green (valid), red (error), yellow (warning)
- Connectors: small circles (top/bottom) for drag-to-connect

**Acceptance Criteria:**
- ✅ Step renders with icon and name
- ✅ Shows validation errors
- ✅ Drag-to-connect works
- ✅ Click to select/edit

##### Task 2.4: Property Editor (12 hours)
**File:** `custom_components/house_voice/frontend/house-voice-panel-chains-editor.js`

```javascript
class ChainPropertyEditor extends HTMLElement {
  // Right sidebar with detailed step properties
  
  constructor(step, hass) {
    super();
    this.step = step;
    this.hass = hass;
  }
  
  render() {
    // Dynamic form based on action type
    // Fields:
    // - Step name (text input)
    // - Step description (textarea)
    // - Action type (selector, read-only)
    // - Target entity (entity selector)
    // - Parameters (dynamic per action)
    // - Filter (condition)
    // - Route expression (Jinja2)
    // - Transform (key-value editor)
    // - Retry config (checkboxes)
    // - Circuit breaker (toggle + thresholds)
  }
  
  // Dynamic form generation based on action
  getFieldsForAction(actionType) {
    // Return field definitions for form generator
    // { name: "target", type: "entity", filter: { domain: "media_player" } }
    // { name: "message", type: "text", required: true }
    // { name: "volume", type: "number", min: 0.05, max: 1.0 }
  }
  
  // Save changes
  async saveStep() {
    // Validate form
    // Call websocket to update chain
    // Notify canvas of changes
  }
}
```

**Form Fields:**

| Action | Fields |
|--------|--------|
| `announce` | target (media_player), message (text, Jinja2 ok), volume (0.05-1.0) |
| `delay` | duration_ms (integer) |
| `condition_check` | entity_id, expected_state (text) |
| `call_service` | domain (select), service (select), data (JSON) |
| `set_state` | entity_id, state (text) |
| `notify` | service (select), message (text, Jinja2 ok), title (text) |

**Advanced Options** (all actions):
- Filter conditions (AND-logic)
- Route expression (Jinja2)
- Parameter transformation (key-value pairs)
- Retry settings (max_attempts, backoff)
- Circuit breaker settings (enable, threshold, timeout)

**Acceptance Criteria:**
- ✅ Dynamic form generation per action
- ✅ Jinja2 syntax highlighting in text fields
- ✅ Real-time validation as user types
- ✅ All 7 action types supported
- ✅ Save updates chain on backend

---

#### Week 3-4: Testing & Export

##### Task 2.5: Validation Panel (8 hours)
**File:** `custom_components/house_voice/frontend/house-voice-panel-chains-validation.js`

```javascript
class ChainValidationPanel extends HTMLElement {
  // Display validation errors/warnings real-time
  
  async validateChain(chain) {
    const result = await this.sendMessage({
      type: "house_voice/chain/validate",
      chain: chain
    });
    
    this.displayErrors(result.errors);    // Red badges
    this.displayWarnings(result.warnings); // Yellow badges
    this.displayInfo(result.info);        // Blue badges
  }
  
  displayErrors(errors) {
    // Red header: "4 Errors"
    // List:
    // - "Entity 'media_player.unknown' does not exist (step 3)"
    // - "Invalid Jinja2: condition }} missing opening {{" (step 5)"
    // Click error → highlight step on canvas
  }
  
  displayWarnings(warnings) {
    // Yellow header: "2 Warnings"
    // List potential issues (not blockers)
    // - "Step has no error handling"
    // - "Long expression may affect performance"
  }
  
  displayInfo(info) {
    // Blue header: "Info"
    // - "Chain is executable (no cycles)"
    // - "All entities exist"
  }
}
```

**Error Messages (user-friendly):**
- "Entity 'media_player.unknown' does not exist (step 3)"
- "Invalid Jinja2 in 'message' field (step 1): 'condition }} missing opening {{'"
- "Unknown action type 'invalid' (step 2)"
- "Circular dependency detected: step_1 → step_2 → step_1"

**Acceptance Criteria:**
- ✅ Real-time validation as user edits
- ✅ Errors prevent publish
- ✅ Warnings are informational
- ✅ Click error → scroll canvas to step
- ✅ <100ms validation time

##### Task 2.6: Test Executor (12 hours)
**File:** `custom_components/house_voice/frontend/house-voice-panel-chains-tester.js`

```javascript
class ChainTestExecutor extends HTMLElement {
  // Test execution UI
  
  async testChain(chain) {
    // Show mock event builder
    // Call backend: house_voice/chain/test
    // Display execution trace
  }
  
  async buildMockEvent() {
    // Form to create test event
    // Fields: room, sensor_type, value, priority, etc.
    // Return: event data object
  }
  
  async executeTest(chain, mockEvent) {
    const result = await this.sendMessage({
      type: "house_voice/chain/test",
      chain_id: chain.id,
      event: mockEvent
    });
    
    this.displayExecutionTrace(result);
  }
  
  displayExecutionTrace(result) {
    // Step-by-step output
    // For each step:
    // - Step name + action
    // - Duration (ms)
    // - Status (executed, skipped, failed)
    // - Result data (if any)
    // - Log messages
  }
}
```

**Mock Event Builder:**
```javascript
{
  room: "living_room",
  sensor: "motion",
  value: true,
  priority: "normal",
  timestamp: "2026-09-24T15:30:00Z"
}
```

**Execution Trace Output:**
```
Step 1: Check away mode (condition_check)
  Duration: 42ms
  Status: ✓ Executed
  Result: Condition matched

Step 2: Send alert (announce)
  Duration: 3200ms (TTS)
  Status: ✓ Executed
  Result: Spoken to media_player.living_room

Total: 3242ms
Status: ✓ Complete
```

**WebSocket Command (new):**
```python
async def websocket_chain_test(hass, connection, msg):
    """house_voice/chain/test"""
    # Execute chain with mock event
    # Capture execution trace
    # Return result with timing
    
    # Response:
    {
      "success": true,
      "steps": [
        {
          "id": "step_1",
          "name": "Check away mode",
          "action": "condition_check",
          "duration_ms": 42,
          "status": "executed",
          "result": {...}
        },
        ...
      ],
      "total_duration_ms": 3242,
      "final_status": "success"
    }
```

**Acceptance Criteria:**
- ✅ Mock event builder works
- ✅ Test execution returns trace
- ✅ Timing information accurate
- ✅ Result shows step-by-step execution
- ✅ <300ms test execution time (excluding TTS)

##### Task 2.7: Chain Management UI (10 hours)
**File:** `custom_components/house_voice/frontend/house-voice-panel-chains-list.js`

```javascript
class ChainsList extends HTMLElement {
  // List of all chains (active, drafts)
  
  async connectedCallback() {
    this.chains = await this.getChains();
    this.render();
  }
  
  async getChains(status = "all") {
    const result = await this.sendMessage({
      type: "house_voice/chain/list",
      status: status
    });
    return result.chains;
  }
  
  render() {
    // Two sections: Active | Drafts
    // For each chain:
    // - Name + description
    // - Step count
    // - Status badge (active, draft)
    // - Actions menu (Edit, Delete, Export, Duplicate)
    // - Create new button
  }
  
  async deleteChain(chainId) {
    // Confirm dialog
    // Call websocket delete
    // Reload list
  }
  
  async exportChain(chainId) {
    // Download as JSON
    // Filename: chain_name_2026-09-24.json
  }
  
  async duplicateChain(chainId) {
    // Create copy with "_copy" suffix
    // Status: draft
  }
}
```

**Chain List Card:**
```html
<div class="chain-card">
  <div class="chain-header">
    <div class="chain-name">Alert on motion</div>
    <div class="chain-status">
      <span class="badge badge-active">Active</span>
    </div>
  </div>
  <div class="chain-description">
    Send alert when motion detected while away
  </div>
  <div class="chain-meta">
    <span>5 steps</span>
    <span>Modified: today at 15:30</span>
  </div>
  <div class="chain-actions">
    <button @click="editChain">Edit</button>
    <button @click="testChain">Test</button>
    <button @click="exportChain">Export</button>
    <button @click="deleteChain">Delete</button>
  </div>
</div>
```

**Acceptance Criteria:**
- ✅ List shows all chains
- ✅ Filter by status (active/draft)
- ✅ Edit/Delete/Export/Duplicate work
- ✅ Create new chain button
- ✅ Performance: <500ms load for 100 chains

##### Task 2.8: Export/Import (8 hours)
**Files:** 
- `custom_components/house_voice/frontend/house-voice-panel-chains-export.js`
- Backend WebSocket commands

**Export:**
```javascript
async exportChain(chainId) {
  const chain = await this.getChain(chainId);
  
  // Format: JSON with metadata
  const export = {
    version: "1.0",
    exported_at: new Date().toISOString(),
    house_voice_version: "3.6.0",
    chain: chain
  };
  
  // Download as file
  const blob = new Blob([JSON.stringify(export, null, 2)]);
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${chain.name}_${new Date().toISOString().split('T')[0]}.json`;
  a.click();
}
```

**Import:**
```javascript
async importChain(file) {
  const text = await file.text();
  const data = JSON.parse(text);
  
  // Validate structure
  if (data.version !== "1.0") {
    throw new Error("Unknown export version");
  }
  
  // Validate chain
  const result = await this.sendMessage({
    type: "house_voice/chain/validate",
    chain: data.chain
  });
  
  if (result.errors.length > 0) {
    throw new Error(`Import validation failed: ${result.errors[0]}`);
  }
  
  // Create chain (status: draft by default)
  const created = await this.sendMessage({
    type: "house_voice/chain/create",
    chain: {
      ...data.chain,
      name: `${data.chain.name} (imported)`,
      status: "draft"
    }
  });
  
  return created.chain_id;
}
```

**WebSocket Commands (new):**
```python
async def websocket_chain_export(hass, connection, msg):
    """house_voice/chain/export"""
    # Return chain with metadata
    
async def websocket_chain_import(hass, connection, msg):
    """house_voice/chain/import"""
    # Validate and create chain
```

**Acceptance Criteria:**
- ✅ Export creates valid JSON
- ✅ Import validates structure before creating
- ✅ Imported chains start as drafts
- ✅ Can round-trip: export → import → export (no loss)
- ✅ File download works in all browsers

---

### PHASE 3: Integration & Polish (Week 5) — 20-30 hours

##### Task 3.1: Add Chains Tab to Panel (6 hours)
**File:** `custom_components/house_voice/frontend/house-voice-panel.js`

Modify existing panel:
```javascript
// Add "Chains" to tab bar
const tabs = ["Events", "Groups", "History", "Chains"];

// Route to ChainsTab component based on active tab
connectedCallback() {
  this._setupTabs();
  this._renderActiveTab();
}

_renderActiveTab() {
  if (this.activeTab === "Chains") {
    this._renderChainsTab();
  }
  // ... other tabs
}

_renderChainsTab() {
  // Mount ChainsList, ChainBuilder, etc.
}
```

**Acceptance Criteria:**
- ✅ Chains tab visible and clickable
- ✅ Tab switching smooth
- ✅ Chain editor loads in tab
- ✅ Navigation between chain list and editor works

##### Task 3.2: Keyboard Shortcuts (4 hours)
Implement common shortcuts:
- `Ctrl+S` — Save chain
- `Ctrl+Z` — Undo (revert to last saved)
- `Ctrl+D` — Duplicate step
- `Delete` — Delete selected step
- `Escape` — Deselect/close editors
- `Space+Drag` — Pan canvas
- `Ctrl+Scroll` — Zoom canvas

**Acceptance Criteria:**
- ✅ All 7 shortcuts work
- ✅ Shortcuts shown in help tooltips
- ✅ Don't conflict with browser shortcuts

##### Task 3.3: Tutorial & Help (6 hours)
Create interactive walkthrough:
1. Welcome screen
2. Drag action onto canvas
3. Edit step properties
4. Connect steps
5. Validate chain
6. Test with mock event
7. Publish chain

**Help Tooltips** on every UI element:
- Action palette: "Drag an action onto the canvas to add a step"
- Canvas: "Connect steps by dragging from output of one step to input of next"
- Property editor: "Jinja2 templates supported — use {{ entity_name }} to access values"
- Test button: "Execute chain against mock event data to verify behavior"

**Acceptance Criteria:**
- ✅ Tutorial guides through main workflow
- ✅ Tooltips on all major UI elements
- ✅ Help accessible from panel menu

##### Task 3.4: Style & Design Polish (8 hours)
Apply Indeklima Designer tokens:

```javascript
// Colors
const colors = {
  bg: "var(--bg)",           // Panel background
  bg2: "var(--bg2)",         // Card background
  accent: "#14b8a6",        // House Voice teal
  accent2: "#34d399",       // House Voice emerald
  text: "var(--text)",
  sub: "var(--sub)",
  div: "var(--div)"          // Borders
};

// Typography
const fonts = {
  body: "font-family: 'DM Sans', sans-serif; font-size: 14px;",
  title: "font-family: 'DM Sans', sans-serif; font-size: 16px; font-weight: 600;",
  mono: "font-family: 'DM Mono', monospace; font-size: 12px;"
};

// Spacing
const spacing = {
  xs: "4px",
  sm: "8px",
  md: "12px",
  lg: "16px",
  xl: "20px"
};

// Shadows
const shadows = {
  sm: "0 1px 2px rgba(0,0,0,0.05)",
  md: "0 4px 6px rgba(0,0,0,0.1)",
  lg: "0 10px 15px rgba(0,0,0,0.15)"
};

// Transitions
const transitions = {
  fast: "all 0.15s ease",
  base: "all 0.2s ease",
  slow: "all 0.3s ease"
};
```

**Responsive Design:**
```css
@media (max-width: 768px) {
  /* Mobile: canvas full width, property editor slides in from right */
  .builder-container { flex-direction: column; }
  .property-editor { position: absolute; right: 0; width: 100%; }
  
  /* Hide tab labels on mobile, show only icons */
  .tab-label { display: none; }
  .tab-icon { display: inline; }
}
```

**Acceptance Criteria:**
- ✅ Consistent color scheme (teal/emerald)
- ✅ Typography matches design tokens
- ✅ Spacing consistent
- ✅ Responsive on mobile (<768px)
- ✅ Smooth transitions between states

##### Task 3.5: Comprehensive Testing (10 hours)
**File:** `tests/components/house_voice/test_chain_builder_ui.py`

End-to-end tests:
1. Create new chain via UI
2. Add 5 steps via drag-drop
3. Edit step properties
4. Connect steps
5. Validate chain
6. Export chain
7. Import exported chain
8. Publish chain

**UI Component Tests:**
- Canvas renders correctly
- Drag-drop works
- Property editor validates input
- Validation panel shows errors
- Test executor returns trace

**Performance Tests:**
- 50-step chain renders <500ms
- Drag-drop response <100ms
- Validation completes <100ms

**Acceptance Criteria:**
- ✅ 20+ UI integration tests
- ✅ All tests pass
- ✅ Coverage >85% for UI code
- ✅ No browser console errors

---

## Testing Strategy

### Unit Tests (by task)
```
Task 1.1: Storage layer — 5 tests
Task 1.2: Validation engine — 10 tests
Task 1.3: WebSocket — 8 tests
Task 1.4: Serialization — 6 tests
Task 1.5: Entity resolver — 4 tests
Task 1.6: Cycle detection — 6 tests
Task 1.7: Integration — 15 tests

Task 2.1: Canvas — 8 tests
Task 2.2: Palette — 4 tests
Task 2.3: Step node — 6 tests
Task 2.4: Property editor — 8 tests
Task 2.5: Validation panel — 4 tests
Task 2.6: Test executor — 8 tests
Task 2.7: Chain list — 6 tests
Task 2.8: Export/Import — 6 tests

Task 3.1-3.5: Integration — 20 tests

TOTAL: 133 tests
```

### Test Execution
```bash
# Run all chain builder tests
pytest tests/components/house_voice/test_chain_builder*.py -v

# Run specific test file
pytest tests/components/house_voice/test_chain_builder_foundation.py::test_validate_chain -v

# Run with coverage
pytest tests/components/house_voice/ --cov=custom_components/house_voice/events/ --cov-report=html
```

---

## Success Criteria (Phase Completion)

### Functional
- ✅ Create chain via UI (drag-drop)
- ✅ Edit chain properties (name, description)
- ✅ Add/remove steps
- ✅ Connect steps visually
- ✅ Test execution with mock events
- ✅ Export chain as JSON
- ✅ Import chain from JSON
- ✅ Publish chain to active
- ✅ Delete chain

### Non-Functional
- ✅ All 133 tests pass
- ✅ Code coverage >90%
- ✅ No console errors
- ✅ Responsive design (mobile-friendly)
- ✅ Validation <100ms
- ✅ Canvas render <500ms for 50 steps
- ✅ Export/import handles all edge cases

### User Experience
- ✅ Tutorial guides new users
- ✅ Error messages are clear and actionable
- ✅ Keyboard shortcuts documented
- ✅ Tooltips on all major UI elements
- ✅ Smooth drag-drop feedback
- ✅ Visual indication of selected steps

---

## Git Commits

Expected commits (weekly):

**Week 1-2:**
```
commit: "feat(chain-builder): Add storage layer and validation engine (Phase 1)"
  - HouseVoiceChains storage class
  - ChainValidator with 6 validation rules
  - WebSocket CRUD commands
  - 40+ unit tests

commit: "feat(chain-builder): Implement DAG cycle detection and resolvers (Phase 1)"
  - ChainGraph with cycle detection
  - Entity and action resolvers
  - Integration tests
  - Full Phase 1 test coverage

commit: "test(chain-builder): Add comprehensive Phase 1 tests"
  - 30+ unit tests
  - Integration tests
  - Performance benchmarks
```

**Week 2-4:**
```
commit: "feat(chain-builder-ui): Build visual canvas and components (Phase 2)"
  - ChainBuilderCanvas (SVG rendering, drag-drop)
  - Action palette with drag support
  - StepNode component with status indicators
  - PropertyEditor with dynamic forms
  - 30+ UI component tests

commit: "feat(chain-builder-ui): Add validation, testing, and management UI (Phase 2)"
  - ValidationPanel with real-time error display
  - ChainTestExecutor with mock event builder
  - ChainsList with CRUD actions
  - Export/Import functionality
  - 30+ UI integration tests

commit: "style(chain-builder): Apply design tokens and responsive layout (Phase 3)"
  - Indeklima Designer color scheme
  - Typography and spacing consistent
  - Mobile-responsive design
  - Keyboard shortcuts
  - Tutorial and help system

commit: "test(chain-builder): Final UI testing and polish (Phase 3)"
  - 20+ end-to-end UI tests
  - Performance benchmarks
  - Browser compatibility testing
  - Full regression test suite
```

---

## Version Management

Update these files with each commit:

1. `manifest.json` — version: "3.6.0"
2. `const.py` — VERSION = "3.6.0" and `# VERSION 3.6.0`
3. `CHANGELOG.md` — new entry with date and features
4. `STATUS.md` — update with current progress

---

## Dependencies & Blockers

### No Blockers
- All foundation complete (Sprint 5)
- No external dependencies needed
- No breaking changes to existing APIs

### Optional Enhancements (Future)
- Undo/redo history (currently just revert to last save)
- Collaborative editing (multiple users editing same chain)
- Chain versioning (track history of changes)
- Custom action plugins (extend with user-defined actions)

---

## Rollout Plan

**Phase Completion:** 3-4 weeks (dependent on scope verification)

**Release:**
1. ✅ Complete all tasks
2. ✅ All 133 tests pass
3. ✅ Documentation complete
4. ✅ Tag v3.6.0
5. ✅ Update README with new Chain Builder tab

**Post-Release:**
- Monitor for UI bugs
- Gather user feedback
- Plan optimizations for Phase 2

---

**Document Version:** 1.0  
**Last Updated:** 2026-09-24  
**Owner:** Claude  
**Status:** Ready for Implementation
