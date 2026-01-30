"""Integration-style tests for WiimoteConnection using HID mocks."""

import pytest

from src.wiimote import connection as connection_module


class FakeDevice:
    """Simple fake HID device for connection tests."""

    def __init__(self, read_payloads):
        self._read_payloads = list(read_payloads)
        self.writes = []
        self.opened = False
        self.nonblocking = None
        self.path = None

    def open_path(self, path):
        self.opened = True
        self.path = path

    def set_nonblocking(self, value):
        self.nonblocking = value

    def read(self, size, timeout):
        if self._read_payloads:
            return self._read_payloads.pop(0)
        return []

    def write(self, data):
        self.writes.append(bytes(data))
        return len(data)

    def close(self):
        self.opened = False


class FakeHID:
    """Fake hid module with enumerate() and device() factory."""

    def __init__(self, devices, device_factory):
        self._devices = devices
        self._device_factory = device_factory

    def enumerate(self, vendor_id):
        return list(self._devices)

    def device(self):
        return self._device_factory()


def test_find_wiimote_prefers_interface_zero(monkeypatch):
    devices = [
        {
            'product_id': connection_module.WiimoteConnection.WIIMOTE_PRODUCT_ID,
            'interface_number': 1,
            'usage_page': 0x0005,
            'path': b'\\\\?\\hid#path1',
            'product_string': 'Nintendo RVL-CNT-01',
        },
        {
            'product_id': connection_module.WiimoteConnection.WIIMOTE_PRODUCT_ID,
            'interface_number': 0,
            'usage_page': 0x0001,
            'path': b'\\\\?\\hid#path0',
            'product_string': 'Nintendo RVL-CNT-01',
        },
    ]

    fake_hid = FakeHID(devices, lambda: FakeDevice([]))
    monkeypatch.setattr(connection_module, 'hid', fake_hid)
    monkeypatch.setattr(connection_module, 'HID_AVAILABLE', True)

    wiimote = connection_module.WiimoteConnection()
    result = wiimote.find_wiimote(timeout=1)

    assert result is not None
    assert result['path'] == b'\\\\?\\hid#path0'


def test_connect_success_with_mock_device(monkeypatch):
    device_info = {
        'product_id': connection_module.WiimoteConnection.WIIMOTE_PRODUCT_ID,
        'interface_number': 0,
        'usage_page': 0x0001,
        'path': b'\\\\?\\hid#path0',
        'product_string': 'Nintendo RVL-CNT-01',
    }

    fake_device = FakeDevice([
        [0xA1, 0x31, 0x00, 0x00, 0x00],  # _verify_connection
        [0xA1, 0x31, 0x00, 0x00, 0x00],  # read_data
    ])

    fake_hid = FakeHID([device_info], lambda: fake_device)
    monkeypatch.setattr(connection_module, 'hid', fake_hid)
    monkeypatch.setattr(connection_module, 'HID_AVAILABLE', True)
    monkeypatch.setattr(connection_module.time, 'sleep', lambda *_: None)

    wiimote = connection_module.WiimoteConnection()
    assert wiimote.connect(device_info=device_info, timeout=1) is True
    assert wiimote.connected is True
    assert fake_device.writes  # initialization should send commands

    data = wiimote.read_data()
    assert data == bytes([0xA1, 0x31, 0x00, 0x00, 0x00])

    wiimote.disconnect()