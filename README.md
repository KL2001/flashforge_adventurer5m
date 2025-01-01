# FlashForge Adventurer 5M Integration

This project integrates the FlashForge Adventurer 5M 3D printer with Home Assistant.

## Features

- Monitor printer status
- Start, pause, and stop prints
- Receive notifications on print completion
- View print progress and details

## Requirements

- Home Assistant 2023.10 or later
- FlashForge Adventurer 5M 3D printer
- Network connection to the printer

## Installation

1. Clone this repository to your Home Assistant config\custom_components directory:

    ```bash
    git clone https://github.com/yourusername/flashforge_adventurer5m.git
    ```

2. Add the following to your `configuration.yaml`:

    ```yaml
    flashforge_adventurer5m:
      host: YOUR_PRINTER_IP
      api_key: YOUR_API_KEY
    ```

3. Restart Home Assistant.

## Usage

After installation, you can find the FlashForge Adventurer 5M integration in the Home Assistant UI. Use the provided controls to manage your 3D printer.

## Contributing

Contributions are welcome! Please fork this repository and submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgements

Special thanks to the Home Assistant community for their support and contributions.
