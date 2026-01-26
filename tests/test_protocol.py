"""Tests for Wiimote protocol parsing."""

import pytest
from wiimote.protocol import WiimoteProtocol, ButtonState, AccelData


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


if __name__ == '__main__':
    pytest.main([__file__])
