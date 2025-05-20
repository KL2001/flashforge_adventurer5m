import asyncio
import json
import logging
from coordinator import FlashforgeDataUpdateCoordinator

# Load test config
with open("test_config.json") as f:
    config = json.load(f)

async def main():
    # Minimal Home Assistant mock for testing only.
    class DummyHass:
        def __init__(self):
            self.loop = asyncio.get_event_loop()
    
    hass = DummyHass()
    coordinator = FlashforgeDataUpdateCoordinator(
        hass,
        host=config["host"],
        serial_number=config["serial_number"],
        check_code=config["check_code"],
        scan_interval=10,
    )
    print("Fetching printer data...")
    data = await coordinator._fetch_data()
    print("Data fetched:")
    print(json.dumps(data, indent=2))
    
    # Test a command (pause_print)
    print("Sending pause_print command...")
    result = await coordinator.pause_print()
    print(f"pause_print result: {result}")

    # Test toggle_light (on)
    print("Sending toggle_light command (on)...")
    result = await coordinator.toggle_light(True)
    print(f"toggle_light (on) result: {result}")

    # Test toggle_light (off)
    print("Sending toggle_light command (off)...")
    result = await coordinator.toggle_light(False)
    print(f"toggle_light (off) result: {result}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())
