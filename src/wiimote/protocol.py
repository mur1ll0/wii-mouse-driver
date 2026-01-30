"""Wiimote HID protocol parsing."""

import logging
from typing import Dict, List, Optional
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


@dataclass
class MotionPlusData:
    """MotionPlus (gyro) data."""
    yaw: int
    pitch: int
    roll: int
    yaw_fast: bool
    pitch_fast: bool
    roll_fast: bool
    extension_connected: bool


@dataclass
class NunchukButtons:
    """Nunchuk button states."""
    C: bool = False
    Z: bool = False


@dataclass
class NunchukData:
    """Nunchuk data (stick + accel + buttons)."""
    stick_x: int
    stick_y: int
    accel_x: int
    accel_y: int
    accel_z: int
    buttons: NunchukButtons


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
        
        # Expand to 10-bit by adding LSBs from button bytes.
        # Byte0 bits 5-6 hold X<1:0>. Byte1 bit5 holds Y<1>, bit6 holds Z<1>.
        if len(data) > 1:
            x = (x << 2) | ((data[0] >> 5) & 0x03)
            y = (y << 1) | ((data[1] >> 5) & 0x01)
            z = (z << 1) | ((data[1] >> 6) & 0x01)
        else:
            x = x << 2
            y = y << 1
            z = z << 1
        
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

    @staticmethod
    def parse_motionplus(data: bytes, offset: int = 0) -> Optional[MotionPlusData]:
        """
        Parse MotionPlus (gyro) data.

        Args:
            data: Raw data bytes containing MotionPlus extension data
            offset: Byte offset where MotionPlus data starts

        Returns:
            MotionPlusData or None
        """
        if len(data) < offset + 6:
            return None

        b0 = data[offset]
        b1 = data[offset + 1]
        b2 = data[offset + 2]
        b3 = data[offset + 3]
        b4 = data[offset + 4]
        b5 = data[offset + 5]

        yaw = b0 | ((b3 & 0xFC) << 6)
        roll = b1 | ((b4 & 0xFC) << 6)
        pitch = b2 | ((b5 & 0xFC) << 6)

        yaw_fast = (b3 & 0x02) == 0
        roll_fast = (b4 & 0x02) == 0
        pitch_fast = (b5 & 0x02) == 0
        extension_connected = (b5 & 0x01) == 0

        return MotionPlusData(
            yaw=yaw,
            pitch=pitch,
            roll=roll,
            yaw_fast=yaw_fast,
            pitch_fast=pitch_fast,
            roll_fast=roll_fast,
            extension_connected=extension_connected,
        )

    @staticmethod
    def parse_nunchuk(data: bytes, offset: int = 0) -> Optional[NunchukData]:
        """
        Parse Nunchuk data.

        Args:
            data: Raw data bytes containing Nunchuk extension data
            offset: Byte offset where Nunchuk data starts

        Returns:
            NunchukData or None
        """
        if len(data) < offset + 6:
            return None

        stick_x = data[offset]
        stick_y = data[offset + 1]
        ax_hi = data[offset + 2]
        ay_hi = data[offset + 3]
        az_hi = data[offset + 4]
        btns = data[offset + 5]

        accel_x = (ax_hi << 2) | ((btns >> 2) & 0x03)
        accel_y = (ay_hi << 2) | ((btns >> 4) & 0x03)
        accel_z = (az_hi << 2) | ((btns >> 6) & 0x03)

        buttons = NunchukButtons(
            C=(btns & 0x02) == 0,
            Z=(btns & 0x01) == 0,
        )

        return NunchukData(
            stick_x=stick_x,
            stick_y=stick_y,
            accel_x=accel_x,
            accel_y=accel_y,
            accel_z=accel_z,
            buttons=buttons,
        )
    
    @classmethod
    def parse_report(cls, data: bytes, extension: Optional[str] = None) -> Dict:
        """
        Parse complete data report.
        
        Args:
            data: Raw report data from Wiimote
            extension: Optional extension type to parse ("motionplus" or "nunchuk")
            
        Returns:
            Dictionary with parsed data
        """
        result = {
            'buttons': None,
            'accel': None,
            'ir_points': [],
            'battery': None,
            'report_type': None,
            'motionplus': None,
            'nunchuk': None,
            'events': [],
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
            if result['buttons'] is not None:
                result['events'].append({'type': 'buttons', 'data': result['buttons']})
            
            # Mode 0x31, 0x32, 0x33, 0x35, 0x36, 0x37: Include accelerometer
            if report_type in [0x31, 0x32, 0x33, 0x35, 0x36, 0x37]:
                result['accel'] = cls.parse_accelerometer(payload, offset=2)
                if result['accel'] is not None:
                    result['events'].append({'type': 'accel', 'data': result['accel']})
            
            # Mode 0x33, 0x36, 0x37: Include IR data
            if report_type == 0x33:
                result['ir_points'] = cls.parse_ir(payload, offset=5)
            elif report_type == 0x36:
                result['ir_points'] = cls.parse_ir(payload, offset=2)
            elif report_type == 0x37:
                result['ir_points'] = cls.parse_ir(payload, offset=5)
            if result['ir_points']:
                result['events'].append({'type': 'ir', 'data': result['ir_points']})

            # Extension data block (8 or 16 bytes depending on report type)
            if report_type in [0x32, 0x35, 0x36, 0x37]:
                # Calculate extension offset: buttons (2) + accel (3) = 5
                # Exception: 0x37 has IR data before extension
                if report_type == 0x37:
                    extension_offset = 15  # buttons(2) + accel(3) + IR(10)
                else:
                    extension_offset = 5  # buttons(2) + accel(3)
                
                extension_data = payload[extension_offset:]
                if extension == "motionplus":
                    result['motionplus'] = cls.parse_motionplus(extension_data, offset=0)
                    if result['motionplus'] is not None:
                        result['events'].append({'type': 'motionplus', 'data': result['motionplus']})
                elif extension == "nunchuk":
                    result['nunchuk'] = cls.parse_nunchuk(extension_data, offset=0)
                    if result['nunchuk'] is not None:
                        result['events'].append({'type': 'nunchuk', 'data': result['nunchuk']})
        
        elif report_type == 0x20:
            # Status report (includes battery)
            if len(data) >= 7:
                battery_raw = data[6]
                # Convert to percentage (approximate)
                result['battery'] = int((battery_raw / 255.0) * 100)
        
        return result
