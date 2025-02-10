# FlashForge Adventurer 5M Integration

This project integrates the **FlashForge Adventurer 5M** 3D printer in LAN mode with Home Assistant.

## Features

- **Monitor Printer Status**
  - View real-time status of the printer.
  - Track print progress and details.

- **View Camera Feed**
  - Access live camera feed from the printer's webcam.

## Planned Features

- **Print Notifications**
  - Receive alerts on print completion.

- **Print Control**
  - Start, pause, and stop prints directly from Home Assistant.

## Requirements

- **Home Assistant** 2023.10 or later
- **FlashForge Adventurer 5M 3D Printer**
- **Network Connection** to the printer

## Installation

1. **Clone the Repository**

   Clone this repository to your Home Assistant `config/custom_components` directory:

   ```bash
   git clone https://github.com/xombie21/flashforge_adventurer5m.git

2. **Configure Integration**

   You can add the integration via the Home Assistant UI or manually via `configuration.yaml`.

   a. **Using Home Assistant UI**
      - Navigate to `Settings` > `Devices & Services` > `Add Integration`.
      - Search for `FlashForge Adventurer 5M PRO`.
      - Enter the required details:
        - **Host**: IP address or hostname of your printer (e.g., 192.168.1.50).
        - **Serial Number**: Serial number of your printer.
        - **Check Code**: Authentication code for your printer.
b. **Manual Configuration**
      Add the following to your `configuration.yaml`:
      
  ```yaml
  flashforge_adventurer5m:
    host: YOUR_PRINTER_IP
    serial_number: YOUR_PRINTER_SERIAL_NUMBER
    check_code: YOUR_PRINTER_CHECK_CODE
  ```
      
      Replace `YOUR_PRINTER_IP`, `YOUR_PRINTER_SERIAL_NUMBER`, and `YOUR_PRINTER_CHECK_CODE` with the actual values for your printer.

3. **Restart Home Assistant**

   Restart Home Assistant to apply the changes.

## Usage

After installation, the FlashForge Adventurer 5M PRO integration will appear in the Home Assistant UI. You can manage your 3D printer through the available entities, including sensors and camera feed.

- Monitor Status: Check the printer's current status, temperature readings, and more.
- Camera Feed: View a live stream from the printer's webcam directly within Home Assistant.

## Troubleshooting

If you encounter issues with the camera feed, such as:

`Error getting new camera image from 3D Printer: Server disconnected without sending a response.`

Ensure that:

**Stream URL Configuration:**
  - The cameraStreamUrl provided by the printer is correct.
  - If cameraStreamUrl is not available, the fallback URL (http://YOUR_PRINTER_IP:8080/?action=stream) is accessible.

**Network Configuration:**
- Home Assistant and the printer are on the same network segment.
- Necessary ports (e.g., 8080) are open and not blocked by firewalls.

**Stream Accessibility:**

Test the stream URL using a web browser.
## Enter the stream URL, for example:
[http://192.168.1.50:8080/?action=stream](http://192.168.1.50:8080/?action=stream)

**Home Assistant Logs:**
- Check Settings > System > Logs for any related error messages.
- Ensure that the integration is fetching data correctly without errors.

## Contributing

Contributions are welcome! Please fork this repository and submit a pull request with your improvements.

License
This project is licensed under the MIT License. See the LICENSE file for details.