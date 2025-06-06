# FlashForge Adventurer 5M Pro Integration

This project integrates the **FlashForge Adventurer 5M** 3D printer in LAN mode with Home Assistant.

## Features

- **Monitor Printer Status (via HTTP API on port 8898):**
  - View real-time operational status (e.g., Idle, Printing, Paused).
  - Track print progress, layer information, and time estimates.
  - Monitor extruder and bed temperatures (current and target).
  - View firmware version, IP/MAC address, and other diagnostic details.
  - Get current X, Y, Z nozzle positions (in mm).
  - List printable files available on the printer (via the "Printable Files Count" sensor's attributes).
  - Binary sensor states for: Connection, Error, Door Open, Light On (actual light), Auto Shutdown Enabled, External Fan Active, Internal Fan Active.
- **View Camera Feed**
  - Access live camera feed from the printer's webcam.
- **Control Printer Operations (primarily via TCP M-codes on port 8899):**
  - Start new print jobs by specifying the file path on the printer (`start_print`).
  - Pause active print jobs (`pause_print`).
  - Resume paused print jobs (`resume_print`).
  - Cancel ongoing print jobs (`cancel_print`).
  - Toggle the printer's built-in LED light (`toggle_light`).
  - Set target temperatures for the extruder and heated bed (`set_extruder_temperature`, `set_bed_temperature`).
  - Control the part cooling fan speed, including turning it off (`set_fan_speed`, `turn_fan_off`).
  - Move individual axes for jogging/manual positioning (`move_axis`).

## Planned Features

- **Print Notifications**
  - Receive alerts on print completion.

## Requirements

- **Home Assistant** 2023.10 or later
- **FlashForge Adventurer 5M Pro 3D Printer**
- **Network Connection** to the printer
- Ensure Home Assistant can reach the printer on TCP port 8898 (for status/sensor data) and TCP port 8899 (for control commands). The camera stream uses port 8080 or a URL provided by the printer.

## Installation

1. **Clone the Repository**

   Clone this repository to your Home Assistant `config/custom_components` directory:

   ```bash
   git clone https://github.com/xombie21/flashforge_adventurer5m.git
   ```

2. **Configure Integration**

   This integration is configured via the Home Assistant UI after installation.

   a. **Using Home Assistant UI**
      - Navigate to `Settings` > `Devices & Services` > `Add Integration`.
      - Search for `FlashForge Adventurer 5M Pro`.
      - Enter the required details:
        - **Host**: IP address or hostname of your printer (e.g., 192.168.1.50).
        - **Serial Number**: Serial number of your printer (often includes an 'SN' prefix, which should be included if displayed by your printer).
        - **Check Code**: Authentication code for your printer.

3. **Restart Home Assistant**

   Restart Home Assistant to apply the changes.

## Usage

After installation, the FlashForge Adventurer 5M Pro integration will appear in the Home Assistant UI. You can manage your 3D printer through the available entities, including sensors and camera feed.

- **Monitor Status:** Check the printer's current status, temperature readings, and more.
- **Camera Feed:** View a live stream from the printer's webcam directly within Home Assistant.

### Printer Controls

You can control your Flashforge Adventurer 5M Pro using various services provided by this integration. Call these services from your automations or the Developer Tools > Services UI. Most control commands are sent via TCP to port 8899, while status is polled via HTTP on port 8898.

**Light Control:**
*   `flashforge_adventurer5m.toggle_light`
    *   Toggles the printer's chamber light.
    *   **Parameters:**
        *   `state` (boolean, required): `true` to turn on, `false` to turn off.
    *   **Example:**
      ```yaml
      service: flashforge_adventurer5m.toggle_light
      data:
        state: true
      ```

**Print Job Management:**
*   `flashforge_adventurer5m.start_print`
    *   Starts printing a specified file from the printer's storage. The path should match those reported by the "Printable Files Count" sensor's attributes (e.g., `/data/yourfile.gcode`).
    *   **Parameters:**
        *   `file_path` (string, required): Path to the G-code file on the printer (e.g., `/data/yourfile.gcode`).
    *   **Example:**
      ```yaml
      service: flashforge_adventurer5m.start_print
      data:
        file_path: "/data/test_model.gcode" # Note: M23 prepends "0:/user" or "0:"
      ```
*   `flashforge_adventurer5m.pause_print`
    *   Pauses the current print job.
    *   No parameters.
*   `flashforge_adventurer5m.resume_print`
    *   Resumes a paused print job.
    *   No parameters.
*   `flashforge_adventurer5m.cancel_print`
    *   Cancels the ongoing print job.
    *   No parameters.

**Temperature Control:**
*   `flashforge_adventurer5m.set_extruder_temperature`
    *   Sets the target temperature for the extruder.
    *   **Parameters:**
        *   `temperature` (integer, required): Target temperature in Celsius.
    *   **Example:**
      ```yaml
      service: flashforge_adventurer5m.set_extruder_temperature
      data:
        temperature: 215
      ```
*   `flashforge_adventurer5m.set_bed_temperature`
    *   Sets the target temperature for the heated bed.
    *   **Parameters:**
        *   `temperature` (integer, required): Target temperature in Celsius.
    *   **Example:**
      ```yaml
      service: flashforge_adventurer5m.set_bed_temperature
      data:
        temperature: 60
      ```

**Fan Control:**
*   `flashforge_adventurer5m.set_fan_speed`
    *   Sets the speed of the part cooling fan.
    *   **Parameters:**
        *   `speed` (integer, required): Fan speed from 0 (off) to 255 (full speed).
    *   **Example:**
      ```yaml
      service: flashforge_adventurer5m.set_fan_speed
      data:
        speed: 128 # Set fan to 50%
      ```
*   `flashforge_adventurer5m.turn_fan_off`
    *   Turns the part cooling fan off.
    *   No parameters.

**Axis Movement (Jogging):**
*   `flashforge_adventurer5m.move_axis`
    *   Moves one or more axes to specified absolute coordinates. Use with caution.
    *   **Parameters (all optional, but at least one axis must be provided):**
        *   `x` (float, optional): Target X-axis coordinate in mm.
        *   `y` (float, optional): Target Y-axis coordinate in mm.
        *   `z` (float, optional): Target Z-axis coordinate in mm.
        *   `feedrate` (integer, optional): Speed of movement in mm/minute.
    *   **Example (move X and Y):**
      ```yaml
      service: flashforge_adventurer5m.move_axis
      data:
        x: 100
        y: 50
        feedrate: 1500
      ```

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
Test the stream URL using a web browser:

- Enter the stream URL, for example: `http://192.168.1.50:8080/?action=stream`

**Home Assistant Logs:**

- Check Settings > System > Logs for any related error messages.
- Ensure that the integration is fetching data correctly without errors.

**Control Command Issues:**
If services like toggling the light, pausing/resuming prints, setting temperatures, etc., are not working:
- Verify that your printer's IP address is correctly configured in the integration.
- Ensure your firewall allows Home Assistant to make outgoing TCP connections to your printer on port 8899 (for M-code commands) in addition to port 8898 (for status).
- Check the Home Assistant logs for any error messages from the `flashforge_adventurer5m` integration when you call a service.

## Development and Testing

### Important Note

This integration's test suite is designed for local development only and requires access to a physical FlashForge Adventurer 5M Pro printer. To protect printer credentials and ensure safe testing practices, all test files are excluded from the git repository.
Note: This integration communicates with the printer using two main network ports: TCP port 8898 for the HTTP API (status, sensor data) and TCP port 8899 for the M-code command interface (printer controls).

### Local Development Setup

1. **Clone and Setup**

   ```bash
   git clone https://github.com/yourusername/flashforge_adventurer5m
   cd flashforge_adventurer5m
   python scripts/setup_test_env.py --printer-ip YOUR_PRINTER_IP --serial YOUR_SERIAL --code YOUR_CODE
   ```

2. **Install Dependencies**

   ```bash
   pip install -r requirements_test.txt
   ```

3. **Test Documentation**

   ```bash
   cat tests/README.md  # Review testing guidelines
   ```

### Test Data and Security

The test suite uses mock data to protect sensitive information:

- Test data files are git-ignored by default
- Credentials are stored in local configuration only
- Mock data generators are provided for test cases

**Never include in repository:**

- Real printer credentials
- Captured printer responses
- Network configuration details
- Personal test data

### Running Tests

1. **Quick Tests**

   ```bash
   python scripts/run_test_suite.py --config quick
   ```

2. **Generate Mock Data**

   ```bash
   python scripts/generate_test_data.py
   ```

3. **Full Test Suite**

   ```bash
   python scripts/run_test_suite.py --config full
   ```

### Testing Guidelines

1. **Use Mock Data**
   - Generate mock data using provided scripts
   - Never use real printer data in tests
   - Follow data structure guidelines

2. **Local Testing Only**
   - Use development printer only
   - Run in safe environment
   - Monitor printer state

3. **Security First**
   - Keep credentials private
   - Use example data in documentation
   - Follow secure development practices

For detailed testing instructions, see [Local Testing Guide](tests/README.md).

### Testing Disclaimer

The test suite is provided for development purposes only:

- Always test with a development printer
- Never test against production printers
- Use caution when running tests that modify printer state
- Be aware that some tests may affect printer operation

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Follow security guidelines
4. Submit a pull request

## License

This project is licensed under the MIT License. See the LICENSE file for details.
