"""Mouse controller using Wiimote data."""

import pyautogui
import time
from typing import Optional, List, Callable
import logging
from src.wiimote.driver import WiimoteState
from src.config import Config
from src.mouse.filters import LowPassFilter
from src.mouse.mapping import ActionMapper


class MouseController:
    """Controls mouse using Wiimote input."""
    
    def __init__(self, config: Config, control_state_callback: Optional[Callable[[bool], None]] = None):
        """Initialize mouse controller."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # State
        self.enabled = False
        self.last_gyro_x = 0
        self.last_gyro_y = 0
        self.last_ir_x = 0
        self.last_ir_y = 0
        self._accel_baseline = None
        self._prev_accel = None
        
        # Sensor fusion state (for accel + gyro)
        self._pitch = 0.0  # Rotation around X-axis
        self._roll = 0.0   # Rotation around Y-axis
        self._prev_pitch = 0.0  # Previous pitch for delta calculation
        self._prev_roll = 0.0   # Previous roll for delta calculation
        self._last_time = None
        
        # Get screen size
        self.screen_width, self.screen_height = pyautogui.size()
        
        # Disable PyAutoGUI failsafe
        pyautogui.FAILSAFE = False
        
        # Load settings
        self.reload_settings()

        # Action mapper
        self.mapper = ActionMapper(
            config,
            toggle_control_callback=self.toggle_control,
            center_mouse_callback=self.center_cursor,
            profile_next_callback=self._profile_next,
            profile_prev_callback=self._profile_prev,
        )

        self._control_state_callback = control_state_callback
        
        # Previous button state
        self.prev_buttons = 0
        self._prev_nunchuk_buttons = 0
    
    def toggle_control(self):
        """Toggle mouse control on/off."""
        self.enabled = not self.enabled
        if not self.enabled:
            self.reset_motion_state()
        if self._control_state_callback:
            self._control_state_callback(self.enabled)
        self.logger.info(f"Mouse control: {'ENABLED' if self.enabled else 'DISABLED'}")
        return self.enabled

    def reset_motion_state(self):
        """Reset motion-related state to avoid drift when switching modes."""
        self._accel_baseline = None
        self._prev_accel = None
        self._pitch = 0.0
        self._roll = 0.0
        self._prev_pitch = 0.0
        self._prev_roll = 0.0
        self._last_time = None

    def reload_settings(self):
        """Reload config values for current profile."""
        self.mouse_speed = self.config.get_int('Sensitivity', 'mouse_speed', 50) / 50.0
        self.smoothing = self.config.get_int('Sensitivity', 'smoothing', 5)
        self.gyro_sensitivity = self.config.get_int('Sensitivity', 'gyro_sensitivity', 30) / 100.0
        self.accel_sensitivity = self.config.get_int('Sensitivity', 'accel_sensitivity', 25) / 100.0
        self.button_map = self.config.get_button_mapping()
        self.acceleration_factor = self.config.get_float('MotionPlus', 'acceleration_factor', 1.0)
        self.gyro_deadzone = self.config.get_int('MotionPlus', 'deadzone', 5)

        smoothing_alpha = 1.0 / (self.smoothing + 1) if self.smoothing >= 0 else 1.0
        accel_smoothing_alpha = 1.0 / (max(0, self.smoothing // 2) + 1)
        self._gyro_filter_x = LowPassFilter(smoothing_alpha)
        self._gyro_filter_y = LowPassFilter(smoothing_alpha)
        self._accel_filter_x = LowPassFilter(accel_smoothing_alpha)
        self._accel_filter_y = LowPassFilter(accel_smoothing_alpha)

        if hasattr(self, "mapper"):
            self.mapper.reload_mappings()
    
    def center_cursor(self):
        """Center cursor on screen."""
        pyautogui.moveTo(self.screen_width // 2, self.screen_height // 2)
        self.logger.info("Cursor centered")

    def _profile_next(self):
        profile = self.config.next_profile()
        self.reload_settings()
        self.logger.info(f"Profile changed to: {profile}")
        return profile

    def _profile_prev(self):
        profile = self.config.previous_profile()
        self.reload_settings()
        self.logger.info(f"Profile changed to: {profile}")
        return profile
    
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
        self.mapper.handle_action_for_key(button_key)
    
    def process_state(self, state: WiimoteState, buttons_pressed: Optional[list] = None):
        """Process Wiimote state and update mouse."""
        # Handle button presses (only on new press, not hold)
        new_presses = state.buttons & ~self.prev_buttons
        if new_presses:
            for button in self._button_names_from_mask(new_presses):
                self.handle_button_action(button)
        self.prev_buttons = state.buttons

        # Handle Nunchuk buttons/stick
        self._process_nunchuk(state)
        
        # Only move mouse if enabled
        if not self.enabled:
            self.reset_motion_state()
            return
        
        # Get operation mode (respect driver fallback when present)
        mode = getattr(state, 'effective_mode', None) or self.config.get_mode()
        
        if mode == 'MotionPlus':
            # MotionPlus mode = Accel + Gyro fusion
            self._process_accel_gyro_fusion(state)
        elif mode == 'IR':
            self._process_ir(state)
        elif mode == 'Hybrid':
            self._process_hybrid(state)
        elif mode == 'Accel':
            self._process_accel(state)

    def _process_nunchuk(self, state: WiimoteState):
        """Process Nunchuk buttons and stick for mapped actions."""
        if state.nunchuk_connected is not True:
            self._prev_nunchuk_buttons = 0
            return

        nunchuk_buttons = 0
        if state.nunchuk_c:
            nunchuk_buttons |= 0x01
        if state.nunchuk_z:
            nunchuk_buttons |= 0x02

        new_presses = nunchuk_buttons & ~self._prev_nunchuk_buttons
        if new_presses & 0x01:
            self.mapper.handle_action_for_key("C", is_nunchuk=True)
        if new_presses & 0x02:
            self.mapper.handle_action_for_key("Z", is_nunchuk=True)

        self._prev_nunchuk_buttons = nunchuk_buttons

        # Stick actions (simple threshold-based)
        if state.nunchuk_stick_x is None or state.nunchuk_stick_y is None:
            return

        center = 128
        deadzone = self.config.get_int('Nunchuk', 'deadzone', 15)
        stick_x = state.nunchuk_stick_x - center
        stick_y = state.nunchuk_stick_y - center

        if stick_y > deadzone:
            self.mapper.handle_action_for_key("StickUp", is_nunchuk=True)
        elif stick_y < -deadzone:
            self.mapper.handle_action_for_key("StickDown", is_nunchuk=True)
        if stick_x > deadzone:
            self.mapper.handle_action_for_key("StickRight", is_nunchuk=True)
        elif stick_x < -deadzone:
            self.mapper.handle_action_for_key("StickLeft", is_nunchuk=True)
    
    def _process_accel_gyro_fusion(self, state: WiimoteState):
        """Process accelerometer + gyroscope using complementary filter (sensor fusion).
        
        This is the industry-standard approach for motion controllers:
        - Accelerometer provides absolute orientation (tilt) using gravity as reference
        - Gyroscope provides fast rotation data but drifts over time
        - Complementary filter combines both: gyro for fast movements, accel for drift correction
        - Uses DELTA (change) in angles for mouse movement, not absolute angles
        """
        import math
        
        # Get current time for delta calculation
        current_time = time.time()
        if self._last_time is None:
            self._last_time = current_time
            # Initialize with current accelerometer angles
            accel_x = state.accel_x - 512
            accel_y = state.accel_y - 512
            accel_z = state.accel_z - 512
            self._pitch = math.atan2(accel_y, math.sqrt(accel_x**2 + accel_z**2))
            self._roll = math.atan2(-accel_x, math.sqrt(accel_y**2 + accel_z**2))
            self._prev_pitch = self._pitch
            self._prev_roll = self._roll
            return
        
        dt = current_time - self._last_time
        self._last_time = current_time
        
        # Prevent too large time steps
        if dt > 0.1 or dt <= 0:
            dt = 0.01
        
        # === ACCELEROMETER: Calculate tilt angles from gravity ===
        # Normalize accelerometer values (typical range ~400-650 with 512 neutral)
        accel_x = state.accel_x - 512
        accel_y = state.accel_y - 512
        accel_z = state.accel_z - 512
        
        # Calculate pitch and roll from accelerometer (angles in radians)
        # pitch = rotation around X-axis (forward/backward tilt)
        # roll = rotation around Y-axis (left/right tilt)
        accel_pitch = math.atan2(accel_y, math.sqrt(accel_x**2 + accel_z**2))
        accel_roll = math.atan2(-accel_x, math.sqrt(accel_y**2 + accel_z**2))
        
        # === GYROSCOPE: Integrate rotation rates ===
        # Gyro values: neutral ~8000, rotation changes this
        gyro_neutral = 8000
        gyro_x_rate = (state.gyro_x - gyro_neutral) * 0.00014  # Scale to rad/s
        gyro_y_rate = (state.gyro_y - gyro_neutral) * 0.00014

        # Gyro rate deadzone to prevent drift when stationary
        rate_deadzone = 0.002 + (self.smoothing * 0.0008)
        if abs(gyro_x_rate) < rate_deadzone:
            gyro_x_rate = 0.0
        if abs(gyro_y_rate) < rate_deadzone:
            gyro_y_rate = 0.0
        
        # Integrate gyro to get angle changes
        gyro_pitch_delta = gyro_y_rate * dt
        gyro_roll_delta = gyro_x_rate * dt
        
        # === COMPLEMENTARY FILTER: Combine both sensors ===
        # Lower alpha = trust accel more for stability and accuracy
        # Higher alpha = trust gyro more (can cause drift)
        # Set to 0.3 to heavily favor accelerometer for corrections
        alpha = 0.3
        
        # Update pitch and roll using complementary filter
        self._pitch = alpha * (self._pitch + gyro_pitch_delta) + (1 - alpha) * accel_pitch
        self._roll = alpha * (self._roll + gyro_roll_delta) + (1 - alpha) * accel_roll
        
        # === CALCULATE DELTAS (CHANGE IN ANGLES) ===
        # Only the CHANGE in angle moves the mouse, not the absolute angle
        # This prevents drift and continuous movement when controller is stationary
        delta_pitch = self._pitch - self._prev_pitch
        delta_roll = self._roll - self._prev_roll
        
        # Store current angles for next iteration
        self._prev_pitch = self._pitch
        self._prev_roll = self._roll
        
        # === APPLY DEADZONE TO DELTAS ===
        # Only move if there's actual change in orientation.
        # Smoothing acts as a larger threshold for response.
        base_deadzone = 0.0005  # radians
        smoothing_factor = max(0, self.smoothing) * 0.0006
        deadzone = base_deadzone + smoothing_factor
        
        if abs(delta_pitch) < deadzone:
            delta_pitch = 0
        if abs(delta_roll) < deadzone:
            delta_roll = 0
        
        # === CONVERT ANGLE DELTAS TO MOUSE MOVEMENT ===
        # Scale deltas to pixel movement
        # Use accel sensitivity weighted more since we trust accel in fusion
        accel_weight = 0.6
        gyro_weight = 0.4
        combined_sensitivity = (self.accel_sensitivity * accel_weight + self.gyro_sensitivity * gyro_weight)
        speed_multiplier = max(0.2, self.mouse_speed) ** 1.8 * 5.0
        scale = combined_sensitivity * speed_multiplier * 50000.0
        
        # Invert X axis so left rotation moves cursor left
        move_x = -delta_roll * scale
        move_y = delta_pitch * scale
        
        # Apply smoothing filters
        move_x = self._gyro_filter_x.apply(move_x)
        move_y = self._gyro_filter_y.apply(move_y)
        
        # Move mouse relatively (only if there's actual movement)
        if abs(move_x) > 0.5 or abs(move_y) > 0.5:
            try:
                pyautogui.moveRel(int(move_x), int(move_y))
            except:
                pass
    
    def _process_gyro(self, state: WiimoteState):
        """Process gyroscope data for mouse movement."""
        # Calculate delta from neutral position (assuming ~8000 is neutral)
        neutral = 8000
        deadzone = self.gyro_deadzone
        
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

        # Apply acceleration factor
        move_x *= self.acceleration_factor
        move_y *= self.acceleration_factor

        # Apply smoothing filters
        move_x = self._gyro_filter_x.apply(move_x)
        move_y = self._gyro_filter_y.apply(move_y)
        
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

    def _process_accel(self, state: WiimoteState):
        """Process accelerometer data for mouse movement."""
        base_deadzone = 1
        deadzone = max(1, int(base_deadzone + (self.smoothing * 2)))

        current = (state.accel_x, state.accel_y, state.accel_z)
        if self._accel_baseline is None:
            self._accel_baseline = current
            self._prev_accel = current
            return

        if self._prev_accel is None:
            self._prev_accel = current
            return

        # Use delta between samples to move only when controller moves
        delta_x = current[0] - self._prev_accel[0]
        delta_y = current[1] - self._prev_accel[1]

        self._prev_accel = current

        if abs(delta_x) < deadzone:
            delta_x = 0
        if abs(delta_y) < deadzone:
            delta_y = 0

        screen_scale = min(self.screen_width, self.screen_height) / 120.0
        speed_multiplier = max(0.2, self.mouse_speed) ** 1.8 * 1.2
        gain = max(0.1, self.accel_sensitivity) * speed_multiplier * 1.3
        move_x = delta_x * gain * screen_scale
        move_y = delta_y * gain * screen_scale

        move_x = self._accel_filter_x.apply(move_x)
        move_y = self._accel_filter_y.apply(move_y)

        if move_x != 0 or move_y != 0:
            try:
                pyautogui.moveRel(int(move_x), int(move_y))
            except Exception:
                pass

    def _button_names_from_mask(self, buttons: int) -> List[str]:
        """Convert button bitmask to list of button names."""
        pressed = []
        if buttons & 0x0001: pressed.append("TWO")
        if buttons & 0x0002: pressed.append("ONE")
        if buttons & 0x0004: pressed.append("B")
        if buttons & 0x0008: pressed.append("A")
        if buttons & 0x0010: pressed.append("MINUS")
        if buttons & 0x0020: pressed.append("HOME")
        if buttons & 0x0040: pressed.append("PLUS")
        if buttons & 0x0080: pressed.append("LEFT")
        if buttons & 0x0100: pressed.append("RIGHT")
        if buttons & 0x0200: pressed.append("DOWN")
        if buttons & 0x0400: pressed.append("UP")
        return pressed
