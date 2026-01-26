"""Configuration manager for Wii Mouse Driver."""

import configparser
import os
from pathlib import Path
from typing import Dict, Any


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
        else:
            self._create_default()
    
    def _create_default(self):
        """Create default configuration."""
        self.config['General'] = {
            'mode': 'Hybrid'
        }
        
        self.config['Sensitivity'] = {
            'mouse_speed': '50',
            'smoothing': '5',
            'gyro_sensitivity': '30',
            'ir_sensitivity': '40'
        }
        
        self.config['ButtonMapping'] = {
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
        }
        
        self.config['IR'] = {
            'enable_smoothing': 'true',
            'min_dots': '1',
            'calibration_width': '1024',
            'calibration_height': '768'
        }
        
        self.config['MotionPlus'] = {
            'enable_drift_correction': 'true',
            'deadzone': '5',
            'acceleration_factor': '1.5'
        }
        
        self.config['Hybrid'] = {
            'ir_weight': '0.7',
            'gyro_weight': '0.3',
            'auto_calibration': 'true'
        }
        
        self.save()
    
    def save(self):
        """Save configuration to file."""
        with open(self.config_file, 'w') as f:
            self.config.write(f)
    
    def get(self, section: str, key: str, fallback: Any = None) -> str:
        """Get configuration value."""
        return self.config.get(section, key, fallback=fallback)
    
    def get_int(self, section: str, key: str, fallback: int = 0) -> int:
        """Get integer configuration value."""
        return self.config.getint(section, key, fallback=fallback)
    
    def get_float(self, section: str, key: str, fallback: float = 0.0) -> float:
        """Get float configuration value."""
        return self.config.getfloat(section, key, fallback=fallback)
    
    def get_bool(self, section: str, key: str, fallback: bool = False) -> bool:
        """Get boolean configuration value."""
        return self.config.getboolean(section, key, fallback=fallback)
    
    def set(self, section: str, key: str, value: Any):
        """Set configuration value."""
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = str(value)
    
    def get_button_mapping(self) -> Dict[str, str]:
        """Get button mapping dictionary."""
        if 'ButtonMapping' in self.config:
            return dict(self.config['ButtonMapping'])
        return {}
    
    def get_mode(self) -> str:
        """Get current operation mode."""
        return self.get('General', 'mode', 'Hybrid')
    
    def set_mode(self, mode: str):
        """Set operation mode."""
        self.set('General', 'mode', mode)
        self.save()
