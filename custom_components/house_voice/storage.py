# VERSION = "2.0.0"
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