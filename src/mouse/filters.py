"""Movement filtering and smoothing."""

import logging
from collections import deque
from typing import Tuple, Optional


class MovementFilter:
    """Filter and smooth mouse movements."""
    
    def __init__(self, config: dict):
        """
        Initialize movement filter.
        
        Args:
            config: Configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        
        # Get smoothing settings
        smoothing_size = config.get('mouse', {}).get('smoothing', 5)
        self.position_history = deque(maxlen=max(1, smoothing_size))
        
        # Deadzone
        self.deadzone = config.get('mouse', {}).get('deadzone', 10)
    
    def filter_position(self, x: int, y: int) -> Tuple[int, int]:
        """
        Filter absolute position using moving average.
        
        Args:
            x: Target X coordinate
            y: Target Y coordinate
            
        Returns:
            Filtered (x, y) coordinates
        """
        # Add to history
        self.position_history.append((x, y))
        
        # Calculate average
        if len(self.position_history) == 1:
            return (x, y)
        
        avg_x = sum(pos[0] for pos in self.position_history) / len(self.position_history)
        avg_y = sum(pos[1] for pos in self.position_history) / len(self.position_history)
        
        return (int(avg_x), int(avg_y))
    
    def filter_delta(self, dx: int, dy: int) -> Tuple[int, int]:
        """
        Filter relative movement delta.
        
        Args:
            dx: X movement
            dy: Y movement
            
        Returns:
            Filtered (dx, dy)
        """
        # Apply deadzone
        if abs(dx) < self.deadzone:
            dx = 0
        if abs(dy) < self.deadzone:
            dy = 0
        
        return (dx, dy)


class LowPassFilter:
    """Simple low-pass (exponential moving average) filter."""

    def __init__(self, alpha: float):
        """
        Initialize low-pass filter.

        Args:
            alpha: Smoothing factor in range [0, 1].
        """
        self.alpha = self._clamp_alpha(alpha)
        self._has_value = False
        self._value = 0.0

    @staticmethod
    def _clamp_alpha(alpha: float) -> float:
        try:
            alpha = float(alpha)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, alpha))

    def reset(self, value: Optional[float] = None):
        """Reset filter state."""
        self._has_value = value is not None
        self._value = float(value) if value is not None else 0.0

    def apply(self, value: float) -> float:
        """
        Apply filter to a new sample.

        Args:
            value: New sample value.

        Returns:
            Filtered value.
        """
        value = float(value)
        if self.alpha <= 0.0:
            self._has_value = True
            self._value = value
            return value

        if not self._has_value:
            self._has_value = True
            self._value = value
            return value

        self._value = self.alpha * value + (1.0 - self.alpha) * self._value
        return self._value
