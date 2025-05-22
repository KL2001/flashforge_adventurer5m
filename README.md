# FlashForge Adventurer 5M Pro Integration

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
   ```

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

- Add the following to your `configuration.yaml`:

```yaml
flashforge_adventurer5m:
  host: YOUR_PRINTER_IP
  serial_number: YOUR_PRINTER_SERIAL_NUMBER #including the prefix "SN"
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
Test the stream URL using a web browser:

- Enter the stream URL, for example: `http://192.168.1.50:8080/?action=stream`

**Home Assistant Logs:**

- Check Settings > System > Logs for any related error messages.
- Ensure that the integration is fetching data correctly without errors.

## Development and Testing

### Important Note

This integration's test suite is designed for local development only and requires access to a physical Flashforge Adventurer 5M printer. To protect printer credentials and ensure safe testing practices, all test files are excluded from the git repository.

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
