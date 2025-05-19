# FlashForge Adventurer 5M Pro Integration

This project integrates the **FlashForge Adventurer 5M** 3D printer in LAN mode with Home Assistant.

## Features

- **Monitor Printer Status**: View real-time status of the printer, track print progress and details.
- **View Camera Feed**: Access live camera feed from the printer's webcam.
- **Print Control**: Start, pause, and stop prints directly from Home Assistant.

## Planned Features

- **Print Notifications**: Receive alerts on print completion.

## Requirements

- **Home Assistant** 2023.10 or later
- **FlashForge Adventurer 5M 3D Printer**
- **Network Connection** to the printer

## Installation

1. **Clone the Repository**

   Clone this repository to your Home Assistant `config/custom_components` directory:

   ```bash
   git clone https://github.com/xombie21/flashforge_adventurer5m.git
   ```

2. **Add Integration via Home Assistant UI**

   - Go to `Settings` > `Devices & Services` > `Add Integration`.
   - Search for `FlashForge Adventurer 5M PRO`.
   - Enter the required details:
     - **Host**: IP address or hostname of your printer (e.g., 192.168.1.50).
     - **Serial Number**: Serial number of your printer.
     - **Check Code**: Authentication code for your printer.

3. **Restart Home Assistant**

   Restart Home Assistant to apply the changes.

## Usage

After installation, the FlashForge Adventurer 5M PRO integration will appear in the Home Assistant UI. You can manage your 3D printer through the available entities, including sensors and camera feed.

- **Monitor Status**: Check the printer's current status, temperature readings, and more.
- **Camera Feed**: View a live stream from the printer's webcam directly within Home Assistant.

## Services

The following services are available for use in automations or scripts:

- `flashforge_adventurer5m.pause_print`: Pause the current print job.
- `flashforge_adventurer5m.start_print`: Start a new print job. Requires `file_path` (string) as a parameter.
- `flashforge_adventurer5m.cancel_print`: Cancel the current print job.
- `flashforge_adventurer5m.toggle_light`: Toggle the printer's light. Requires `state` (boolean) as a parameter.

## Troubleshooting

If you encounter issues with the camera feed, such as:

```
Error getting new camera image from 3D Printer: Server disconnected without sending a response.
```

Ensure that:

- The `cameraStreamUrl` provided by the printer is correct.
- If `cameraStreamUrl` is not available, the fallback URL (`http://YOUR_PRINTER_IP:8080/?action=stream`) is accessible.
- Home Assistant and the printer are on the same network segment.
- Necessary ports (e.g., 8080) are open and not blocked by firewalls.
- Test the stream URL using a web browser (e.g., `http://192.168.1.50:8080/?action=stream`).
- Check Home Assistant logs (`Settings > System > Logs`) for any related error messages.

## Contributing

Contributions are welcome! Please fork this repository and submit a pull request with your improvements.

## License

This project is licensed under the MIT License. See the LICENSE file for details.