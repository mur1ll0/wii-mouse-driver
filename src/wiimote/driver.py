"""Wiimote driver for mouse control."""

import hid
import time
import logging
from typing import Optional, Tuple, List, Callable
from dataclasses import dataclass


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
    ir_x: int = 0
    ir_y: int = 0
    ir_visible: bool = False


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
    
    def __init__(self):
        """Initialize driver."""
        self.logger = logging.getLogger(__name__)
        self.device = None
        self.state = WiimoteState()
        self.running = False
        
        # Callbacks
        self.on_state_update: Optional[Callable[[WiimoteState], None]] = None
        self.on_button_press: Optional[Callable[[List[str]], None]] = None
    
    def find_and_connect(self) -> bool:
        """Find and connect to Wiimote."""
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
            
            # Use first interface found
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
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error connecting: {e}")
            return False
    
    def _initialize(self):
        """Initialize Wiimote settings."""
        # Set LED 1
        self.device.write(bytes([0x11, 0x10]))
        time.sleep(0.1)
        
        # Enable continuous reporting mode (0x31 = buttons + accel)
        self.device.write(bytes([0x12, 0x04, 0x31]))
        time.sleep(0.1)
        
        self.logger.info("Wiimote initialized!")
    
    def read_state(self) -> bool:
        """Read current Wiimote state."""
        if not self.device:
            return False
        
        try:
            data = self.device.read(32, 50)  # 50ms timeout
            
            if data and len(data) > 2:
                # Parse buttons (bytes 1-2)
                buttons = (data[1] << 8) | data[2]
                self.state.buttons = buttons
                
                # Parse accelerometer (bytes 3-5)
                if len(data) > 5:
                    self.state.accel_x = data[3]
                    self.state.accel_y = data[4]
                    self.state.accel_z = data[5]
                
                # Parse gyro data if available (bytes 6-8)
                if len(data) > 8:
                    self.state.gyro_x = (data[6] | ((data[9] & 0xFC) << 6)) if len(data) > 9 else data[6]
                    self.state.gyro_y = (data[7] | ((data[9] & 0x03) << 8)) if len(data) > 9 else data[7]
                    self.state.gyro_z = data[8]
                
                # Trigger callbacks
                if self.on_state_update:
                    self.on_state_update(self.state)
                
                # Check for button presses
                if buttons and self.on_button_press:
                    button_names = self.get_pressed_buttons(buttons)
                    if button_names:
                        self.on_button_press(button_names)
                
                return True
            
            return False
            
        except Exception as e:
            if "timeout" not in str(e).lower():
                self.logger.debug(f"Read error: {e}")
            return False
    
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
        if self.device:
            try:
                # Turn off LEDs
                self.device.write(bytes([0x11, 0x00]))
                time.sleep(0.1)
                self.device.close()
            except:
                pass
            
            self.device = None
        
        self.logger.info("Disconnected")
