"""HID connection management for Wiimote using hidapi."""

import logging
import time
import sys
import threading
import queue
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple

try:
    import hid
    HID_AVAILABLE = True
except ImportError:
    HID_AVAILABLE = False
    logging.warning("hidapi not available, Wiimote functionality disabled")


@dataclass
class WiimoteHIDEvent:
    """Represents a raw HID event from the Wiimote."""
    timestamp: float
    data: bytes


class WiimoteConnection:
    """Manages HID connection to Wii Remote using hidapi."""
    
    # Nintendo Wiimote USB Vendor/Product IDs
    NINTENDO_VENDOR_ID = 0x057E
    WIIMOTE_PRODUCT_ID = 0x0306  # Original Wiimote
    WIIMOTE_PLUS_PRODUCT_ID = 0x0330  # Wiimote Plus (with MotionPlus built-in)
    
    # Report IDs
    REPORT_LED = 0x11
    REPORT_MODE = 0x12
    REPORT_IR_ENABLE_1 = 0x13
    REPORT_IR_ENABLE_2 = 0x1A
    REPORT_STATUS_REQUEST = 0x15
    REPORT_WRITE_MEMORY = 0x16
    REPORT_READ_MEMORY = 0x17
    
    # Output report flag
    REPORT_OUTPUT = 0xA2
    
    def __init__(self):
        """Initialize Wiimote connection handler."""
        self.logger = logging.getLogger(__name__)
        self.device = None
        self.device_info = None
        self.connected = False
        self.rumble_state = False  # Track rumble state
        self.auto_reconnect = True
        self._read_thread: Optional[threading.Thread] = None
        self._read_stop = threading.Event()
        self._read_timeout_ms = 100
        self._event_queue: "queue.Queue[WiimoteHIDEvent]" = queue.Queue(maxsize=256)
        self._last_read_error: Optional[Exception] = None
        self._read_loop_wanted = False

        self._reconnect_thread: Optional[threading.Thread] = None
        self._reconnect_stop = threading.Event()
        self._reconnect_lock = threading.Lock()
        self._reconnect_initial_delay = 0.5
        self._reconnect_max_delay = 3.0
        self._reconnect_backoff = 1.6
        self._reconnect_jitter = 0.1
        
        if not HID_AVAILABLE:
            self.logger.error("hidapi not available - install hidapi: pip install hidapi")
    
    def find_wiimote(self, timeout: int = 10) -> Optional[Dict[str, Any]]:
        """
        Search for Wiimote via HID.
        
        Args:
            timeout: Search timeout in seconds
            
        Returns:
            Device info dict if found, None otherwise
        """
        if not HID_AVAILABLE:
            self.logger.error("hidapi not available")
            return None
        
        self.logger.info(f"Searching for Wiimote (timeout: {timeout}s)...")
        
        try:
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                # Enumerate HID devices
                devices = hid.enumerate(self.NINTENDO_VENDOR_ID)
                
                # Filter for Wiimote devices
                wiimote_devices = []
                for device_info in devices:
                    product_id = device_info['product_id']
                    
                    # Check if it's a Wiimote
                    if product_id in [self.WIIMOTE_PRODUCT_ID, self.WIIMOTE_PLUS_PRODUCT_ID]:
                        wiimote_devices.append(device_info)
                
                if wiimote_devices:
                    # Log all found interfaces
                    self.logger.debug(f"Found {len(wiimote_devices)} Wiimote interface(s)")
                    
                    for i, dev in enumerate(wiimote_devices):
                        path = dev.get('path', b'Unknown')
                        if isinstance(path, bytes):
                            path = path.decode('utf-8', errors='ignore')
                        self.logger.debug(f"  Interface {i}: {path}")
                        self.logger.debug(f"    Interface: {dev.get('interface_number', -1)}")
                        self.logger.debug(f"    Usage Page: 0x{dev.get('usage_page', 0):04X}")
                        self.logger.debug(f"    Usage: 0x{dev.get('usage', 0):04X}")
                    
                    # Try to find the primary interface (usage_page 0x0001, usage 0x0005)
                    # or interface 0
                    for device_info in wiimote_devices:
                        interface_num = device_info.get('interface_number', -1)
                        usage_page = device_info.get('usage_page', 0)
                        usage = device_info.get('usage', 0)
                        
                        # Prefer Generic Desktop / Game Pad
                        if usage_page == 0x0001 and usage == 0x0005:
                            product_name = device_info.get('product_string', 'Unknown')
                            product_id = device_info['product_id']
                            device_type = "Wiimote Plus" if product_id == self.WIIMOTE_PLUS_PRODUCT_ID else "Wiimote"
                            
                            self.logger.info(f"✓ Found {device_type}: {product_name}")
                            self.logger.debug(f"  Using interface {interface_num}")
                            return device_info

                        # Interface 0 or usage_page 0x0001 is usually the main control interface
                        if interface_num == 0 or usage_page == 0x0001:
                            product_name = device_info.get('product_string', 'Unknown')
                            product_id = device_info['product_id']
                            device_type = "Wiimote Plus" if product_id == self.WIIMOTE_PLUS_PRODUCT_ID else "Wiimote"
                            
                            self.logger.info(f"✓ Found {device_type}: {product_name}")
                            self.logger.debug(f"  Using interface {interface_num}")
                            return device_info
                    
                    # If no interface 0 found, use the first one
                    self.logger.warning("No interface 0 found, using first available")
                    device_info = wiimote_devices[0]
                    product_name = device_info.get('product_string', 'Unknown')
                    product_id = device_info['product_id']
                    device_type = "Wiimote Plus" if product_id == self.WIIMOTE_PLUS_PRODUCT_ID else "Wiimote"
                    self.logger.info(f"✓ Found {device_type}: {product_name}")
                    return device_info
                
                # Wait before next scan
                time.sleep(1)
            
            self.logger.warning("Wiimote not found within timeout")
            self.logger.info("Make sure Wiimote is paired with Windows Bluetooth settings")
            return None
        
        except Exception as e:
            self.logger.exception(f"Error searching for Wiimote: {e}")
            return None
    
    def list_all_wiimotes(self) -> List[Dict[str, Any]]:
        """
        List all connected Wiimotes.
        
        Returns:
            List of device info dicts
        """
        if not HID_AVAILABLE:
            return []
        
        try:
            devices = hid.enumerate(self.NINTENDO_VENDOR_ID)
            wiimotes = []
            
            for device_info in devices:
                product_id = device_info['product_id']
                if product_id in [self.WIIMOTE_PRODUCT_ID, self.WIIMOTE_PLUS_PRODUCT_ID]:
                    wiimotes.append(device_info)
            
            return wiimotes
        
        except Exception as e:
            self.logger.error(f"Error listing Wiimotes: {e}")
            return []
            return []
    
    def connect(self, device_info: Optional[Dict[str, Any]] = None, timeout: int = 30) -> bool:
        """
        Connect to Wiimote.
        
        Args:
            device_info: Device info dict from find_wiimote() (auto-detect if None)
            timeout: Connection timeout in seconds
            
        Returns:
            True if connected successfully
        """
        if not HID_AVAILABLE:
            self.logger.error("hidapi not available")
            return False
        
        try:
            # Find Wiimote if device_info not provided
            if device_info is None:
                device_info = self.find_wiimote(timeout)
                if device_info is None:
                    self.logger.error(
                        "Wiimote not found. Ensure it is paired and press 1+2 to sync."
                    )
                    return False
            
            self.device_info = device_info
            path = device_info.get('path')

            if not path:
                self.logger.error(
                    "Wiimote device path missing in HID info. Device info: %s",
                    device_info,
                )
                return False
            
            # Ensure path is bytes
            if isinstance(path, str):
                path = path.encode('utf-8')
            
            self.logger.info(f"Connecting to Wiimote...")
            
            # Open HID device
            self.device = hid.device()
            self.device.open_path(path)  # Pass bytes directly
            
            # Set non-blocking mode initially
            self.device.set_nonblocking(False)
            
            self.logger.info("✓ HID device opened, verifying communication...")
            
            # Verify real communication by requesting status
            if not self._verify_connection():
                self.logger.error("✗ Wiimote not responding! Make sure:")
                self.logger.error("  1. Wiimote has batteries")
                self.logger.error("  2. Press buttons 1+2 simultaneously on Wiimote")
                self.logger.error("  3. Wait for LEDs to stop flashing (paired)")
                self._cleanup()
                return False
            
            self.connected = True
            self.logger.info("✓ Connected to Wiimote successfully!")
            
            # Initialize Wiimote
            self._initialize()
            
            return True
        
        except Exception as e:
            self.logger.exception(f"Error connecting to Wiimote: {e}")
            self._cleanup()
            return False
    
    def _verify_connection(self) -> bool:
        """
        Verify that Wiimote is actually responding.
        
        Returns:
            True if Wiimote responds, False otherwise
        """
        try:
            self.logger.info("Waiting for Wiimote to send data...")
            self.logger.info("💡 Press AND HOLD a button (A, B, 1, 2, etc) on the Wiimote!")
            
            # Try to read any data to verify connection is active
            # Wiimote needs a button press to start sending data
            start_time = time.time()
            attempts = 0
            while time.time() - start_time < 8.0:  # 8 second timeout
                attempts += 1
                if attempts % 4 == 0:
                    self.logger.info(f"  Still waiting... ({int(8 - (time.time() - start_time))}s remaining)")
                
                # Note: timeout is POSITIONAL argument (in milliseconds), not keyword
                data = self.device.read(32, 500)  # 500ms per read
                if data and len(data) > 0:
                    # Convert to bytes if needed
                    if not isinstance(data, bytes):
                        data = bytes(data)
                    
                    self.logger.info(f"✓ Received {len(data)} bytes: {data[:15].hex()}")
                    self.logger.info("✓ Wiimote is responding!")
                    return True
            
            self.logger.warning("✗ No response from Wiimote within timeout")
            self.logger.warning("   Make sure you pressed AND HELD a button on the Wiimote!")
            return False
            
        except Exception as e:
            self.logger.error(f"Error verifying connection: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _initialize(self):
        """Initialize Wiimote after connection."""
        try:
            self.logger.info("Initializing Wiimote...")
            
            # Set LEDs (player 1)
            self.set_leds(led1=True)
            time.sleep(0.1)
            
            # Enable data reporting (mode 0x31: buttons + accel)
            # Skip IR for now as it requires complex calibration
            self.set_report_mode(0x31)
            time.sleep(0.1)
            
            # Optional: rumble briefly to confirm connection
            self.set_rumble(True)
            time.sleep(0.2)
            self.set_rumble(False)
            time.sleep(0.1)
            
            # Set non-blocking for continuous data reading
            if self.device:
                self.device.set_nonblocking(False)
            
            self.logger.info("✓ Wiimote initialized")
            
        except Exception as e:
            self.logger.exception(f"Error initializing Wiimote: {e}")
    
    def disconnect(self):
        """Disconnect from Wiimote."""
        if not self.connected:
            return
        
        self.logger.info("Disconnecting from Wiimote...")
        
        try:
            # Turn off LEDs and rumble
            self.set_leds(False, False, False, False)
            self.set_rumble(False)
            time.sleep(0.1)
        except:
            pass

        self.stop_read_loop()
        self._stop_reconnect_loop()
        
        self._cleanup()
        self.connected = False
        self.logger.info("Disconnected")
    
    def _cleanup(self):
        """Close HID device."""
        if self.device:
            try:
                self.device.close()
            except:
                pass
            self.device = None
    
    def read_data(self) -> Optional[bytes]:
        """
        Read data from Wiimote.
        
        Returns:
            Raw data bytes or None if no data available
        """
        if not self.connected or not self.device:
            self._ensure_reconnect()
            return None
        
        try:
            # Read HID report (max 23 bytes for Wiimote)
            # timeout is positional argument in milliseconds
            data = self.device.read(23, 100)  # 100ms timeout
            
            if data:
                return bytes(data)
            return None

        except Exception as e:
            # Ignore timeout errors (expected in non-blocking mode)
            if "timeout" not in str(e).lower():
                self.logger.debug(f"Error reading data: {e}")
                self._handle_disconnect(e)
            return None

    def start_read_loop(self, timeout_ms: int = 50, queue_size: Optional[int] = None) -> bool:
        """
        Start background read thread that enqueues raw HID events.

        Args:
            timeout_ms: Read timeout per loop (milliseconds)
            queue_size: Optional queue size override

        Returns:
            True if thread started or already running
        """
        if not self.connected or not self.device:
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
        """Stop background read thread and wait briefly for it to finish."""
        self._read_stop.set()
        if self._read_thread and self._read_thread.is_alive():
            self._read_thread.join(timeout=join_timeout)
        self._read_thread = None
        self._read_loop_wanted = False

    def get_event(self, timeout: float = 0.0) -> Optional[WiimoteHIDEvent]:
        """
        Get the next queued HID event.

        Args:
            timeout: Seconds to wait for an event (0 for non-blocking)

        Returns:
            WiimoteHIDEvent if available, else None
        """
        try:
            if timeout and timeout > 0:
                return self._event_queue.get(timeout=timeout)
            return self._event_queue.get_nowait()
        except queue.Empty:
            return None

    def drain_events(self, max_events: Optional[int] = None) -> List[WiimoteHIDEvent]:
        """Drain up to max_events from the queue (or all if None)."""
        drained: List[WiimoteHIDEvent] = []
        while True:
            if max_events is not None and len(drained) >= max_events:
                break
            try:
                drained.append(self._event_queue.get_nowait())
            except queue.Empty:
                break
        return drained

    def _read_loop(self):
        """Background loop reading from HID and enqueuing raw events."""
        self.logger.info("Starting HID read loop...")
        try:
            while not self._read_stop.is_set():
                if not self.connected or not self.device:
                    break

                try:
                    data = self.device.read(32, self._read_timeout_ms)
                    if data:
                        payload = bytes(data)
                        event = WiimoteHIDEvent(timestamp=time.time(), data=payload)
                        try:
                            self._event_queue.put_nowait(event)
                        except queue.Full:
                            # Drop oldest to keep latest data flowing
                            try:
                                _ = self._event_queue.get_nowait()
                                self._event_queue.put_nowait(event)
                            except queue.Empty:
                                pass
                except Exception as e:
                    # Treat read errors as disconnects, unless it's a benign timeout
                    if "timeout" not in str(e).lower():
                        self._last_read_error = e
                        self.logger.warning(f"HID read error, stopping read loop: {e}")
                        self._handle_disconnect(e)
                        break
        finally:
            self.logger.info("HID read loop stopped")
            if self._last_read_error:
                self._handle_disconnect(self._last_read_error)
    
    def send_command(self, command: bytes):
        """
        Send command to Wiimote via HID output report.
        
        Args:
            command: Command bytes to send (command ID + data)
        """
        if not self.connected or not self.device:
            self.logger.warning("Not connected, cannot send command")
            return
        
        try:
            # For Windows HID via hidapi on Wiimote:
            # Send command directly WITHOUT report ID prefix
            # Just: [command_id, data...]
            self.logger.debug(f"Sending: {command.hex()}")
            result = self.device.write(command)
            
            if result > 0:
                self.logger.debug(f"✓ Sent {result} bytes")
            else:
                self.logger.error(f"✗ Write failed: returned {result}")
        
        except Exception as e:
            self.logger.error(f"Error sending command: {e}")
    
    def set_leds(self, led1=False, led2=False, led3=False, led4=False):
        """Set Wiimote LED states."""
        leds = (
            (0x10 if led1 else 0) |
            (0x20 if led2 else 0) |
            (0x40 if led3 else 0) |
            (0x80 if led4 else 0)
        )
        # Add rumble bit to LED byte
        rumble_bit = 0x01 if self.rumble_state else 0x00
        self.send_command(bytes([0x11, leds | rumble_bit]))
    
    def set_rumble(self, enable: bool):
        """Enable or disable rumble."""
        self.rumble_state = enable
        # Use player status report to set rumble
        rumble_bit = 0x01 if enable else 0x00
        self.send_command(bytes([0x11, 0x10 | rumble_bit]))  # LED 1 + rumble bit
    
    def set_report_mode(self, mode: int, continuous: bool = True):
        """
        Set data reporting mode.
        
        Args:
            mode: Report mode (0x30-0x3f)
            continuous: Continuous reporting if True
        """
        flags = 0x04 if continuous else 0x00
        rumble_bit = 0x01 if self.rumble_state else 0x00
        self.send_command(bytes([0x12, flags | rumble_bit, mode]))
    
    def enable_ir(self, enable: bool):
        """Enable or disable IR camera."""
        # Enable IR camera (report 0x13)
        self.send_command(bytes([0x13, 0x04 if enable else 0x00]))
        
        if enable:
            # Enable IR camera 2 (report 0x1a)
            self.send_command(bytes([0x1a, 0x04]))
            time.sleep(0.05)
            
            # Write to registers to configure IR camera
            # (simplified initialization)
            self._write_register(0x04b00030, bytes([0x08]))
            time.sleep(0.05)
    
    def _write_register(self, address: int, data: bytes):
        """Write to Wiimote register/memory."""
        # Address is 4 bytes in little-endian for Wiimote memory operations
        addr_bytes = address.to_bytes(4, byteorder='little')
        size = len(data).to_bytes(1, byteorder='big')
        
        # Pad data to 16 bytes
        padded_data = data + bytes(16 - len(data))
        
        command = bytes([0x16]) + addr_bytes + size + padded_data
        self.send_command(command)
    
    def get_battery_level(self) -> int:
        """
        Request battery level.
        
        Returns:
            Battery percentage (0-100)
        """
        # Request status report
        self.send_command(bytes([0x15, 0x00]))
        
        # Battery level will be in next status report (0x20)
        # For now, return cached value or 100
        return 100  # Placeholder
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

    def _handle_disconnect(self, error: Optional[Exception] = None):
        if not self.connected and self.device is None:
            return

        if error:
            self.logger.warning(f"Wiimote disconnected: {error}")
        else:
            self.logger.warning("Wiimote disconnected")

        self.stop_read_loop()
        self._cleanup()
        self.connected = False
        self._ensure_reconnect()

    def _ensure_reconnect(self):
        if not self.auto_reconnect:
            return
        if self.connected:
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
        delay = max(0.1, self._reconnect_initial_delay)
        while not self._reconnect_stop.is_set():
            if self.connected:
                return

            self.logger.info(f"Reconnecting in {delay:.2f}s...")
            time.sleep(delay)
            if self._reconnect_stop.is_set():
                return

            if self.connect(timeout=5):
                if self._read_loop_wanted:
                    self.start_read_loop(timeout_ms=self._read_timeout_ms)
                return

            delay = min(self._reconnect_max_delay, delay * self._reconnect_backoff)
            if self._reconnect_jitter > 0:
                delay = max(0.1, delay + (self._reconnect_jitter * (0.5 - time.time() % 1)))
