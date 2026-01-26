"""Sensor data processing and calibration."""

import logging
import math
from collections import deque
from typing import Dict, Optional, Tuple, List

from .protocol import WiimoteProtocol, AccelData, IRPoint


class SensorProcessor:
    """Process and filter sensor data from Wiimote."""
    
    def __init__(self, config: Dict):
        """
        Initialize sensor processor.
        
        Args:
            config: Configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.protocol = WiimoteProtocol()
        
        # Calibration data
        self.accel_calibration = {
            'x_zero': 512,
            'y_zero': 512,
            'z_zero': 512,
        }
        
        self.ir_calibration = {
            'x_offset': 0,
            'y_offset': 0,
            'x_scale': 1.0,
            'y_scale': 1.0,
        }
        
        # Load calibration from config
        self._load_calibration()
        
        # Filtering
        smoothing_size = config.get('mouse', {}).get('smoothing', 5)
        self.accel_filter = deque(maxlen=smoothing_size)
        self.ir_filter = deque(maxlen=smoothing_size)
        
        # Previous values for delta calculation
        self.prev_accel = None
        self.prev_ir_pos = None
    
    def _load_calibration(self):
        """Load calibration from config."""
        accel_cal = self.config.get('accelerometer', {}).get('calibration', {})
        self.accel_calibration.update(accel_cal)
        
        ir_cal = self.config.get('ir_pointer', {}).get('calibration', {})
        self.ir_calibration.update(ir_cal)
    
    def calibrate(self, wiimote):
        """
        Perform sensor calibration.
        
        Args:
            wiimote: WiimoteConnection instance
        """
        self.logger.info("Starting calibration...")
        
        # Collect samples for accelerometer calibration
        samples = []
        for _ in range(50):
            data = wiimote.read_data()
            if data:
                parsed = self.protocol.parse_report(data)
                if parsed.get('accel'):
                    samples.append(parsed['accel'])
        
        if samples:
            # Calculate average (resting position)
            avg_x = sum(s.x for s in samples) / len(samples)
            avg_y = sum(s.y for s in samples) / len(samples)
            avg_z = sum(s.z for s in samples) / len(samples)
            
            self.accel_calibration = {
                'x_zero': avg_x,
                'y_zero': avg_y,
                'z_zero': avg_z,
            }
            
            self.logger.info(f"Accelerometer calibrated: {self.accel_calibration}")
    
    def process(self, raw_data: bytes) -> Dict:
        """
        Process raw Wiimote data.
        
        Args:
            raw_data: Raw bytes from Wiimote
            
        Returns:
            Processed sensor data dictionary
        """
        # Parse raw data
        parsed = self.protocol.parse_report(raw_data)
        
        result = {
            'buttons': parsed.get('buttons'),
            'mouse_delta': (0, 0),
            'mouse_position': None,
            'ir_visible': False,
            'battery': parsed.get('battery', 100),
            'gestures': [],
        }
        
        # Process accelerometer
        if parsed.get('accel'):
            accel_data = self._process_accelerometer(parsed['accel'])
            result['accel'] = accel_data
            
            # Calculate mouse delta from accelerometer
            if self.config.get('accelerometer', {}).get('enabled', True):
                result['mouse_delta'] = self._accel_to_mouse_delta(accel_data)
        
        # Process IR
        if parsed.get('ir_points'):
            ir_pos = self._process_ir(parsed['ir_points'])
            if ir_pos:
                result['mouse_position'] = ir_pos
                result['ir_visible'] = True
        
        return result
    
    def _process_accelerometer(self, accel: AccelData) -> Dict:
        """
        Process accelerometer data.
        
        Args:
            accel: Raw accelerometer data
            
        Returns:
            Processed accelerometer dict
        """
        # Apply calibration
        x = accel.x - self.accel_calibration['x_zero']
        y = accel.y - self.accel_calibration['y_zero']
        z = accel.z - self.accel_calibration['z_zero']
        
        # Normalize to -1.0 to 1.0 range
        x_norm = x / 512.0
        y_norm = y / 512.0
        z_norm = z / 512.0
        
        # Calculate tilt angles
        pitch = math.atan2(y_norm, math.sqrt(x_norm**2 + z_norm**2))
        roll = math.atan2(x_norm, math.sqrt(y_norm**2 + z_norm**2))
        
        # Convert to degrees
        pitch_deg = math.degrees(pitch)
        roll_deg = math.degrees(roll)
        
        # Calculate magnitude (for shake detection)
        magnitude = math.sqrt(x**2 + y**2 + z**2)
        
        # Apply smoothing filter
        filtered_accel = (x, y, z)
        self.accel_filter.append(filtered_accel)
        
        if len(self.accel_filter) > 1:
            avg_x = sum(a[0] for a in self.accel_filter) / len(self.accel_filter)
            avg_y = sum(a[1] for a in self.accel_filter) / len(self.accel_filter)
            avg_z = sum(a[2] for a in self.accel_filter) / len(self.accel_filter)
            filtered_accel = (avg_x, avg_y, avg_z)
        
        return {
            'raw': (accel.x, accel.y, accel.z),
            'calibrated': (x, y, z),
            'filtered': filtered_accel,
            'normalized': (x_norm, y_norm, z_norm),
            'pitch': pitch_deg,
            'roll': roll_deg,
            'magnitude': magnitude,
        }
    
    def _accel_to_mouse_delta(self, accel_data: Dict) -> Tuple[int, int]:
        """
        Convert accelerometer data to mouse movement delta.
        
        Args:
            accel_data: Processed accelerometer data
            
        Returns:
            (dx, dy) mouse movement
        """
        x, y, z = accel_data['filtered']
        
        # Get sensitivity from config
        sensitivity = self.config.get('accelerometer', {}).get('motion_sensitivity', 2.0)
        
        # Apply sensitivity
        dx = int(x * sensitivity)
        dy = int(-y * sensitivity)  # Invert Y for natural movement
        
        # Apply deadzone
        deadzone = self.config.get('mouse', {}).get('deadzone', 10)
        if abs(dx) < deadzone:
            dx = 0
        if abs(dy) < deadzone:
            dy = 0
        
        return (dx, dy)
    
    def _process_ir(self, ir_points: List[IRPoint]) -> Optional[Tuple[int, int]]:
        """
        Process IR points to screen coordinates.
        
        Args:
            ir_points: List of IR points from camera
            
        Returns:
            (x, y) screen coordinates or None
        """
        if len(ir_points) < 2:
            return None
        
        # Use first two points for triangulation
        p1 = ir_points[0]
        p2 = ir_points[1]
        
        # Calculate center point between two IR dots
        center_x = (p1.x + p2.x) / 2.0
        center_y = (p1.y + p2.y) / 2.0
        
        # Normalize to 0.0-1.0 range (IR sensor is 1024x768)
        norm_x = center_x / 1024.0
        norm_y = center_y / 768.0
        
        # Apply calibration
        norm_x = (norm_x + self.ir_calibration['x_offset']) * self.ir_calibration['x_scale']
        norm_y = (norm_y + self.ir_calibration['y_offset']) * self.ir_calibration['y_scale']
        
        # Clamp to valid range
        norm_x = max(0.0, min(1.0, norm_x))
        norm_y = max(0.0, min(1.0, norm_y))
        
        # Convert to screen coordinates
        # These will be scaled to actual screen resolution by MouseController
        ir_pos = (norm_x, norm_y)
        
        # Apply smoothing filter
        self.ir_filter.append(ir_pos)
        
        if len(self.ir_filter) > 1:
            avg_x = sum(pos[0] for pos in self.ir_filter) / len(self.ir_filter)
            avg_y = sum(pos[1] for pos in self.ir_filter) / len(self.ir_filter)
            ir_pos = (avg_x, avg_y)
        
        return ir_pos
