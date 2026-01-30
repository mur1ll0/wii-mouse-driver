"""Gesture detection and input action mapping."""

import logging
import math
from collections import deque
from typing import Dict, Optional, Callable, Iterable, List

import pyautogui


class GestureMapper:
    """Detects gestures from sensor data."""
    
    def __init__(self, config: Dict):
        """
        Initialize gesture mapper.
        
        Args:
            config: Configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # Gesture settings
        gesture_config = config.get('gestures', {})
        self.enabled = gesture_config.get('enabled', True)
        self.shake_threshold = gesture_config.get('shake_threshold', 400)
        self.tilt_threshold = gesture_config.get('tilt_threshold', 30)
        
        # History for gesture detection
        self.accel_history = deque(maxlen=10)
        self.last_gesture_time = 0
        self.gesture_cooldown = 0.5  # seconds
        
        if not self.enabled:
            self.logger.info("Gesture recognition disabled")
    
    def detect_gesture(self, sensor_data: Dict) -> Optional[str]:
        """
        Detect gesture from sensor data.
        
        Args:
            sensor_data: Processed sensor data
            
        Returns:
            Gesture name or None
        """
        if not self.enabled:
            return None
        
        accel_data = sensor_data.get('accel')
        if not accel_data:
            return None
        
        # Store history
        self.accel_history.append(accel_data)
        
        if len(self.accel_history) < 5:
            return None
        
        # Check for shake
        gesture = self._detect_shake()
        if gesture:
            return gesture
        
        # Check for tilt
        gesture = self._detect_tilt(accel_data)
        if gesture:
            return gesture
        
        return None


class ActionMapper:
    """Maps buttons/actions to mouse/keyboard/system operations."""

    def __init__(
        self,
        config: object,
        toggle_control_callback: Optional[Callable[[], bool]] = None,
        center_mouse_callback: Optional[Callable[[], None]] = None,
        profile_next_callback: Optional[Callable[[], str]] = None,
        profile_prev_callback: Optional[Callable[[], str]] = None,
    ):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self._toggle_control = toggle_control_callback
        self._center_mouse = center_mouse_callback
        self._profile_next = profile_next_callback
        self._profile_prev = profile_prev_callback
        self._drag_active = False

        # Disable PyAutoGUI failsafe for continuous control
        pyautogui.FAILSAFE = False

        self.reload_mappings()

    def reload_mappings(self):
        """Reload button mappings from config."""
        if hasattr(self.config, "get_button_mapping"):
            self.button_map = self._normalize_mapping(self.config.get_button_mapping())
        else:
            raw = self.config.get("ButtonMapping", {}) if isinstance(self.config, dict) else {}
            self.button_map = self._normalize_mapping(raw)

        if hasattr(self.config, "get_nunchuk_mapping"):
            self.nunchuk_map = self._normalize_mapping(self.config.get_nunchuk_mapping())
        else:
            raw = self.config.get("NunchukMapping", {}) if isinstance(self.config, dict) else {}
            self.nunchuk_map = self._normalize_mapping(raw)

        self.scroll_amount = 120
        if hasattr(self.config, "get_int"):
            self.scroll_amount = self.config.get_int("Sensitivity", "scroll_amount", 120)

    def get_action(self, key: str, is_nunchuk: bool = False) -> str:
        mapping = self.nunchuk_map if is_nunchuk else self.button_map
        normalized = self._normalize_mapping_key(key)
        return mapping.get(normalized, "none")

    @staticmethod
    def _normalize_mapping(mapping: Dict[str, str]) -> Dict[str, str]:
        return {ActionMapper._normalize_mapping_key(k): v for k, v in mapping.items()}

    @staticmethod
    def _normalize_mapping_key(key: str) -> str:
        if not key:
            return ""
        return str(key).strip().lower()

    def handle_action_for_key(self, key: str, is_nunchuk: bool = False) -> bool:
        action = self.get_action(key, is_nunchuk=is_nunchuk)
        return self.execute_action(action)

    def execute_action(self, action: str) -> bool:
        if not action or action == "none":
            return False

        try:
            if action == "left_click":
                pyautogui.click()
            elif action == "right_click":
                pyautogui.rightClick()
            elif action == "middle_click":
                pyautogui.middleClick()
            elif action == "double_click":
                pyautogui.doubleClick()
            elif action == "scroll_up":
                pyautogui.scroll(self.scroll_amount)
            elif action == "scroll_down":
                pyautogui.scroll(-self.scroll_amount)
            elif action == "drag_toggle":
                self._drag_active = not self._drag_active
                if self._drag_active:
                    pyautogui.mouseDown()
                else:
                    pyautogui.mouseUp()
            elif action == "toggle_control":
                if self._toggle_control:
                    self._toggle_control()
            elif action == "center_mouse":
                if self._center_mouse:
                    self._center_mouse()
            elif action == "profile_next":
                if self._profile_next:
                    self._profile_next()
            elif action == "profile_prev":
                if self._profile_prev:
                    self._profile_prev()
            elif action.startswith("key:") or action.startswith("key_"):
                key_str = action[4:]
                keys = self._parse_key_combo(key_str)
                if not keys:
                    return False
                if len(keys) == 1:
                    pyautogui.press(keys[0])
                else:
                    pyautogui.hotkey(*keys)
            else:
                self.logger.warning("Unknown action: %s", action)
                return False

            return True
        except Exception as e:
            self.logger.error("Error executing action %s: %s", action, e)
            return False

    def _parse_key_combo(self, key_str: str) -> List[str]:
        if not key_str:
            return []

        raw_keys = [k.strip() for k in key_str.split("+") if k.strip()]
        return [self._normalize_key(k) for k in raw_keys if self._normalize_key(k)]

    def _normalize_key(self, key: str) -> str:
        if not key:
            return ""
        key_upper = key.strip().upper()
        key_map = {
            "CTRL": "ctrl",
            "CONTROL": "ctrl",
            "ALT": "alt",
            "SHIFT": "shift",
            "WIN": "win",
            "CMD": "win",
            "DEL": "delete",
            "DELETE": "delete",
            "ESC": "esc",
            "ENTER": "enter",
            "RETURN": "enter",
            "PGUP": "pageup",
            "PGDOWN": "pagedown",
            "UP": "up",
            "DOWN": "down",
            "LEFT": "left",
            "RIGHT": "right",
            "SPACE": "space",
            "TAB": "tab",
            "BACKSPACE": "backspace",
            "CAPS": "capslock",
        }
        if key_upper in key_map:
            return key_map[key_upper]
        return key.strip().lower()
    
    def _detect_shake(self) -> Optional[str]:
        """
        Detect shake gesture.
        
        Returns:
            'shake' if detected, None otherwise
        """
        # Calculate acceleration variance
        magnitudes = [data['magnitude'] for data in self.accel_history]
        
        if len(magnitudes) < 5:
            return None
        
        # Check for sudden spike in magnitude
        recent = magnitudes[-3:]
        baseline = magnitudes[:-3]
        
        avg_baseline = sum(baseline) / len(baseline)
        max_recent = max(recent)
        
        delta = max_recent - avg_baseline
        
        if delta > self.shake_threshold:
            self.logger.debug(f"Shake detected (delta: {delta})")
            
            # Clear history to prevent re-triggering
            self.accel_history.clear()
            
            return 'shake'
        
        return None
    
    def _detect_tilt(self, accel_data: Dict) -> Optional[str]:
        """
        Detect tilt gesture.
        
        Args:
            accel_data: Accelerometer data with pitch/roll
            
        Returns:
            Tilt gesture name or None
        """
        roll = accel_data.get('roll', 0)
        
        # Check for significant tilt
        if roll > self.tilt_threshold:
            return 'tilt_right'
        elif roll < -self.tilt_threshold:
            return 'tilt_left'
        
        return None
