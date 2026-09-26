/**
 * House Voice Panel — Tooltips & Help Text Enhancement
 * Version: 3.13.0
 * Description: Dynamic tooltip enhancement for panel UI elements
 *
 * This module adds helpful tooltips to all major UI elements in the House Voice panel.
 * Tooltips appear on hover and help users understand what each setting does.
 */

const HOUSE_VOICE_TOOLTIPS = {
  // Events Tab
  eventId: "Unikt ID for dette event. Bruges når du kalder house_voice.say fra automationer. Kan ikke ændres efter oprettelse.",
  message: "Teksten som skal læses op. Understøtter Jinja2-skabeloner: {{ entity.attribute }}",
  conditions: "Betingelser der skal være opfyldt før eventet afspilles. Lad tomt for altid at afspille. Alle valgte betingelser skal være sande (AND-logik).",
  priority: "Prioritetsniveau påvirker kørækkefølgen. 'Critical' spiller altid øjeblikkeligt.",
  volume: "Afspilningsvolumen fra 5% til 100%. Standardværdien er 35%.",
  speakers: "Vælg hvilke højtalere/grupper dette event skal afspille på. Mindst én speaker er påkrævet.",
  
  // Groups Tab
  groupId: "Unikt ID for denne gruppe. Bruges som 'group:grupnavn' i events.",
  groupName: "Brugervenlig navn for denne gruppe. Vises i panelet.",
  groupSpeakers: "Vælg alle højtalere som skal være i denne gruppe.",
  
  // Conditions Tab
  conditionId: "Unikt ID for denne betingelse. Bruges i event-konfiguration.",
  conditionLabel: "Brugervenlig navn som forklarer hvad betingelsen betyder.",
  conditionEntity: "Home Assistant entity ID der skal overvåges (fx binary_sensor.nogen_hjemme).",
  conditionState: "Den tilstand som entity skal have for at betingelsen er opfyldt (fx 'on', 'off', 'true').",
  
  // History Tab
  searchHistory: "Søg i alle TTS-afspilninger efter event ID eller besked.",
  filterChain: "Filtrer efter hvilken automation/kæde der udløste afspilningen.",
  filterStatus: "Vis kun afspilninger med denne status (afsluttet, fejlet, blokeret, etc).",
  filterDate: "Vælg dato-interval for de afspilninger du vil se.",
  exportExecution: "Download fuld detaljer om denne afspilning som JSON.",
  
  // Analytics Tab
  analyticsDateRange: "Vælg periode for analytik-data (første til sidste dato).",
  analyticsChainFilter: "Filtrer analytics efter en bestemt automation/kæde.",
  successRate: "Procentdel af afspilninger der lykkedes uden fejl eller blokering.",
  avgDuration: "Gennemsnitlig varighed af afspilninger i denne periode.",
  
  // Settings & Options
  quietHoursStart: "Tidspunkt hvor stilletimerne begynder (fx 22:00 for 10 PM).",
  quietHoursEnd: "Tidspunkt hvor stilletimerne slutter (fx 07:00 for 7 AM).",
  quietHoursEnabled: "Slå stilletimerne til/fra. Under stilletimerne blokeres normale og info-events.",
  
  // Main Buttons
  testEvent: "Afspil dette event med nuværende indstillinger. Ignorer spam-filter og stilletimer.",
  editEvent: "Rediger dette events indstillinger.",
  deleteEvent: "Slet dette event permanent. Kan ikke fortrydes.",
  refreshData: "Genindlæs alle data fra serveren.",
  reloadPanel: "Fuld genindlæsning af panelet. Nyttig hvis noget virker uordentligt.",
  addEvent: "Opret et nyt event der kan bruges i automationer.",
  addGroup: "Opret en ny gruppe af højtalere.",
  addCondition: "Opret en ny betingelse der kan bruges i events.",
  saveForm: "Gem ændringer og luk formularen.",
  cancelForm: "Luk formularen uden at gemme ændringer.",
};

/**
 * Apply tooltips to panel UI elements
 */
function applyHouseVoiceTooltips(rootElement) {
  if (!rootElement) return;

  // Event form tooltips
  addTooltipToLabel(rootElement, "Event ID", HOUSE_VOICE_TOOLTIPS.eventId);
  addTooltipToLabel(rootElement, "Besked", HOUSE_VOICE_TOOLTIPS.message);
  addTooltipToLabel(rootElement, "Betingelser", HOUSE_VOICE_TOOLTIPS.conditions);
  addTooltipToLabel(rootElement, "Prioritet", HOUSE_VOICE_TOOLTIPS.priority);
  addTooltipToLabel(rootElement, "Volumen", HOUSE_VOICE_TOOLTIPS.volume);
  addTooltipToLabel(rootElement, "Højttalere / Grupper", HOUSE_VOICE_TOOLTIPS.speakers);

  // Group form tooltips
  addTooltipToLabel(rootElement, "Gruppe ID", HOUSE_VOICE_TOOLTIPS.groupId);
  addTooltipToLabel(rootElement, "Navn", HOUSE_VOICE_TOOLTIPS.groupName);

  // Condition form tooltips
  addTooltipToLabel(rootElement, "Betingelse ID", HOUSE_VOICE_TOOLTIPS.conditionId);
  addTooltipToLabel(rootElement, "Entity ID", HOUSE_VOICE_TOOLTIPS.conditionEntity);
  addTooltipToLabel(rootElement, "Forventet tilstand", HOUSE_VOICE_TOOLTIPS.conditionState);

  // History filter tooltips
  const searchInput = rootElement.querySelector('.search-input');
  if (searchInput) searchInput.title = HOUSE_VOICE_TOOLTIPS.searchHistory;

  // Buttons
  addTooltipToClass(rootElement, 'btn-test', HOUSE_VOICE_TOOLTIPS.testEvent);
  addTooltipToClass(rootElement, 'btn-edit', HOUSE_VOICE_TOOLTIPS.editEvent);
  addTooltipToClass(rootElement, 'btn-delete', HOUSE_VOICE_TOOLTIPS.deleteEvent);
  addTooltipToClass(rootElement, 'btn-refresh', HOUSE_VOICE_TOOLTIPS.refreshData);
  addTooltipToClass(rootElement, 'btn-reload', HOUSE_VOICE_TOOLTIPS.reloadPanel);
  addTooltipToClass(rootElement, 'btn-add', HOUSE_VOICE_TOOLTIPS.addEvent);
  addTooltipToClass(rootElement, 'btn-save', HOUSE_VOICE_TOOLTIPS.saveForm);
  addTooltipToClass(rootElement, 'btn-cancel', HOUSE_VOICE_TOOLTIPS.cancelForm);
}

/**
 * Add tooltip to a label containing specific text
 */
function addTooltipToLabel(root, labelText, tooltip) {
  const labels = root.querySelectorAll('.field-label');
  for (const label of labels) {
    if (label.textContent.includes(labelText) && !label.title) {
      label.title = tooltip;
      // Also add to the input field
      const input = label.closest('.field')?.querySelector('input, select, textarea');
      if (input && !input.title) {
        input.title = tooltip;
      }
    }
  }
}

/**
 * Add tooltip to all elements with a class
 */
function addTooltipToClass(root, className, tooltip) {
  const elements = root.querySelectorAll(`.${className}`);
  for (const el of elements) {
    if (!el.title) {
      el.title = tooltip;
    }
  }
}
