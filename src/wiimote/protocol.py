"""Wiimote HID protocol parsing."""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ButtonState:
    """Button states."""
    A: bool = False
    B: bool = False
    One: bool = False
    Two: bool = False
    Plus: bool = False
    Minus: bool = False
    Home: bool = False
    DPad_Left: bool = False
    DPad_Right: bool = False
    DPad_Up: bool = False
    DPad_Down: bool = False


@dataclass
class AccelData:
    """Accelerometer data."""
    x: int = 512
    y: int = 512
    z: int = 512


@dataclass
class IRPoint:
    """IR point data."""
    x: int
    y: int
    size: int = 0


class WiimoteProtocol:
    """Parser for Wiimote HID protocol."""
    
    def __init__(self):
        """Initialize protocol parser."""
        self.logger = logging.getLogger(__name__)
    
    @staticmethod
    def parse_buttons(data: bytes) -> ButtonState:
        """
        Parse button state from data.
        
        Args:
            data: Raw button bytes (first 2 bytes of report)
            
        Returns:
            ButtonState object
        """
        if len(data) < 2:
            return ButtonState()
        
        byte0 = data[0]
        byte1 = data[1]
        
        return ButtonState(
            DPad_Left=(byte0 & 0x01) != 0,
            DPad_Right=(byte0 & 0x02) != 0,
            DPad_Down=(byte0 & 0x04) != 0,
            DPad_Up=(byte0 & 0x08) != 0,
            Plus=(byte0 & 0x10) != 0,
            Two=(byte1 & 0x01) != 0,
            One=(byte1 & 0x02) != 0,
            B=(byte1 & 0x04) != 0,
            A=(byte1 & 0x08) != 0,
            Minus=(byte1 & 0x10) != 0,
            Home=(byte1 & 0x80) != 0,
        )
    
    @staticmethod
    def parse_accelerometer(data: bytes, offset: int = 2) -> Optional[AccelData]:
        """
        Parse accelerometer data.
        
        Args:
            data: Raw data bytes
            offset: Byte offset where accel data starts
            
        Returns:
            AccelData object or None
        """
        if len(data) < offset + 3:
            return None
        
        # Get 8-bit values
        x = data[offset]
        y = data[offset + 1]
        z = data[offset + 2]
        
        # Expand to 10-bit by adding LSBs from button byte if available
        # (For mode 0x33, LSBs are in button bits)
        # For now, just shift left by 2 (approximate 10-bit)
        x = (x << 2) | ((data[0] >> 5) & 0x03) if len(data) > 0 else (x << 2)
        y = (y << 2) | ((data[1] >> 4) & 0x02) if len(data) > 1 else (y << 2)
        z = (z << 2) | ((data[1] >> 5) & 0x02) if len(data) > 1 else (z << 2)
        
        return AccelData(x=x, y=y, z=z)
    
    @staticmethod
    def parse_ir(data: bytes, offset: int = 5) -> List[IRPoint]:
        """
        Parse IR camera data.
        
        Args:
            data: Raw data bytes
            offset: Byte offset where IR data starts
            
        Returns:
            List of IR points (up to 4)
        """
        ir_points = []
        
        if len(data) < offset + 10:
            return ir_points
        
        # IR data format (mode 0x33): 12 bytes for up to 4 points
        # Each point: X_lo, Y_lo, followed by packed X_hi|Y_hi|size
        
        for i in range(4):
            base = offset + i * 3
            
            if base + 2 >= len(data):
                break
            
            x_lo = data[base]
            y_lo = data[base + 1]
            packed = data[base + 2]
            
            # Extract high bits
            x_hi = (packed >> 4) & 0x03
            y_hi = (packed >> 6) & 0x03
            size = packed & 0x0F
            
            # Combine to 10-bit coordinates
            x = (x_hi << 8) | x_lo
            y = (y_hi << 8) | y_lo
            
            # Check if point is valid (0x3FF = not visible)
            if x != 0x3FF and y != 0x3FF:
                ir_points.append(IRPoint(x=x, y=y, size=size))
        
        return ir_points
    
    @classmethod
    def parse_report(cls, data: bytes) -> Dict:
        """
        Parse complete data report.
        
        Args:
            data: Raw report data from Wiimote
            
        Returns:
            Dictionary with parsed data
        """
        result = {
            'buttons': None,
            'accel': None,
            'ir_points': [],
            'battery': None,
            'report_type': None,
        }
        
        if not data or len(data) < 2:
            return result
        
        # First byte should be 0xa1 (input report)
        if data[0] != 0xa1:
            return result
        
        # Second byte is report type
        report_type = data[1]
        result['report_type'] = report_type
        
        # Parse based on report type
        if report_type >= 0x30 and report_type <= 0x3f:
            # Data reports
            payload = data[2:]
            
            # All data reports start with buttons
            result['buttons'] = cls.parse_buttons(payload)
            
            # Mode 0x31, 0x33, 0x35, 0x37: Include accelerometer
            if report_type in [0x31, 0x33, 0x35, 0x37]:
                result['accel'] = cls.parse_accelerometer(payload, offset=2)
            
            # Mode 0x33, 0x36, 0x37: Include IR data
            if report_type == 0x33:
                result['ir_points'] = cls.parse_ir(payload, offset=5)
            elif report_type == 0x36:
                result['ir_points'] = cls.parse_ir(payload, offset=2)
            elif report_type == 0x37:
                result['ir_points'] = cls.parse_ir(payload, offset=5)
        
        elif report_type == 0x20:
            # Status report (includes battery)
            if len(data) >= 7:
                battery_raw = data[6]
                # Convert to percentage (approximate)
                result['battery'] = int((battery_raw / 255.0) * 100)
        
        return result
