"""Tests for Wiimote protocol parsing."""

import pytest
from src.wiimote.protocol import (
    WiimoteProtocol,
    ButtonState,
    AccelData,
    MotionPlusData,
    NunchukData,
)


class TestWiimoteProtocol:
    """Test protocol parsing functions."""
    
    def test_parse_buttons_all_off(self):
        """Test parsing when no buttons pressed."""
        data = bytes([0x00, 0x00])
        buttons = WiimoteProtocol.parse_buttons(data)
        
        assert buttons.A == False
        assert buttons.B == False
        assert buttons.One == False
        assert buttons.Two == False
    
    def test_parse_buttons_a_pressed(self):
        """Test parsing when A button pressed."""
        data = bytes([0x00, 0x08])  # A = bit 3 of byte 1
        buttons = WiimoteProtocol.parse_buttons(data)
        
        assert buttons.A == True
        assert buttons.B == False
    
    def test_parse_buttons_multiple(self):
        """Test parsing multiple buttons."""
        data = bytes([0x10, 0x0C])  # Plus, B, A
        buttons = WiimoteProtocol.parse_buttons(data)
        
        assert buttons.A == True
        assert buttons.B == True
        assert buttons.Plus == True
    
    def test_parse_accelerometer(self):
        """Test accelerometer parsing."""
        # Simulate centered position (~512 in 10-bit)
        data = bytes([0x00, 0x00, 0x80, 0x80, 0x80])  # Buttons + 3 accel bytes
        accel = WiimoteProtocol.parse_accelerometer(data, offset=2)
        
        assert accel is not None
        assert isinstance(accel.x, int)
        assert isinstance(accel.y, int)
        assert isinstance(accel.z, int)
    
    def test_parse_report_empty(self):
        """Test parsing empty report."""
        data = bytes()
        result = WiimoteProtocol.parse_report(data)
        
        assert result['buttons'] is None
        assert result['accel'] is None
        assert result['ir_points'] == []

    def test_parse_motionplus(self):
        """Test MotionPlus parsing."""
        data = bytes([0x10, 0x20, 0x30, 0xFC, 0xFC, 0xFC])
        motion = WiimoteProtocol.parse_motionplus(data)

        assert motion is not None
        assert isinstance(motion, MotionPlusData)
        assert motion.yaw == 0x3F10
        assert motion.roll == 0x3F20
        assert motion.pitch == 0x3F30
        assert motion.extension_connected == True

    def test_parse_nunchuk(self):
        """Test Nunchuk parsing."""
        data = bytes([0x80, 0x90, 0x20, 0x30, 0x40, 0xD9])
        nunchuk = WiimoteProtocol.parse_nunchuk(data)

        assert nunchuk is not None
        assert isinstance(nunchuk, NunchukData)
        assert nunchuk.stick_x == 0x80
        assert nunchuk.stick_y == 0x90
        assert nunchuk.accel_x == 0x82
        assert nunchuk.accel_y == 0xC1
        assert nunchuk.accel_z == 0x103
        assert nunchuk.buttons.C == True
        assert nunchuk.buttons.Z == False

    def test_parse_report_with_extension(self):
        """Test report parsing with Nunchuk extension."""
        payload = bytes([0x00, 0x00, 0x80, 0x80, 0x80]) + bytes([0x80, 0x90, 0x20, 0x30, 0x40, 0xD9, 0x00, 0x00])
        data = bytes([0xA1, 0x32]) + payload
        result = WiimoteProtocol.parse_report(data, extension="nunchuk")

        assert result['buttons'] is not None
        assert result['accel'] is not None
        assert result['nunchuk'] is not None

    def test_parse_ir_points(self):
        """Test IR point parsing with a valid point."""
        # Build IR payload: one valid point at index 0
        # x_lo=0x34, y_lo=0x12, x_hi=2, y_hi=1, size=0x0A
        packed = (2 << 4) | (1 << 6) | 0x0A
        ir_payload = bytes([0x34, 0x12, packed]) + bytes([0xFF, 0xFF, 0xF0] * 3)
        data = bytes([0x00] * 5) + ir_payload

        points = WiimoteProtocol.parse_ir(data, offset=5)

        assert len(points) == 1
        assert points[0].x == 0x234
        assert points[0].y == 0x112
        assert points[0].size == 0x0A

    def test_parse_status_report_battery(self):
        """Test battery parsing in status report (0x20)."""
        data = bytes([0xA1, 0x20, 0x00, 0x00, 0x00, 0x00, 0x80])
        result = WiimoteProtocol.parse_report(data)

        assert result['battery'] == 50


if __name__ == '__main__':
    pytest.main([__file__])
