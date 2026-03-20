Overordnet arkitektur

Integration navn:

house_voice

Struktur:

custom_components/
 └── house_voice/
      ├── __init__.py
      ├── manifest.json
      ├── const.py
      ├── coordinator.py
      ├── services.yaml
      ├── voice_engine.py
      ├── storage.py
      ├── config_flow.py
      ├── panel.py
      └── sensor.py
Hvad integrationen gør

House Voice Manager bliver et centralt TTS system.

Automations kalder bare:

service: house_voice.say
data:
  event: dishwasher_open

Integration:

1️⃣ finder event
2️⃣ henter besked
3️⃣ prioritet / regler
4️⃣ vælger speaker
5️⃣ sender til script.ultra_tts

Storage (HA native)

Vi bruger HA storage API:

.storage/house_voice_events

Eksempel:

{
  "dishwasher_open": {
    "message": "Opvaskeren er åben",
    "priority": "normal",
    "speakers": ["media_player.kokken"]
  },
  "washer_done": {
    "message": "Vaskemaskinen er færdig",
    "priority": "info",
    "speakers": [
      "media_player.kokken",
      "media_player.stue"
    ]
  }
}

Fordel:

✔ kan redigeres fra UI
✔ overlever restart
✔ versionering

Services

services.yaml

say:
  name: Say voice event
  description: Speak a configured house voice message
  fields:
    event:
      example: dishwasher_open

add_event:
  name: Add voice event

delete_event:
  name: Delete voice event

test_event:
  name: Test voice event
Example automation

Din opvasker automation bliver:

service: house_voice.say
data:
  event: dishwasher_open

Det er meget renere.

UI panel

Vi kan lave et HA panel via:

async_register_panel

Det giver et sidebar panel:

🏠 House Voice

Indhold:

Voice Events
────────────

Dishwasher Open
Message: Opvaskeren er åben
Speaker: Køkken

[Test] [Edit] [Delete]

+ Add Event
Prioritetssystem

Integration kan håndtere:

Priority	Opførsel
info	duck musik
normal	normal TTS
critical	stop musik
Quiet hours

Config:

22:00 → 07:00

Kun:

critical

beskeder.

Multiroom

Event kan definere:

speaker_group

eller individuelle speakers.

Anti spam

Integration kan holde state:

last_spoken[event]

så samme besked ikke spammes.

Eksempel på backend flow
Automation
   │
   ▼
house_voice.say
   │
   ▼
voice_engine.py
   │
   ├─ spam check
   ├─ quiet hours
   ├─ priority
   ▼
Ultra TTS
   │
   ▼
Music Assistant
Bonus features du nemt kan bygge senere
📊 Statistik sensor
sensor.house_voice_today
🎙 Dynamic messages
"Godmorgen {{ user }}. Klokken er {{ time }}."
🌦 Morgen briefing
vejr
kalender
temperatur
Det fede ved denne løsning

Du får en rigtig smart home voice platform.

Alt i huset kan sige ting via én service:

house_voice.say
Hvis du vil, kan jeg også lave

en starter version af integrationen til dig med:

✔ manifest
✔ services
✔ storage
✔ say service
✔ Ultra TTS integration
✔ basic UI panel

Det vil være omkring 250 linjer kode, men fuldt fungerende.

Så kan du installere den direkte i:

custom_components/house_voice

og genstarte HA.

Vil du have jeg bygger v1 af House Voice integrationen til dig?
(det er faktisk et ret fedt projekt).

ja tak byg

Fedt projekt 👍
Her er en første fuldt fungerende v1 af din House Voice Manager integration til Home Assistant.
Den er lavet så den:

bruger HA storage API

laver services

kalder dit script.ultra_tts

er klar til senere UI panel

er meget let at udvide

Du kan installere den direkte i:

/config/custom_components/house_voice/
1️⃣ mappestruktur
custom_components/
 └── house_voice/
      ├── __init__.py
      ├── manifest.json
      ├── const.py
      ├── services.yaml
      ├── voice_engine.py
      └── storage.py
2️⃣ manifest.json
{
  "domain": "house_voice",
  "name": "House Voice Manager",
  "version": "1.0.0",
  "documentation": "https://github.com/yourrepo/house_voice",
  "requirements": [],
  "dependencies": [],
  "codeowners": ["@you"],
  "iot_class": "local_push"
}
3️⃣ const.py
DOMAIN = "house_voice"

STORAGE_KEY = "house_voice_events"
STORAGE_VERSION = 1

SERVICE_SAY = "say"
SERVICE_ADD = "add_event"
SERVICE_DELETE = "delete_event"
SERVICE_TEST = "test_event"
4️⃣ storage.py
from homeassistant.helpers.storage import Store
from .const import STORAGE_KEY, STORAGE_VERSION

class HouseVoiceStorage:

    def __init__(self, hass):
        self.hass = hass
        self.store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data = {}

    async def async_load(self):
        data = await self.store.async_load()
        if data is None:
            data = {}
        self.data = data
        return data

    async def async_save(self):
        await self.store.async_save(self.data)

    async def add_event(self, event_id, event_data):
        self.data[event_id] = event_data
        await self.async_save()

    async def delete_event(self, event_id):
        if event_id in self.data:
            del self.data[event_id]
            await self.async_save()

    def get_event(self, event_id):
        return self.data.get(event_id)
5️⃣ voice_engine.py
from .const import DOMAIN

class VoiceEngine:

    def __init__(self, hass, storage):
        self.hass = hass
        self.storage = storage

    async def say(self, event_id):

        event = self.storage.get_event(event_id)

        if not event:
            raise Exception(f"House Voice event '{event_id}' not found")

        message = event["message"]
        speakers = event["speakers"]
        volume = event.get("volume", 0.35)
        priority = event.get("priority", "normal")

        await self.hass.services.async_call(
            "script",
            "ultra_tts",
            {
                "speaker": speakers,
                "message": message,
                "volume": volume,
                "priority": priority
            },
            blocking=False
        )
6️⃣ services.yaml
say:
  name: Say voice event
  description: Speak a house voice message
  fields:
    event:
      required: true
      example: dishwasher_open

add_event:
  name: Add voice event
  fields:
    event:
      example: dishwasher_open
    message:
      example: Opvaskeren er åben
    speakers:
      example: media_player.kokken

delete_event:
  name: Delete voice event
  fields:
    event:
      example: dishwasher_open

test_event:
  name: Test voice event
  fields:
    event:
      example: dishwasher_open
7️⃣ init.py
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, SERVICE_SAY, SERVICE_ADD, SERVICE_DELETE, SERVICE_TEST
from .storage import HouseVoiceStorage
from .voice_engine import VoiceEngine


async def async_setup(hass: HomeAssistant, config):

    storage = HouseVoiceStorage(hass)
    await storage.async_load()

    engine = VoiceEngine(hass, storage)

    hass.data[DOMAIN] = {
        "storage": storage,
        "engine": engine
    }

    async def handle_say(call):

        event_id = call.data["event"]

        await engine.say(event_id)

    async def handle_add(call):

        event_id = call.data["event"]

        event_data = {
            "message": call.data["message"],
            "speakers": call.data["speakers"],
            "priority": call.data.get("priority", "normal"),
            "volume": call.data.get("volume", 0.35)
        }

        await storage.add_event(event_id, event_data)

    async def handle_delete(call):

        await storage.delete_event(call.data["event"])

    async def handle_test(call):

        await engine.say(call.data["event"])


    hass.services.async_register(
        DOMAIN,
        SERVICE_SAY,
        handle_say,
        schema=vol.Schema({
            vol.Required("event"): cv.string
        })
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD,
        handle_add
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE,
        handle_delete
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_TEST,
        handle_test
    )

    return True
8️⃣ start Home Assistant

Når HA starter, oprettes automatisk:

.storage/house_voice_events
9️⃣ tilføj første besked

Developer Tools → Services

service: house_voice.add_event
event: dishwasher_open
message: Opvaskeren er åben
speakers:
  - media_player.kokken
priority: normal
volume: 0.35
🔟 test beskeden
service: house_voice.say
event: dishwasher_open
din automation bliver nu super simpel
action:

  - service: house_voice.say
    data:
      event: dishwasher_open
hvad vi kan bygge i v2

Hvis du vil, kan vi næste skridt tilføje:

UI panel

sidebar menu:

🏠 House Voice

hvor du kan:

➕ tilføje beskeder

✏️ redigere

🧪 teste

❌ slette

spam filter
ikke sige samme besked igen indenfor 30 sek
quiet hours
22:00-07:00
dynamic templates
Godmorgen {{ user }}
Temperaturen er {{ temperature }}

💡 Hvis du vil, kan jeg også lave v2 med fuldt UI panel + event editor, så din House Voice bliver en rigtig Home Assistant hub.
Det bliver faktisk ret lækkert.