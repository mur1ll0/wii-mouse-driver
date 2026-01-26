"""Mouse control logic."""

import logging
import pyautogui
from typing import Dict, Tuple, Optional
from .filters import MovementFilter


class MouseController:
    """Controls computer mouse based on Wiimote input."""
    
    def __init__(self, config: Dict):
        """
        Initialize mouse controller.
        
        Args:
            config: Configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # Get screen dimensions
        screen_config = config.get('mouse', {})
        self.screen_width = screen_config.get('screen_width') or pyautogui.size()[0]
        self.screen_height = screen_config.get('screen_height') or pyautogui.size()[1]
        
        # Mouse settings
        self.sensitivity = screen_config.get('sensitivity', 1.5)
        self.acceleration = screen_config.get('acceleration', 1.2)
        
        # Button mappings
        self.button_map = config.get('buttons', {})
        
        # PyAutoGUI settings
        pyautogui.FAILSAFE = True  # Move to corner to abort
        pyautogui.PAUSE = 0.0  # No delay between commands
        
        # Movement filter
        self.movement_filter = MovementFilter(config)
        
        # Previous button states
        self.prev_buttons = {}
        
        # IR or accelerometer mode
        self.ir_enabled = config.get('ir_pointer', {}).get('enabled', True)
        self.accel_enabled = config.get('accelerometer', {}).get('enabled', True)
        
        self.logger.info(f"MouseController initialized ({self.screen_width}x{self.screen_height})")
    
    def update(self, sensor_data: Dict):
        """
        Update mouse position based on sensor data.
        
        Args:
            sensor_data: Processed sensor data from SensorProcessor
        """
        # Priority: IR pointer > Accelerometer
        if self.ir_enabled and sensor_data.get('ir_visible'):
            self._update_ir_position(sensor_data['mouse_position'])
        
        elif self.accel_enabled and sensor_data.get('mouse_delta'):
            self._update_accel_movement(sensor_data['mouse_delta'])
    
    def _update_ir_position(self, ir_position: Tuple[float, float]):
        """
        Update mouse position using IR pointer (absolute positioning).
        
        Args:
            ir_position: Normalized (0.0-1.0) screen position
        """
        if ir_position is None:
            return
        
        norm_x, norm_y = ir_position
        
        # Convert to screen coordinates
        target_x = int(norm_x * self.screen_width)
        target_y = int(norm_y * self.screen_height)
        
        # Apply filter
        filtered_x, filtered_y = self.movement_filter.filter_position(target_x, target_y)
        
        # Move mouse (duration=0 for instant)
        try:
            pyautogui.moveTo(filtered_x, filtered_y, duration=0)
        except Exception as e:
            self.logger.debug(f"Mouse move error: {e}")
    
    def _update_accel_movement(self, delta: Tuple[int, int]):
        """
        Update mouse position using accelerometer (relative movement).
        
        Args:
            delta: (dx, dy) movement delta
        """
        dx, dy = delta
        
        if dx == 0 and dy == 0:
            return
        
        # Apply sensitivity
        dx = int(dx * self.sensitivity)
        dy = int(dy * self.sensitivity)
        
        # Apply acceleration (amplify larger movements)
        if abs(dx) > 5:
            dx = int(dx * (abs(dx) / 5.0) ** (self.acceleration - 1.0))
        if abs(dy) > 5:
            dy = int(dy * (abs(dy) / 5.0) ** (self.acceleration - 1.0))
        
        # Move mouse relatively
        try:
            pyautogui.move(dx, dy, duration=0)
        except Exception as e:
            self.logger.debug(f"Mouse move error: {e}")
    
    def handle_buttons(self, buttons):
        """
        Handle button presses.
        
        Args:
            buttons: ButtonState object
        """
        if buttons is None:
            return
        
        # Check each button
        button_attrs = ['A', 'B', 'Plus', 'Minus', 'Home', 'One', 'Two',
                       'DPad_Up', 'DPad_Down', 'DPad_Left', 'DPad_Right']
        
        for button_name in button_attrs:
            pressed = getattr(buttons, button_name, False)
            was_pressed = self.prev_buttons.get(button_name, False)
            
            # Detect button press (edge trigger)
            if pressed and not was_pressed:
                self._handle_button_press(button_name)
            
            # Update state
            self.prev_buttons[button_name] = pressed
    
    def _handle_button_press(self, button_name: str):
        """
        Execute action for button press.
        
        Args:
            button_name: Name of pressed button
        """
        # Get action from config
        action = self.button_map.get(button_name)
        
        if action is None:
            return
        
        self.logger.debug(f"Button {button_name} -> {action}")
        
        try:
            # Execute action
            if action == 'left_click':
                pyautogui.click()
            
            elif action == 'right_click':
                pyautogui.click(button='right')
            
            elif action == 'middle_click':
                pyautogui.click(button='middle')
            
            elif action == 'double_click':
                pyautogui.doubleClick()
            
            elif action == 'scroll_up':
                pyautogui.scroll(3)
            
            elif action == 'scroll_down':
                pyautogui.scroll(-3)
            
            elif action == 'page_up':
                pyautogui.press('pageup')
            
            elif action == 'page_down':
                pyautogui.press('pagedown')
            
            else:
                self.logger.warning(f"Unknown action: {action}")
        
        except Exception as e:
            self.logger.error(f"Error executing action {action}: {e}")
    
    def execute_gesture(self, gesture: str):
        """
        Execute action for recognized gesture.
        
        Args:
            gesture: Gesture name
        """
        gestures = self.config.get('gestures', {})
        action = gestures.get(gesture)
        
        if action:
            self.logger.info(f"Gesture detected: {gesture} -> {action}")
            self._handle_button_press(action)  # Reuse button handler
    
    def cleanup(self):
        """Cleanup resources."""
        self.logger.info("MouseController cleanup")
