# Logs Directory

This directory contains application logs generated during execution.

## Log Files

- `wii_mouse.log` - Main application log
  - INFO: Connection status, calibration events
  - DEBUG: Sensor data, FPS, detailed operations
  - WARNING: Non-critical issues
  - ERROR: Operation errors
  - CRITICAL: Fatal errors

## Log Rotation

Logs are not automatically rotated. To clear old logs:

```bash
# Windows
del logs\*.log

# Linux/Mac
rm logs/*.log
```

## Log Format

```
2026-01-25 10:30:45,123 - wiimote.connection - INFO - Connected to Wiimote successfully!
2026-01-25 10:30:45,234 - wiimote.sensors - INFO - Calibrating sensors...
2026-01-25 10:30:47,456 - main - INFO - Driver active
```

## Debugging

To enable detailed logging:

```bash
python src/main.py --debug
```

This will output DEBUG level messages showing:
- Raw sensor values
- FPS (frames per second)
- Battery level
- Button states
- IR visibility
