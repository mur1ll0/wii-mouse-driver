"""Auto-start GUI and log debug info updates without manual clicks."""
import sys
import time
from pathlib import Path

# Ensure project root on path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.ui.gui import WiimoteGUI
from logging_utils import configure_logging


class AutoStartGUI(WiimoteGUI):
    """GUI that auto-starts and logs useful state changes."""

    def __init__(self):
        super().__init__()

    def _toggle_motionplus(self):
        """Override to log mode changes."""
        enabled = not self.motionplus_enabled.get()
        mode_name = "Acelerômetro + Giroscópio" if enabled else "Apenas Acelerômetro"
        print(f"[MODE CHANGE] Switching to: {mode_name}")
        super()._toggle_motionplus()
        print(f"[MODE CHANGE] Mode switched successfully")
    
    def _on_driver_state_change(self, driver_state):
        """Override to log control state changes."""
        super()._on_driver_state_change(driver_state)
        if hasattr(self, '_last_control_enabled'):
            if self._last_control_enabled != driver_state.control_enabled:
                state = "ENABLED" if driver_state.control_enabled else "DISABLED"
                print(f"[CONTROL STATE] Mouse control: {state}")
        self._last_control_enabled = driver_state.control_enabled


def main():
    configure_logging(debug=False)
    app = AutoStartGUI()
    # Auto-start the driver after GUI is ready
    app.root.after(200, app._start)
    app.run()


if __name__ == "__main__":
    main()
