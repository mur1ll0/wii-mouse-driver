"""Gesture detection and mapping."""

import logging
import math
from collections import deque
from typing import Dict, Optional


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
