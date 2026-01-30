"""Wiimote driver for mouse control."""

import time
import logging
import threading
import queue
from typing import Optional, Tuple, List, Callable
from dataclasses import dataclass

from src.mouse.filters import LowPassFilter
from src.wiimote.protocol import WiimoteProtocol, ButtonState

try:
    import hid
    HID_AVAILABLE = True
except Exception as exc:
    hid = None
    HID_AVAILABLE = False
    HID_IMPORT_ERROR = exc


@dataclass
class WiimoteState:
    """Current state of the Wiimote."""
    buttons: int = 0
    accel_x: int = 0
    accel_y: int = 0
    accel_z: int = 0
    gyro_x: int = 0
    gyro_y: int = 0
    gyro_z: int = 0
    gyro_raw_x: Optional[int] = None
    gyro_raw_y: Optional[int] = None
    gyro_raw_z: Optional[int] = None
    ir_x: int = 0
    ir_y: int = 0
    ir_visible: bool = False
    effective_mode: str = "MotionPlus"
    battery_level: int = -1
    last_report_id: Optional[int] = None
    last_extension_hex: Optional[str] = None
    extension_connected: Optional[bool] = None
    motionplus_connected: Optional[bool] = None
    nunchuk_connected: Optional[bool] = None
    nunchuk_stick_x: Optional[int] = None
    nunchuk_stick_y: Optional[int] = None
    nunchuk_c: bool = False
    nunchuk_z: bool = False


@dataclass
class DriverState:
    """Driver state for connection and control."""
    connected: bool = False
    control_enabled: bool = False
    profile: str = "default"
    mode: str = "MotionPlus"
    reconnecting: bool = False


class WiimoteDriver:
    """Driver for Wiimote communication and control."""
    
    # Nintendo Wiimote IDs
    NINTENDO_VENDOR_ID = 0x057E
    WIIMOTE_PRODUCT_ID = 0x0306
    WIIMOTE_PLUS_PRODUCT_ID = 0x0330
    
    # Button masks
    BUTTON_TWO = 0x0001
    BUTTON_ONE = 0x0002
    BUTTON_B = 0x0004
    BUTTON_A = 0x0008
    BUTTON_MINUS = 0x0010
    BUTTON_HOME = 0x0020
    BUTTON_PLUS = 0x0040
    BUTTON_LEFT = 0x0080
    BUTTON_RIGHT = 0x0100
    BUTTON_DOWN = 0x0200
    BUTTON_UP = 0x0400
    
    def __init__(self, config: Optional[object] = None):
        """Initialize driver."""
        self.logger = logging.getLogger(__name__)
        self.device = None
        self.state = WiimoteState()
        self.driver_state = DriverState()
        self.running = False
        self.motionplus_enabled = True

        # Config (optional)
        self.config = config

        if hasattr(self.config, 'get_active_profile'):
            self.driver_state.profile = self.config.get_active_profile()
        if hasattr(self.config, 'get_mode'):
            self.driver_state.mode = self.config.get_mode()
            self.state.effective_mode = self.driver_state.mode

        # Calibration offsets
        self._gyro_offset = (0.0, 0.0, 0.0)
        self._accel_offset = (0.0, 0.0, 0.0)

        # Protocol parser
        self._protocol = WiimoteProtocol()

        # Extension selection
        self._extension_auto = False
        self.extension_type = self._init_extension_settings()
        self._ir_enabled = False

        # Low-pass filters
        gyro_alpha = self._get_float('Filters', 'gyro_lowpass_alpha', 0.25)
        accel_alpha = self._get_float('Filters', 'accel_lowpass_alpha', 0.25)
        self._gyro_filters = (
            LowPassFilter(gyro_alpha),
            LowPassFilter(gyro_alpha),
            LowPassFilter(gyro_alpha),
        )
        self._accel_filters = (
            LowPassFilter(accel_alpha),
            LowPassFilter(accel_alpha),
            LowPassFilter(accel_alpha),
        )
        
        # Callbacks
        self.on_state_update: Optional[Callable[[WiimoteState], None]] = None
        self.on_button_press: Optional[Callable[[List[str]], None]] = None
        self.on_driver_state_change: Optional[Callable[[DriverState], None]] = None

        # Event queue for HID read loop
        self._event_queue: "queue.Queue[bytes]" = queue.Queue(maxsize=256)
        self._read_thread: Optional[threading.Thread] = None
        self._read_stop = threading.Event()
        self._read_timeout_ms = 50
        self._last_read_error: Optional[Exception] = None
        self._read_failures = 0
        self._read_loop_wanted = False

        # Status request management
        self._last_status_request = 0.0
        self._status_request_interval = self._get_float('General', 'status_poll_interval', 2.5)

        # Reconnect management
        self._reconnect_thread: Optional[threading.Thread] = None
        self._reconnect_stop = threading.Event()
        self._reconnect_lock = threading.Lock()
        # Report mode tracking
        self._last_report_mode_set = 0.0
        self._last_gyro_update = 0.0
        self._last_gyro_parse_warn = 0.0

    def set_motionplus_enabled(self, enabled: bool):
        """Enable or disable MotionPlus usage (gyro)."""
        self.motionplus_enabled = bool(enabled)
        self.logger.info(f"MotionPlus {'enabled' if enabled else 'disabled'}")
        
        # Reset calibration offsets
        self._gyro_offset = (0.0, 0.0, 0.0)
        self._accel_offset = (0.0, 0.0, 0.0)

        # Recreate filters with current settings
        gyro_alpha = self._get_float('Filters', 'gyro_lowpass_alpha', 0.25)
        accel_alpha = self._get_float('Filters', 'accel_lowpass_alpha', 0.25)
        self._gyro_filters = (
            LowPassFilter(gyro_alpha),
            LowPassFilter(gyro_alpha),
            LowPassFilter(gyro_alpha),
        )
        self._accel_filters = (
            LowPassFilter(accel_alpha),
            LowPassFilter(accel_alpha),
            LowPassFilter(accel_alpha),
        )
        
        # If device is connected, reapply report mode
        if self.device and self.driver_state.connected:
            self._apply_report_mode_for_mode_change()
    
    def _apply_report_mode_for_mode_change(self):
        """Reapply report mode when switching between modes without disconnecting."""
        try:
            self.logger.info("Reapplying report mode for mode change...")
            time.sleep(0.1)  # Brief pause
            self._apply_report_mode()
            time.sleep(0.1)  # Allow device to adjust
            self.logger.info("Report mode reapplied successfully")
        except Exception as e:
            self.logger.warning(f"Failed to reapply report mode: {e}")

    def _get_int(self, section: str, key: str, fallback: int) -> int:
        if hasattr(self.config, 'get_int'):
            return self.config.get_int(section, key, fallback=fallback)
        return fallback

    def _get_float(self, section: str, key: str, fallback: float) -> float:
        if hasattr(self.config, 'get_float'):
            return self.config.get_float(section, key, fallback=fallback)
        return fallback

    def _get_bool(self, section: str, key: str, fallback: bool) -> bool:
        if hasattr(self.config, 'get_bool'):
            return self.config.get_bool(section, key, fallback=fallback)
        return fallback

    def _notify_driver_state(self):
        if self.on_driver_state_change:
            self.on_driver_state_change(self.driver_state)

    def _init_extension_settings(self) -> Optional[str]:
        raw = None
        if hasattr(self.config, 'get'):
            raw = self.config.get('General', 'extension', fallback='auto')
        extension = (raw or 'auto').strip().lower()

        if extension in ('auto', 'detect'):
            self._extension_auto = True
            return None
        if extension in ('none', 'off', 'disable', 'disabled'):
            return None
        if extension in ('motionplus', 'gyro'):
            return 'motionplus'
        if extension in ('nunchuk', 'nun', 'chuk'):
            return 'nunchuk'

        return None

    def _button_state_to_mask(self, buttons: ButtonState) -> int:
        mask = 0
        if buttons.Two:
            mask |= self.BUTTON_TWO
        if buttons.One:
            mask |= self.BUTTON_ONE
        if buttons.B:
            mask |= self.BUTTON_B
        if buttons.A:
            mask |= self.BUTTON_A
        if buttons.Minus:
            mask |= self.BUTTON_MINUS
        if buttons.Home:
            mask |= self.BUTTON_HOME
        if buttons.Plus:
            mask |= self.BUTTON_PLUS
        if buttons.DPad_Left:
            mask |= self.BUTTON_LEFT
        if buttons.DPad_Right:
            mask |= self.BUTTON_RIGHT
        if buttons.DPad_Down:
            mask |= self.BUTTON_DOWN
        if buttons.DPad_Up:
            mask |= self.BUTTON_UP
        return mask

    def _normalize_report(self, payload: bytes) -> Tuple[Optional[int], int]:
        if not payload:
            return None, 0
        if payload[0] == 0xA1 and len(payload) > 1:
            return payload[1], 2
        if 0x20 <= payload[0] <= 0x3F:
            return payload[0], 1
        return None, 0

    def request_status(self) -> bool:
        """Request a status report (battery + extension flags)."""
        if not self.device:
            return False
        try:
            self.device.write(bytes([0x15, 0x00]))
            self._last_status_request = time.time()
            return True
        except Exception as e:
            self.logger.debug(f"Status request failed: {e}")
            return False

    def set_control_enabled(self, enabled: bool):
        """Update control enabled state."""
        self.driver_state.control_enabled = enabled
        self._notify_driver_state()

    def set_profile(self, profile: str):
        """Update active profile in config and driver state."""
        if hasattr(self.config, 'set_active_profile'):
            self.config.set_active_profile(profile)
        self.driver_state.profile = profile
        self._notify_driver_state()

    def set_mode(self, mode: str):
        """Update desired mode in config and driver state."""
        if hasattr(self.config, 'set_mode'):
            self.config.set_mode(mode)
        self.driver_state.mode = mode
        self.state.effective_mode = mode
        self._notify_driver_state()

    def calibrate(self) -> bool:
        """Calibrate gyro and accelerometer baseline offsets."""
        if not self.device:
            return False

        samples = self._get_int('Calibration', 'samples', 60)
        sample_delay_ms = self._get_int('Calibration', 'sample_delay_ms', 5)
        gyro_target = self._get_int('Calibration', 'gyro_neutral', 8000)
        accel_target = self._get_int('Calibration', 'accel_neutral', 512)

        self.logger.info("Starting calibration...")
        gyro_samples: List[Tuple[int, int, int]] = []
        accel_samples: List[Tuple[int, int, int]] = []

        attempts = 0
        max_attempts = samples * 3
        while len(gyro_samples) < samples and attempts < max_attempts:
            attempts += 1
            raw = self._read_raw_state()
            if raw is None:
                time.sleep(sample_delay_ms / 1000.0)
                continue

            accel, gyro = raw
            accel_samples.append(accel)
            gyro_samples.append(gyro)
            time.sleep(sample_delay_ms / 1000.0)

        if not gyro_samples or not accel_samples:
            self.logger.warning("Calibration failed: no samples collected")
            return False

        avg_gyro = (
            sum(v[0] for v in gyro_samples) / len(gyro_samples),
            sum(v[1] for v in gyro_samples) / len(gyro_samples),
            sum(v[2] for v in gyro_samples) / len(gyro_samples),
        )
        avg_accel = (
            sum(v[0] for v in accel_samples) / len(accel_samples),
            sum(v[1] for v in accel_samples) / len(accel_samples),
            sum(v[2] for v in accel_samples) / len(accel_samples),
        )

        self._gyro_offset = (
            avg_gyro[0] - gyro_target,
            avg_gyro[1] - gyro_target,
            avg_gyro[2] - gyro_target,
        )
        self._accel_offset = (
            avg_accel[0] - accel_target,
            avg_accel[1] - accel_target,
            avg_accel[2] - accel_target,
        )

        # Reset filters to avoid using pre-calibration state
        for f in self._gyro_filters:
            f.reset()
        for f in self._accel_filters:
            f.reset()

        self.logger.info(
            "Calibration complete. Gyro offset=%s Accel offset=%s",
            self._gyro_offset,
            self._accel_offset,
        )
        return True
    
    def find_and_connect(self) -> bool:
        """Find and connect to Wiimote."""
        if not HID_AVAILABLE:
            self.logger.error("hidapi not available: %s", HID_IMPORT_ERROR)
            return False

        try:
            self.logger.info("Searching for Wiimote...")
            
            # Enumerate Nintendo devices
            devices = hid.enumerate(self.NINTENDO_VENDOR_ID)
            wiimote_devices = []
            
            for device_info in devices:
                product_id = device_info['product_id']
                if product_id in [self.WIIMOTE_PRODUCT_ID, self.WIIMOTE_PLUS_PRODUCT_ID]:
                    wiimote_devices.append(device_info)
            
            if not wiimote_devices:
                self.logger.error("No Wiimote found!")
                return False
            
            # Prefer Game Pad usage or interface 0
            device_info = None
            for candidate in wiimote_devices:
                interface_num = candidate.get('interface_number', -1)
                usage_page = candidate.get('usage_page', 0)
                usage = candidate.get('usage', 0)
                if usage_page == 0x0001 and usage == 0x0005:
                    device_info = candidate
                    break
                if interface_num == 0 or usage_page == 0x0001:
                    device_info = candidate
                    break
            if device_info is None:
                device_info = wiimote_devices[0]
            path = device_info.get('path')
            if isinstance(path, str):
                path = path.encode('utf-8')
            
            self.logger.info(f"Connecting to {device_info.get('product_string', 'Wiimote')}...")
            
            # Open device
            self.device = hid.device()
            self.device.open_path(path)
            
            self.logger.info("Connected! Initializing...")
            
            # Initialize Wiimote
            self._initialize()

            self.driver_state.connected = True
            self.driver_state.reconnecting = False
            self._notify_driver_state()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error connecting: {e}")
            return False
    
    def _initialize(self):
        """Initialize Wiimote settings."""
        # Set LED 1
        self.device.write(bytes([0x11, 0x10]))
        time.sleep(0.1)

        # Auto-detect extension if enabled
        if self._extension_auto:
            self.extension_type = self._detect_extension()

            # If auto-detect failed but mode requires MotionPlus, force it
            if self.extension_type is None and self.driver_state.mode in ("MotionPlus", "Gyro"):
                self.extension_type = "motionplus"

        if self.extension_type is None and self.driver_state.mode in ("MotionPlus", "Gyro", "Hybrid"):
            self.extension_type = "motionplus"

        # Enable extensions (MotionPlus/Nunchuk) if requested
        if self.extension_type == 'motionplus':
            self._enable_motionplus()
        elif self.extension_type == 'nunchuk':
            self._enable_nunchuk()

        # Configure report mode + IR
        self._apply_report_mode()

        # Request status info (battery/extension)
        self.request_status()

        # Validate MotionPlus activation
        self._check_motionplus_active()

        self.logger.info("Wiimote initialized!")

    def _detect_extension(self) -> Optional[str]:
        """Try to detect the connected extension by reading its ID."""
        # Known IDs (prefix for extensions)
        base_prefix = bytes([0x00, 0x00, 0xA4, 0x20])
        nunchuk_id = bytes([0x00, 0x00, 0xA4, 0x20, 0x00, 0x00])
        motionplus_ids = {
            bytes([0x00, 0x00, 0xA4, 0x20, 0x04, 0x05]),
            bytes([0x00, 0x00, 0xA4, 0x20, 0x05, 0x05]),
        }

        try:
            # Try Nunchuk init + ID read
            self._enable_nunchuk()
            ext_id = self._read_extension_id(0x04A400FE)
            if ext_id:
                if ext_id == nunchuk_id or ext_id.startswith(base_prefix):
                    return 'nunchuk'

            # Try MotionPlus init + ID read
            self._enable_motionplus()
            ext_id = self._read_extension_id(0x04A600FE)
            if ext_id:
                if ext_id in motionplus_ids or ext_id.startswith(base_prefix):
                    return 'motionplus'
        except Exception as e:
            self.logger.debug(f"Extension detection failed: {e}")

        return None

    def _read_extension_id(self, address: int) -> Optional[bytes]:
        """Read 6-byte extension ID from a register address."""
        data = self._read_memory(address, 6)
        if not data or len(data) < 6:
            return None
        return bytes(data[:6])

    def _check_motionplus_active(self) -> Optional[bool]:
        """Check whether MotionPlus is active by reading its ID registers."""
        if not self.device:
            return None

        try:
            ext_id = self._read_extension_id(0x04A400FE)
            mp_id = self._read_extension_id(0x04A600FE)
        except Exception:
            return None

        active_ids = {
            bytes([0x00, 0x00, 0xA4, 0x20, 0x04, 0x05]),
            bytes([0x00, 0x00, 0xA4, 0x20, 0x05, 0x05]),
            bytes([0x00, 0x00, 0xA4, 0x20, 0x07, 0x05]),
        }

        if ext_id in active_ids or mp_id in active_ids:
            self.state.motionplus_connected = True
            self.state.extension_connected = True
            return True

        inactive_ids = {
            bytes([0x00, 0x00, 0xA4, 0x20, 0x00, 0x05]),
            bytes([0x00, 0x00, 0xA6, 0x20, 0x00, 0x05]),
        }

        if ext_id in inactive_ids or mp_id in inactive_ids:
            self.state.motionplus_connected = False
            return False

        return None

    def _read_memory(self, address: int, size: int, timeout: float = 0.5) -> Optional[bytes]:
        """Read memory via 0x17 and wait for 0x21 response."""
        if not self.device:
            return None

        try:
            addr_bytes = address.to_bytes(3, byteorder='big')
            size_bytes = size.to_bytes(2, byteorder='big')
            self.device.write(bytes([0x17]) + addr_bytes + size_bytes)
        except Exception as e:
            self.logger.debug(f"Read memory request failed: {e}")
            return None

        end_time = time.time() + max(0.1, timeout)
        while time.time() < end_time:
            try:
                payload = self.device.read(32, 50)
                if not payload:
                    continue
                data = bytes(payload)

                if data[0] == 0xA1 and len(data) > 1:
                    report_id = data[1]
                    offset = 2
                else:
                    report_id = data[0]
                    offset = 1

                if report_id != 0x21:
                    continue

                if len(data) < offset + 6:
                    continue

                error = data[offset]
                if error != 0x00:
                    return None

                data_len = (data[offset + 4] & 0x0F) + 1
                start = offset + 5
                end = start + data_len
                return bytes(data[start:end])
            except Exception:
                continue

        return None

    def _apply_report_mode(self):
        mode = self.driver_state.mode
        wants_extension = mode in ("MotionPlus", "Gyro", "Hybrid")
        has_extension = self.extension_type in ('motionplus', 'nunchuk') or (
            wants_extension and self.extension_type is None
        )

        if mode == 'IR':
            report = 0x33
        elif mode == 'Hybrid':
            if self.extension_type == 'motionplus':
                report = 0x37
            else:
                report = 0x36 if has_extension else 0x33
        elif mode == 'Accel':
            report = 0x31
        else:
            if self.extension_type == 'motionplus':
                report = 0x35
            else:
                report = 0x32 if has_extension else 0x31

        self._set_report_mode(report)

        # Enable IR if needed
        if mode in ('IR', 'Hybrid'):
            self._enable_ir(True)
        else:
            self._enable_ir(False)

    def _set_report_mode(self, report_id: int):
        try:
            self.logger.info(f"Setting report mode to 0x{report_id:02X}")
            self.device.write(bytes([0x12, 0x04, report_id]))
            time.sleep(0.05)
            self._last_report_mode_set = time.time()
        except Exception as e:
            self.logger.debug(f"Failed to set report mode: {e}")

    def _enable_ir(self, enable: bool):
        if self._ir_enabled == enable:
            return
        self._ir_enabled = enable
        try:
            self.device.write(bytes([0x13, 0x04 if enable else 0x00]))
            if enable:
                self.device.write(bytes([0x1A, 0x04]))
                time.sleep(0.05)
                # Minimal IR initialization
                self._write_register(0x04B00030, bytes([0x08]))
        except Exception as e:
            self.logger.debug(f"Failed to toggle IR: {e}")

    def _write_register(self, address: int, data: bytes):
        addr_bytes = address.to_bytes(4, byteorder='big')
        size = len(data).to_bytes(1, byteorder='big')
        padded_data = data + bytes(16 - len(data))
        command = bytes([0x16]) + addr_bytes + size + padded_data
        try:
            self.device.write(command)
        except Exception as e:
            self.logger.debug(f"Register write failed: {e}")

    def _enable_nunchuk(self):
        try:
            # Standard extension init (Nunchuk)
            self._write_register(0x04A400F0, bytes([0x55]))
            time.sleep(0.05)
            self._write_register(0x04A400FB, bytes([0x00]))
            time.sleep(0.05)
        except Exception as e:
            self.logger.debug(f"Failed to enable Nunchuk: {e}")

    def _enable_motionplus(self):
        try:
            # MotionPlus init sequence
            self._write_register(0x04A600F0, bytes([0x55]))
            time.sleep(0.05)
            self._write_register(0x04A600FB, bytes([0x00]))
            time.sleep(0.05)
            # Enable MotionPlus mode explicitly
            self._write_register(0x04A600FE, bytes([0x04]))
            time.sleep(0.05)
        except Exception as e:
            self.logger.debug(f"Failed to enable MotionPlus: {e}")
    
    def read_state(self) -> bool:
        """Read current Wiimote state."""
        if not self.device:
            self._ensure_reconnect()
            return False

        if self._last_read_error:
            self._handle_disconnect(self._last_read_error)
            self._last_read_error = None
            return False
        
        try:
            data = None

            # If read loop is running, consume from queue
            if self._read_thread and self._read_thread.is_alive():
                data = self.get_event(timeout=0.02)
                if data is not None:
                    latest = data
                    while True:
                        next_item = self.get_event(timeout=0.0)
                        if next_item is None:
                            break
                        latest = next_item
                    data = latest
            else:
                data = self.device.read(32, 50)  # 50ms timeout

            if isinstance(data, bytes):
                payload = data
            elif data:
                payload = bytes(data)
            else:
                payload = None

            if payload and len(payload) > 2:
                raw_payload = payload[1:] if payload[0] == 0xA1 else payload
                extension_bytes = None

                # Periodically request status (battery/extension)
                if time.time() - self._last_status_request >= self._status_request_interval:
                    self.request_status()

                report_id, offset = self._normalize_report(payload)
                if report_id is not None:
                    self.state.last_report_id = report_id
                    # self.logger.debug(f"📥 Report ID: 0x{report_id:02X}")
                gyro_extension_bytes = None

                if report_id in (0x32, 0x35, 0x36, 0x37):
                    # Calculate extension data offset (after buttons + accel [+ IR])
                    # raw_payload may include report_id at index 0 depending on HID backend
                    has_report_id = raw_payload[0] == report_id
                    base_offset = 1 if has_report_id else 0
                    buttons_offset = base_offset
                    accel_offset = buttons_offset + 2

                    extension_offset = None
                    expected_len = 0

                    if report_id == 0x32:
                        extension_offset = accel_offset + 3
                        expected_len = 8
                    elif report_id == 0x35:
                        extension_offset = accel_offset + 3
                        expected_len = 16
                    elif report_id in (0x36, 0x37):
                        extension_offset = accel_offset + 3 + 10
                        expected_len = 6 if report_id == 0x37 else 16

                    extension_len = 0
                    if extension_offset is not None and extension_offset < len(raw_payload):
                        available_len = len(raw_payload) - extension_offset
                        extension_len = min(expected_len, available_len) if expected_len > 0 else available_len

                    if extension_offset is not None and extension_len > 0 and len(raw_payload) >= extension_offset + extension_len:
                        extension_bytes = raw_payload[extension_offset:extension_offset + extension_len]
                        self.state.last_extension_hex = extension_bytes.hex()
                        # self.logger.debug(f"📦 Extension bytes (len={extension_len}, offset={extension_offset}): {extension_bytes.hex()}")

                        # For MotionPlus, extension data contains gyro
                        wants_motionplus = self.driver_state.mode in ("MotionPlus", "Gyro", "Hybrid")
                        if self.extension_type == "motionplus" or (self.extension_type is None and wants_motionplus):
                            # Prefer first 6 bytes, but fall back to scanning extension for plausible MotionPlus data
                            best_offset = 0
                            best_score = -1
                            best_mp = None
                            max_start = max(0, len(extension_bytes) - 6)

                            for start in range(0, max_start + 1):
                                candidate = extension_bytes[start:start + 6]
                                mp_candidate = self._protocol.parse_motionplus(candidate, offset=0)
                                if mp_candidate is None:
                                    continue
                                high_bits = ((candidate[3] & 0xFC) != 0) + ((candidate[4] & 0xFC) != 0) + ((candidate[5] & 0xFC) != 0)
                                values = (mp_candidate.roll, mp_candidate.pitch, mp_candidate.yaw)
                                in_range = sum(1 for v in values if 1000 <= v <= 16000)
                                non_zero = sum(1 for v in values if v != 0)
                                score = (high_bits * 3) + (in_range * 2) + non_zero
                                if score > best_score:
                                    best_score = score
                                    best_offset = start
                                    best_mp = mp_candidate

                            if best_mp is not None and best_score >= 2:
                                gyro_extension_bytes = extension_bytes[best_offset:best_offset + 6]
                                # Map MotionPlus axes to X=Roll, Y=Pitch, Z=Yaw
                                self.state.gyro_raw_x = best_mp.roll
                                self.state.gyro_raw_y = best_mp.pitch
                                self.state.gyro_raw_z = best_mp.yaw
                                # self.logger.debug(f"✅ Gyro raw updated: X={best_mp.roll}, Y={best_mp.pitch}, Z={best_mp.yaw}")
                            else:
                                if time.time() - self._last_gyro_parse_warn > 1.0:
                                    self.logger.warning(
                                        f"⚠️ MotionPlus parse returned None/low-score from bytes: {extension_bytes[:6].hex()}"
                                    )
                                    self._last_gyro_parse_warn = time.time()
                        else:
                            self.logger.debug(f"ℹ️ Extension type is '{self.extension_type}', not motionplus")
                    else:
                        self.logger.warning(
                            f"⚠️ Not enough data for extension: len(raw_payload)={len(raw_payload)}, need {extension_offset + extension_len if extension_offset is not None else 'n/a'}"
                        )

                    # Fallback: scan entire payload for plausible MotionPlus block
                    wants_motionplus = self.driver_state.mode in ("MotionPlus", "Gyro", "Hybrid")
                    if gyro_extension_bytes is None and (self.extension_type == "motionplus" or (self.extension_type is None and wants_motionplus)):
                        scan_data = raw_payload[1:] if raw_payload and raw_payload[0] == report_id else raw_payload
                        if scan_data and len(scan_data) >= 6:
                            best_offset = 0
                            best_score = -1
                            best_mp = None
                            for start in range(0, len(scan_data) - 5):
                                candidate = scan_data[start:start + 6]
                                mp_candidate = self._protocol.parse_motionplus(candidate, offset=0)
                                if mp_candidate is None:
                                    continue
                                high_bits = ((candidate[3] & 0xFC) != 0) + ((candidate[4] & 0xFC) != 0) + ((candidate[5] & 0xFC) != 0)
                                values = (mp_candidate.roll, mp_candidate.pitch, mp_candidate.yaw)
                                in_range = sum(1 for v in values if 1000 <= v <= 16000)
                                non_zero = sum(1 for v in values if v != 0)
                                score = (high_bits * 3) + (in_range * 2) + non_zero
                                if score > best_score:
                                    best_score = score
                                    best_offset = start
                                    best_mp = mp_candidate
                            if best_mp is not None and best_score >= 2:
                                gyro_extension_bytes = scan_data[best_offset:best_offset + 6]
                                self.state.gyro_raw_x = best_mp.roll
                                self.state.gyro_raw_y = best_mp.pitch
                                self.state.gyro_raw_z = best_mp.yaw

                # Ensure report mode for MotionPlus is active (some devices revert)
                if self.driver_state.mode in ("MotionPlus", "Gyro", "Hybrid") and report_id in (0x31, 0x33):
                    if time.time() - self._last_report_mode_set > 1.0:
                        self._apply_report_mode()

                # Status report (battery + extension)
                if report_id == 0x20:
                    if len(payload) >= offset + 2:
                        buttons = (payload[offset] << 8) | payload[offset + 1]
                        self.state.buttons = buttons

                    if len(payload) >= offset + 4:
                        flags = payload[offset + 2]
                        self.state.extension_connected = (flags & 0x02) == 0
                        if not self.state.extension_connected:
                            self.state.motionplus_connected = False
                            self.state.nunchuk_connected = False

                    battery_raw = None
                    if len(payload) >= offset + 6:
                        battery_raw = payload[offset + 5]
                    elif len(payload) >= offset + 5:
                        battery_raw = payload[offset + 4]
                    elif len(payload) > 0:
                        battery_raw = payload[-1]

                    if battery_raw is not None:
                        # Wiimote battery: 0x00 = empty, 0xC8 (200) = full
                        # Scale: (raw / 200) * 100 para obter porcentagem
                        self.state.battery_level = min(100, int((battery_raw / 200.0) * 100))

                    if self.extension_type == "motionplus":
                        self._check_motionplus_active()

                    if self.on_state_update:
                        self.on_state_update(self.state)
                    return True

                # Parse report using protocol decoder
                data_for_parse = payload if payload[0] == 0xA1 else bytes([0xA1]) + payload
                result = self._protocol.parse_report(data_for_parse, extension=self.extension_type)

                # Buttons
                if result.get('buttons') is not None:
                    self.state.buttons = self._button_state_to_mask(result['buttons'])

                # Accelerometer
                if result.get('accel') is not None:
                    accel = result['accel']
                    accel_values = (
                        accel.x - self._accel_offset[0],
                        accel.y - self._accel_offset[1],
                        accel.z - self._accel_offset[2],
                    )
                    filtered_accel = (
                        self._accel_filters[0].apply(accel_values[0]),
                        self._accel_filters[1].apply(accel_values[1]),
                        self._accel_filters[2].apply(accel_values[2]),
                    )
                    self.state.accel_x = int(filtered_accel[0])
                    self.state.accel_y = int(filtered_accel[1])
                    self.state.accel_z = int(filtered_accel[2])

                # MotionPlus (gyro)
                gyro = result.get('motionplus')
                if gyro is None and self.extension_type == "motionplus" and report_id in (0x31, 0x33):
                    buttons_offset = 1
                    gyro_offset = buttons_offset + 5
                    gyro_extra_index = buttons_offset + 8
                    if len(raw_payload) > gyro_extra_index + 0:
                        gyro_x = raw_payload[gyro_offset] | ((raw_payload[gyro_extra_index] & 0xFC) << 6)
                        gyro_y = raw_payload[gyro_offset + 1] | ((raw_payload[gyro_extra_index] & 0x03) << 8)
                        gyro_z = raw_payload[gyro_offset + 2]
                        gyro = (gyro_x, gyro_y, gyro_z)

                if gyro is None and report_id in (0x31, 0x32, 0x35, 0x37):
                    wants_motionplus = self.driver_state.mode in ("MotionPlus", "Gyro", "Hybrid")
                    if self.extension_type == "motionplus" or (self.extension_type is None and wants_motionplus):
                        # raw_payload may include report_id at index 0
                        has_report_id = raw_payload[0] == report_id
                        base_offset = 1 if has_report_id else 0
                        buttons_offset = base_offset
                        accel_offset = buttons_offset + 2
                        if report_id in (0x36, 0x37):
                            extension_offset = accel_offset + 3 + 10
                        else:
                            extension_offset = accel_offset + 3
                        ext_start = extension_offset
                        if len(raw_payload) >= ext_start + 6:
                            extension_data = raw_payload[ext_start:]
                            gyro = self._protocol.parse_motionplus(extension_data, offset=0)

                if gyro is None and gyro_extension_bytes and len(gyro_extension_bytes) >= 6 and report_id in (0x32, 0x35, 0x37):
                    gyro = self._protocol.parse_motionplus(gyro_extension_bytes, offset=0)

                if gyro is None and gyro_extension_bytes and len(gyro_extension_bytes) >= 6 and report_id in (0x32, 0x35, 0x37):
                    b0, b1, b2, b3, b4, b5 = gyro_extension_bytes[:6]
                    yaw = b0 | ((b3 & 0xFC) << 6)
                    roll = b1 | ((b4 & 0xFC) << 6)
                    pitch = b2 | ((b5 & 0xFC) << 6)
                    gyro = (yaw, pitch, roll)

                if gyro is not None:
                    if hasattr(gyro, "yaw"):
                        # Map MotionPlus axes to X=Roll, Y=Pitch, Z=Yaw
                        self.state.gyro_raw_x = gyro.roll
                        self.state.gyro_raw_y = gyro.pitch
                        self.state.gyro_raw_z = gyro.yaw
                        gyro_values = (
                            gyro.roll - self._gyro_offset[0],
                            gyro.pitch - self._gyro_offset[1],
                            gyro.yaw - self._gyro_offset[2],
                        )
                    else:
                        # Tuple assumed as (yaw, pitch, roll)
                        self.state.gyro_raw_x = gyro[2]
                        self.state.gyro_raw_y = gyro[1]
                        self.state.gyro_raw_z = gyro[0]
                        gyro_values = (
                            gyro[2] - self._gyro_offset[0],
                            gyro[1] - self._gyro_offset[1],
                            gyro[0] - self._gyro_offset[2],
                        )
                    filtered_gyro = (
                        self._gyro_filters[0].apply(gyro_values[0]),
                        self._gyro_filters[1].apply(gyro_values[1]),
                        self._gyro_filters[2].apply(gyro_values[2]),
                    )
                    self.state.gyro_x = int(filtered_gyro[0])
                    self.state.gyro_y = int(filtered_gyro[1])
                    self.state.gyro_z = int(filtered_gyro[2])
                    self._last_gyro_update = time.time()
                    # self.logger.debug(f"✅ Gyro filtered updated: X={self.state.gyro_x}, Y={self.state.gyro_y}, Z={self.state.gyro_z}")
                else:
                    self.logger.debug("⚠️ Gyro is None - not updated")

                # IR points
                ir_points = result.get('ir_points') or []
                if ir_points:
                    self.state.ir_visible = True
                    self.state.ir_x = ir_points[0].x
                    self.state.ir_y = ir_points[0].y
                else:
                    self.state.ir_visible = False

                # Nunchuk
                if result.get('nunchuk') is not None:
                    nunchuk = result['nunchuk']
                    self.state.nunchuk_connected = True
                    self.state.nunchuk_stick_x = nunchuk.stick_x
                    self.state.nunchuk_stick_y = nunchuk.stick_y
                    self.state.nunchuk_c = nunchuk.buttons.C
                    self.state.nunchuk_z = nunchuk.buttons.Z
                else:
                    self.state.nunchuk_connected = False if self.extension_type == 'nunchuk' else None

                has_gyro = gyro is not None and self.motionplus_enabled
                has_accel = result.get('accel') is not None
                has_ir = self.state.ir_visible
                self.state.effective_mode = self._select_effective_mode(
                    has_gyro=has_gyro,
                    has_accel=has_accel,
                    has_ir=has_ir,
                )

                if has_gyro:
                    self.state.motionplus_connected = True
                    self.state.extension_connected = True
                elif not self.motionplus_enabled:
                    self.state.motionplus_connected = False
                    if self.extension_type is None:
                        self.state.extension_connected = None
                    else:
                        self.state.extension_connected = False
                elif self.extension_type == 'nunchuk' and self.state.nunchuk_connected:
                    self.state.motionplus_connected = False
                    self.state.extension_connected = True
                elif self.extension_type is None:
                    self.state.motionplus_connected = None
                    self.state.extension_connected = None
                else:
                    self.state.motionplus_connected = False
                    self.state.extension_connected = False
                
                # Trigger callbacks
                if self.on_state_update:
                    self.on_state_update(self.state)
                
                # Check for button presses
                if self.on_button_press and self.state.buttons:
                    button_names = self.get_pressed_buttons(self.state.buttons)
                    if button_names:
                        self.on_button_press(button_names)
                
                return True
            
            return False
            
        except Exception as e:
            if "timeout" not in str(e).lower():
                self.logger.debug(f"Read error: {e}")
                self._handle_disconnect(e)
            return False

    def start_read_loop(self, timeout_ms: int = 20, queue_size: Optional[int] = None) -> bool:
        """Start background HID read loop that enqueues raw reports."""
        if not self.device:
            self.logger.warning("Cannot start read loop: not connected")
            return False

        if self._read_thread and self._read_thread.is_alive():
            return True

        if queue_size is not None and queue_size > 0:
            self._event_queue = queue.Queue(maxsize=queue_size)

        self._read_timeout_ms = max(1, int(timeout_ms))
        self._read_stop.clear()
        self._last_read_error = None
        self._read_loop_wanted = True
        self._read_thread = threading.Thread(target=self._read_loop, name="WiimoteReadLoop", daemon=True)
        self._read_thread.start()
        return True

    def stop_read_loop(self, join_timeout: float = 1.0):
        """Stop background read loop and wait briefly for completion."""
        self._read_stop.set()
        if self._read_thread and self._read_thread.is_alive():
            if threading.current_thread() is not self._read_thread:
                self._read_thread.join(timeout=join_timeout)
        self._read_thread = None
        self._read_loop_wanted = False

    def get_event(self, timeout: float = 0.0) -> Optional[bytes]:
        """Get next queued HID report."""
        try:
            if timeout and timeout > 0:
                return self._event_queue.get(timeout=timeout)
            return self._event_queue.get_nowait()
        except queue.Empty:
            return None

    def drain_events(self, max_events: Optional[int] = None) -> List[bytes]:
        """Drain up to max_events queued HID reports."""
        drained: List[bytes] = []
        while True:
            if max_events is not None and len(drained) >= max_events:
                break
            try:
                drained.append(self._event_queue.get_nowait())
            except queue.Empty:
                break
        return drained

    def _read_loop(self):
        """Background loop reading HID reports and enqueuing."""
        self.logger.info("Starting HID read loop...")
        try:
            while not self._read_stop.is_set():
                if not self.device:
                    break
                try:
                    data = self.device.read(32, self._read_timeout_ms)
                    if data:
                        payload = bytes(data)
                        try:
                            self._event_queue.put_nowait(payload)
                        except queue.Full:
                            try:
                                _ = self._event_queue.get_nowait()
                                self._event_queue.put_nowait(payload)
                            except queue.Empty:
                                pass
                except Exception as e:
                    if "timeout" not in str(e).lower():
                        self._last_read_error = e
                        self.logger.warning(f"HID read error, stopping read loop: {e}")
                        break
        finally:
            self.logger.info("HID read loop stopped")
            if self._last_read_error:
                self._handle_disconnect(self._last_read_error)
    
    def get_pressed_buttons(self, buttons: int) -> List[str]:
        """Get list of pressed button names."""
        pressed = []
        
        if buttons & self.BUTTON_TWO: pressed.append("TWO")
        if buttons & self.BUTTON_ONE: pressed.append("ONE")
        if buttons & self.BUTTON_B: pressed.append("B")
        if buttons & self.BUTTON_A: pressed.append("A")
        if buttons & self.BUTTON_MINUS: pressed.append("MINUS")
        if buttons & self.BUTTON_HOME: pressed.append("HOME")
        if buttons & self.BUTTON_PLUS: pressed.append("PLUS")
        if buttons & self.BUTTON_LEFT: pressed.append("LEFT")
        if buttons & self.BUTTON_RIGHT: pressed.append("RIGHT")
        if buttons & self.BUTTON_DOWN: pressed.append("DOWN")
        if buttons & self.BUTTON_UP: pressed.append("UP")
        
        return pressed

    def _read_raw_state(self) -> Optional[Tuple[Tuple[int, int, int], Tuple[int, int, int]]]:
        """Read raw accel/gyro values without calibration or filtering."""
        if not self.device:
            return None

        try:
            data = self.device.read(32, 50)
            if not data or len(data) <= 8:
                return None

            payload = bytes(data)
            raw_payload = payload[1:] if payload and payload[0] == 0xA1 else payload
            report_id, offset = self._normalize_report(payload)
            has_report_id = raw_payload[0] == report_id if report_id is not None and raw_payload else False
            buttons_offset = 1 if has_report_id else 0
            accel_offset = buttons_offset + 2
            gyro_offset = buttons_offset + 5
            gyro_extra_index = buttons_offset + 8

            if len(raw_payload) <= accel_offset + 2:
                return None

            accel = (raw_payload[accel_offset], raw_payload[accel_offset + 1], raw_payload[accel_offset + 2])
            gyro_x = (
                raw_payload[gyro_offset] | ((raw_payload[gyro_extra_index] & 0xFC) << 6)
            ) if len(raw_payload) > gyro_extra_index else raw_payload[gyro_offset]
            gyro_y = (
                raw_payload[gyro_offset + 1] | ((raw_payload[gyro_extra_index] & 0x03) << 8)
            ) if len(raw_payload) > gyro_extra_index else raw_payload[gyro_offset + 1]
            gyro_z = raw_payload[gyro_offset + 2]
            return accel, (gyro_x, gyro_y, gyro_z)

        except Exception:
            return None
    
    def set_leds(self, led1=False, led2=False, led3=False, led4=False):
        """Set LED states."""
        if not self.device:
            return
        
        led_byte = (
            (0x10 if led1 else 0) |
            (0x20 if led2 else 0) |
            (0x40 if led3 else 0) |
            (0x80 if led4 else 0)
        )
        
        try:
            self.device.write(bytes([0x11, led_byte]))
        except Exception as e:
            self.logger.error(f"Error setting LEDs: {e}")
    
    def rumble(self, enable: bool, duration: float = 0.2):
        """Trigger rumble."""
        if not self.device:
            return
        
        try:
            # Turn on rumble
            if enable:
                self.device.write(bytes([0x10, 0x01]))
                time.sleep(duration)
                self.device.write(bytes([0x10, 0x00]))
        except Exception as e:
            self.logger.error(f"Error setting rumble: {e}")
    
    def disconnect(self):
        """Disconnect from Wiimote."""
        self._stop_reconnect_loop()
        self.stop_read_loop()
        if self.device:
            try:
                # Turn off LEDs
                self.device.write(bytes([0x11, 0x00]))
                time.sleep(0.1)
                self.device.close()
            except:
                pass
            
            self.device = None

        self.driver_state.connected = False
        self.driver_state.reconnecting = False
        self._notify_driver_state()
        
        self.logger.info("Disconnected")

    def _handle_disconnect(self, error: Optional[Exception] = None):
        if not self.driver_state.connected and self.device is None:
            return

        if error:
            self.logger.warning(f"Wiimote disconnected: {error}")
        else:
            self.logger.warning("Wiimote disconnected")

        self.stop_read_loop()
        if self.device:
            try:
                self.device.close()
            except Exception:
                pass
            self.device = None

        self.driver_state.connected = False
        self.driver_state.reconnecting = self._get_bool('Reconnect', 'enabled', True)
        self._notify_driver_state()

        self._ensure_reconnect()

    def _ensure_reconnect(self):
        if not self._get_bool('Reconnect', 'enabled', True):
            return
        if self.driver_state.connected:
            return
        with self._reconnect_lock:
            if self._reconnect_thread and self._reconnect_thread.is_alive():
                return
            self._reconnect_stop.clear()
            self._reconnect_thread = threading.Thread(
                target=self._reconnect_loop,
                name="WiimoteReconnect",
                daemon=True,
            )
            self._reconnect_thread.start()

    def _stop_reconnect_loop(self):
        self._reconnect_stop.set()
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            self._reconnect_thread.join(timeout=1.0)
        self._reconnect_thread = None

    def _reconnect_loop(self):
        initial_delay = self._get_float('Reconnect', 'initial_delay', 0.5)
        max_delay = self._get_float('Reconnect', 'max_delay', 3.0)
        backoff = self._get_float('Reconnect', 'backoff_factor', 1.6)
        jitter = self._get_float('Reconnect', 'jitter', 0.1)

        delay = max(0.1, initial_delay)
        while not self._reconnect_stop.is_set():
            if self.driver_state.connected:
                self.driver_state.reconnecting = False
                self._notify_driver_state()
                return

            self.driver_state.reconnecting = True
            self._notify_driver_state()

            self.logger.info(f"Reconnecting in {delay:.2f}s...")
            time.sleep(delay)
            if self._reconnect_stop.is_set():
                return

            if self.find_and_connect():
                self.driver_state.connected = True
                self.driver_state.reconnecting = False
                self._notify_driver_state()
                if self._read_loop_wanted:
                    self.start_read_loop(timeout_ms=self._read_timeout_ms)
                return

            delay = min(max_delay, delay * backoff)
            if jitter > 0:
                delay = max(0.1, delay + (jitter * (0.5 - time.time() % 1)))

    def _select_effective_mode(self, has_gyro: bool, has_accel: bool, has_ir: bool) -> str:
        """
        Select effective mode based on available sensors.
        Priority system for auto-detection:
        - Accel (base - always available)
        - Accel + IR (when sensor bar active)
        - Accel + Gyro (when MotionPlus available)
        - Accel + Gyro + IR (all resources)
        """
        auto_mode_enabled = self._get_bool('General', 'auto_mode_enabled', True)
        
        if not auto_mode_enabled:
            # Use configured mode if auto mode disabled
            desired_mode = self.driver_state.mode
            fallback_ir = self._get_bool('Fallback', 'enable_ir', False)

            if desired_mode in ("MotionPlus", "Gyro"):
                if has_gyro:
                    return "MotionPlus"
                if fallback_ir and has_ir:
                    return "IR"
                return "Accel" if has_accel else "MotionPlus"

            if desired_mode == "Hybrid":
                if has_ir:
                    return "Hybrid"
                if has_gyro:
                    return "MotionPlus"
                if fallback_ir and has_ir:
                    return "IR"
                return "Accel" if has_accel else "Hybrid"

            if desired_mode == "IR":
                if has_ir:
                    return "IR"
                if has_gyro:
                    return "MotionPlus"
                return "Accel" if has_accel else "IR"

            return desired_mode
        
        # Auto mode: combine sensors based on availability
        if has_gyro and has_ir:
            return "MotionPlus"  # Accel + Gyro + IR (all)
        elif has_gyro:
            return "MotionPlus"  # Accel + Gyro
        elif has_ir:
            return "Hybrid"  # Accel + IR
        else:
            return "Accel"  # Accel only
