# Contributing to Flashforge Adventurer 5M Integration

Thank you for considering contributing to this project! This guide will help you understand our development process and testing requirements.

## Important Testing Notes

This integration's test suite is designed for **local development only** and requires access to a physical Flashforge Adventurer 5M printer. To protect security and ensure safe testing:

- All test files are excluded from git
- Never commit real printer credentials
- Use mock data for all tests
- Keep test files local only

## Development Setup

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/yourusername/flashforge_adventurer5m.git
   cd flashforge_adventurer5m
   ```

2. Set up your test environment:
   ```bash
   python scripts/setup_test_env.py --printer-ip YOUR_PRINTER_IP --serial YOUR_SERIAL --code YOUR_CODE
   ```

3. Install development dependencies:
   ```bash
   pip install -r requirements_test.txt
   ```

## Testing Requirements

### Local Testing

1. **Development Printer**
   - Use a dedicated development printer
   - Never test against production printers
   - Monitor printer state during tests

2. **Test Environment**
   - Set up local test configuration
   - Use mock data for tests
   - Keep test files private

3. **Security**
   - No real credentials in code
   - No sensitive data in tests
   - No production dependencies

### Writing Tests

1. **Use Mock Data**
   ```bash
   python scripts/generate_test_data.py
   ```

2. **Test Categories**
   - Unit tests (required)
   - Integration tests (required)
   - Performance tests (optional)
   - Stress tests (optional)

3. **Test Documentation**
   - Document test cases
   - Document mock data
   - Document test requirements

### Running Tests

1. Quick test suite:
   ```bash
   python scripts/run_test_suite.py --config quick
   ```

2. Full test suite:
   ```bash
   python scripts/run_test_suite.py --config full
   ```

3. Check coverage:
   ```bash
   python scripts/analyze_coverage.py
   ```

## Code Style

1. **Python**
   - Follow Black formatting
   - Use type hints
   - Document functions

2. **Testing**
   - Clear test names
   - Documented fixtures
   - Proper assertions

3. **Documentation**
   - Update README.md
   - Update docstrings
   - Update comments

## Pull Request Process

1. **Branch**
   - Create feature branch
   - Keep changes focused
   - Regular commits

2. **Testing**
   - Add/update tests
   - Run full test suite
   - Check coverage

3. **Review**
   - Follow PR template
   - Address feedback
   - Keep security in mind

## Security

### Never Include:
- Real printer credentials
- Network configuration
- Personal identifiers
- Private API keys

### Always:
- Use mock data
- Follow security guidelines
- Review for sensitive data
- Test locally first

## Development Workflow

1. **Planning**
   - Check existing issues
   - Discuss changes
   - Plan implementation

2. **Development**
   - Write tests first
   - Implement changes
   - Document code

3. **Testing**
   - Run all tests
   - Check coverage
   - Verify locally

4. **Review**
   - Self-review changes
   - Update documentation
   - Submit PR

## Getting Help

- Review [test documentation](tests/README.md)
- Check existing issues
- Ask for clarification
- Follow guidelines

## Troubleshooting

### Common Issues

1. **Test Failures**
   - Check mock data
   - Verify setup
   - Review logs

2. **Coverage Issues**
   - Add missing tests
   - Check edge cases
   - Update mocks

3. **Security Concerns**
   - Review guidelines
   - Check for credentials
   - Verify data safety

## Additional Resources

- [Testing Guide](tests/README.md)
- [Security Guidelines](tests/test_data/README.md)
- [Mock Data Guide](scripts/README.md)

## Questions?

If you have questions about contributing or testing:
1. Check existing documentation
2. Review closed issues
3. Open a new issue

Thank you for contributing to the Flashforge Adventurer 5M integration!

