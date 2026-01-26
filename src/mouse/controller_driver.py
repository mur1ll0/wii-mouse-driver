"""Mouse controller using Wiimote data."""

import pyautogui
import time
from typing import Optional
import logging
from src.wiimote.driver import WiimoteState
from src.config import Config


class MouseController:
    """Controls mouse using Wiimote input."""
    
    def __init__(self, config: Config):
        """Initialize mouse controller."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # State
        self.enabled = False
        self.last_gyro_x = 0
        self.last_gyro_y = 0
        self.last_ir_x = 0
        self.last_ir_y = 0
        
        # Get screen size
        self.screen_width, self.screen_height = pyautogui.size()
        
        # Disable PyAutoGUI failsafe
        pyautogui.FAILSAFE = False
        
        # Load settings
        self.mouse_speed = self.config.get_int('Sensitivity', 'mouse_speed', 50) / 50.0
        self.smoothing = self.config.get_int('Sensitivity', 'smoothing', 5)
        self.gyro_sensitivity = self.config.get_int('Sensitivity', 'gyro_sensitivity', 30) / 100.0
        
        # Button mapping
        self.button_map = self.config.get_button_mapping()
        
        # Previous button state
        self.prev_buttons = 0
    
    def toggle_control(self):
        """Toggle mouse control on/off."""
        self.enabled = not self.enabled
        self.logger.info(f"Mouse control: {'ENABLED' if self.enabled else 'DISABLED'}")
        return self.enabled
    
    def center_cursor(self):
        """Center cursor on screen."""
        pyautogui.moveTo(self.screen_width // 2, self.screen_height // 2)
        self.logger.info("Cursor centered")
    
    def handle_button_action(self, button: str):
        """Execute action for button press."""
        # Map button name to config key
        button_map_names = {
            'A': 'A',
            'B': 'B',
            'ONE': 'One',
            'TWO': 'Two',
            'PLUS': 'Plus',
            'MINUS': 'Minus',
            'HOME': 'Home',
            'UP': 'DPadUp',
            'DOWN': 'DPadDown',
            'LEFT': 'DPadLeft',
            'RIGHT': 'DPadRight'
        }
        
        button_key = button_map_names.get(button, button)
        action = self.button_map.get(button_key, 'none')
        
        if action == 'none':
            return
        
        # Execute action
        try:
            if action == 'left_click':
                pyautogui.click()
            elif action == 'right_click':
                pyautogui.rightClick()
            elif action == 'middle_click':
                pyautogui.middleClick()
            elif action == 'scroll_up':
                pyautogui.scroll(120)
            elif action == 'scroll_down':
                pyautogui.scroll(-120)
            elif action == 'toggle_control':
                self.toggle_control()
            elif action == 'center_mouse':
                self.center_cursor()
            elif action.startswith('key_'):
                key = action[4:]
                pyautogui.press(key)
                
        except Exception as e:
            self.logger.error(f"Error executing action {action}: {e}")
    
    def process_state(self, state: WiimoteState, buttons_pressed: list):
        """Process Wiimote state and update mouse."""
        # Handle button presses (only on new press, not hold)
        if state.buttons != self.prev_buttons:
            new_presses = state.buttons & ~self.prev_buttons
            if new_presses:
                for button in buttons_pressed:
                    self.handle_button_action(button)
            self.prev_buttons = state.buttons
        
        # Only move mouse if enabled
        if not self.enabled:
            return
        
        # Get operation mode
        mode = self.config.get_mode()
        
        if mode == 'MotionPlus':
            self._process_gyro(state)
        elif mode == 'IR':
            self._process_ir(state)
        elif mode == 'Hybrid':
            self._process_hybrid(state)
    
    def _process_gyro(self, state: WiimoteState):
        """Process gyroscope data for mouse movement."""
        # Calculate delta from neutral position (assuming ~8000 is neutral)
        neutral = 8000
        deadzone = self.config.get_int('MotionPlus', 'deadzone', 5)
        
        delta_x = state.gyro_x - neutral
        delta_y = state.gyro_y - neutral
        
        # Apply deadzone
        if abs(delta_x) < deadzone * 100:
            delta_x = 0
        if abs(delta_y) < deadzone * 100:
            delta_y = 0
        
        # Apply sensitivity
        move_x = delta_x * self.gyro_sensitivity * self.mouse_speed * 0.01
        move_y = delta_y * self.gyro_sensitivity * self.mouse_speed * 0.01
        
        # Move mouse relatively
        if move_x != 0 or move_y != 0:
            try:
                pyautogui.moveRel(int(move_x), int(move_y))
            except:
                pass
    
    def _process_ir(self, state: WiimoteState):
        """Process IR sensor data for mouse movement."""
        if not state.ir_visible:
            return
        
        # Map IR coordinates to screen coordinates
        # IR typically ranges 0-1024, we need to map to screen size
        ir_width = self.config.get_int('IR', 'calibration_width', 1024)
        ir_height = self.config.get_int('IR', 'calibration_height', 768)
        
        screen_x = int((state.ir_x / ir_width) * self.screen_width)
        screen_y = int((state.ir_y / ir_height) * self.screen_height)
        
        # Apply smoothing
        if self.smoothing > 0:
            alpha = 1.0 / (self.smoothing + 1)
            screen_x = int(alpha * screen_x + (1 - alpha) * self.last_ir_x)
            screen_y = int(alpha * screen_y + (1 - alpha) * self.last_ir_y)
        
        self.last_ir_x = screen_x
        self.last_ir_y = screen_y
        
        try:
            pyautogui.moveTo(screen_x, screen_y)
        except:
            pass
    
    def _process_hybrid(self, state: WiimoteState):
        """Process hybrid mode (IR + Gyro)."""
        if state.ir_visible:
            self._process_ir(state)
        else:
            self._process_gyro(state)
