"""Movement filtering and smoothing."""

import logging
from collections import deque
from typing import Tuple


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
