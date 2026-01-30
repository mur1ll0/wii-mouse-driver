"""Configuration manager for Wii Mouse Driver."""

import configparser
import os
from typing import Any, Dict, List


class Config:
    """Manages application configuration."""
    
    def __init__(self, config_file: str = "config.ini"):
        """Initialize configuration manager."""
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.load()
    
    def load(self):
        """Load configuration from file."""
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
            self._ensure_defaults()
            self._ensure_profiles()
        else:
            self._create_default()

    def _default_sections(self) -> Dict[str, Dict[str, str]]:
        """Return default sections/keys for config migration."""
        return {
            'Profiles': {
                'active': 'default',
                'list': 'default'
            },
            'General': {
                'mode': 'MotionPlus',
                'extension': 'auto',
                'status_poll_interval': '2.5'
            },
            'Sensitivity': {
                'mouse_speed': '50',
                'smoothing': '5',
                'gyro_sensitivity': '30',
                'ir_sensitivity': '40',
                'accel_sensitivity': '25'
            },
            'Filters': {
                'gyro_lowpass_alpha': '0.25',
                'accel_lowpass_alpha': '0.25'
            },
            'Calibration': {
                'auto_on_connect': 'true',
                'samples': '60',
                'sample_delay_ms': '5',
                'gyro_neutral': '8000',
                'accel_neutral': '512'
            },
            'Reconnect': {
                'enabled': 'true',
                'initial_delay': '0.5',
                'max_delay': '3.0',
                'backoff_factor': '1.6',
                'jitter': '0.1'
            },
            'Fallback': {
                'enable_ir': 'false'
            },
            'ButtonMapping': {
                'A': 'left_click',
                'B': 'right_click',
                'One': 'toggle_control',
                'Two': 'center_mouse',
                'Plus': 'scroll_up',
                'Minus': 'scroll_down',
                'Home': 'none',
                'DPadUp': 'key_up',
                'DPadDown': 'key_down',
                'DPadLeft': 'key_left',
                'DPadRight': 'key_right'
            },
            'IR': {
                'enable_smoothing': 'true',
                'min_dots': '1',
                'calibration_width': '1024',
                'calibration_height': '768'
            },
            'MotionPlus': {
                'enable_drift_correction': 'true',
                'deadzone': '5',
                'acceleration_factor': '1.5'
            },
            'Hybrid': {
                'ir_weight': '0.7',
                'gyro_weight': '0.3',
                'auto_calibration': 'true'
            },
            'NunchukMapping': {
                'C': 'left_click',
                'Z': 'right_click',
                'StickUp': 'scroll_up',
                'StickDown': 'scroll_down'
            },
            'Nunchuk': {
                'deadzone': '15'
            }
        }
    
    def _create_default(self):
        """Create default configuration."""
        for section, values in self._default_sections().items():
            self.config[section] = dict(values)

        self._sync_profile_sections('default')
        
        self.save()

    def _ensure_profiles(self):
        """Ensure profiles exist and are valid."""
        if 'Profiles' not in self.config:
            self.config['Profiles'] = {
                'active': 'default',
                'list': 'default'
            }
            self._sync_profile_sections('default')
            self.save()
            return

        profiles = self._parse_profiles_list(self.config['Profiles'].get('list', 'default'))
        if not profiles:
            profiles = ['default']
        active = self.config['Profiles'].get('active', profiles[0])
        if active not in profiles:
            active = profiles[0]

        self.config['Profiles']['list'] = ', '.join(profiles)
        self.config['Profiles']['active'] = active
        self._sync_profile_sections(active)
        self.save()

    def _ensure_defaults(self):
        """Ensure required sections/keys exist (non-destructive)."""
        defaults = self._default_sections()
        changed = False

        for section, values in defaults.items():
            if section not in self.config:
                self.config[section] = dict(values)
                changed = True
                continue

            for key, value in values.items():
                if key not in self.config[section]:
                    self.config[section][key] = value
                    changed = True

        if changed:
            self._sync_profile_sections(self.get_active_profile())
            self.save()

    def _parse_profiles_list(self, raw: str) -> List[str]:
        return [item.strip() for item in raw.split(',') if item.strip()]

    def _profile_section_name(self, section: str, profile: str) -> str:
        return f"{section}:{profile}"

    def _sync_profile_sections(self, profile: str):
        """Create/update profile sections based on base sections when missing."""
        base_sections = [
            'General',
            'Sensitivity',
            'Filters',
            'Calibration',
            'Reconnect',
            'Fallback',
            'ButtonMapping',
            'IR',
            'MotionPlus',
            'Hybrid',
            'NunchukMapping',
            'Nunchuk'
        ]
        for section in base_sections:
            profile_section = self._profile_section_name(section, profile)
            if profile_section not in self.config:
                if section in self.config:
                    self.config[profile_section] = dict(self.config[section])
                else:
                    self.config[profile_section] = {}
            elif section in self.config:
                for key, value in self.config[section].items():
                    if key not in self.config[profile_section]:
                        self.config[profile_section][key] = value
    
    def save(self):
        """Save configuration to file."""
        with open(self.config_file, 'w') as f:
            self.config.write(f)
    
    def get(self, section: str, key: str, fallback: Any = None, use_profile: bool = True) -> str:
        """Get configuration value."""
        if use_profile:
            profile = self.get_active_profile()
            profile_section = self._profile_section_name(section, profile)
            if profile_section in self.config and key in self.config[profile_section]:
                return self.config.get(profile_section, key, fallback=fallback)
        if section in self.config:
            return self.config.get(section, key, fallback=fallback)
        return fallback
    
    def get_int(self, section: str, key: str, fallback: int = 0, use_profile: bool = True) -> int:
        """Get integer configuration value."""
        value = self.get(section, key, fallback=None, use_profile=use_profile)
        if value is None:
            return fallback
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback
    
    def get_float(self, section: str, key: str, fallback: float = 0.0, use_profile: bool = True) -> float:
        """Get float configuration value."""
        value = self.get(section, key, fallback=None, use_profile=use_profile)
        if value is None:
            return fallback
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback
    
    def get_bool(self, section: str, key: str, fallback: bool = False, use_profile: bool = True) -> bool:
        """Get boolean configuration value."""
        value = self.get(section, key, fallback=None, use_profile=use_profile)
        if value is None:
            return fallback
        return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}
    
    def set(self, section: str, key: str, value: Any, use_profile: bool = True):
        """Set configuration value."""
        if use_profile and self.has_profiles():
            profile = self.get_active_profile()
            profile_section = self._profile_section_name(section, profile)
            if profile_section not in self.config:
                self.config[profile_section] = {}
            self.config[profile_section][key] = str(value)
            return
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = str(value)
    
    def get_button_mapping(self) -> Dict[str, str]:
        """Get button mapping dictionary."""
        return self.get_section('ButtonMapping')

    def get_nunchuk_mapping(self) -> Dict[str, str]:
        """Get nunchuk mapping dictionary."""
        return self.get_section('NunchukMapping')

    def get_section(self, section: str, use_profile: bool = True) -> Dict[str, str]:
        """Get section with profile overrides applied."""
        merged: Dict[str, str] = {}
        if section in self.config:
            merged.update(self.config[section])
        if use_profile:
            profile = self.get_active_profile()
            profile_section = self._profile_section_name(section, profile)
            if profile_section in self.config:
                merged.update(self.config[profile_section])
        return merged
    
    def get_mode(self) -> str:
        """Get current operation mode."""
        return self.get('General', 'mode', 'Hybrid')
    
    def set_mode(self, mode: str):
        """Set operation mode."""
        self.set('General', 'mode', mode)
        self.save()

    def has_profiles(self) -> bool:
        return 'Profiles' in self.config

    def get_profiles(self) -> List[str]:
        if 'Profiles' not in self.config:
            return []
        return self._parse_profiles_list(self.config['Profiles'].get('list', ''))

    def get_active_profile(self) -> str:
        if 'Profiles' not in self.config:
            return 'default'
        return self.config['Profiles'].get('active', 'default')

    def set_active_profile(self, profile: str):
        """Set active profile and ensure sections exist."""
        profiles = self.get_profiles()
        if profile not in profiles:
            profiles.append(profile)
        self.config['Profiles']['list'] = ', '.join(profiles)
        self.config['Profiles']['active'] = profile
        self._sync_profile_sections(profile)
        self.save()

    def next_profile(self) -> str:
        """Cycle to next profile."""
        profiles = self.get_profiles()
        if not profiles:
            self.set_active_profile('default')
            return 'default'
        active = self.get_active_profile()
        try:
            index = profiles.index(active)
        except ValueError:
            index = 0
        next_profile = profiles[(index + 1) % len(profiles)]
        self.set_active_profile(next_profile)
        return next_profile

    def previous_profile(self) -> str:
        """Cycle to previous profile."""
        profiles = self.get_profiles()
        if not profiles:
            self.set_active_profile('default')
            return 'default'
        active = self.get_active_profile()
        try:
            index = profiles.index(active)
        except ValueError:
            index = 0
        prev_profile = profiles[(index - 1) % len(profiles)]
        self.set_active_profile(prev_profile)
        return prev_profile
