"""Debug script to test gyroscope data reading."""
import sys
import time
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config
from src.wiimote.driver import WiimoteDriver
from logging_utils import configure_logging

# Configure logging with debug level
configure_logging(level=logging.DEBUG)

logger = logging.getLogger(__name__)

def main():
    """Test gyroscope reading."""
    logger.info("=== Gyro Debug Test ===")
    
    config = Config()
    driver = WiimoteDriver(config)
    
    logger.info("Attempting to connect...")
    if not driver.find_and_connect():
        logger.error("Failed to connect to Wiimote!")
        return
    
    logger.info("Connected! Starting read loop...")
    driver.start_read_loop(timeout_ms=10)
    
    try:
        for i in range(100):  # Read 100 samples
            if driver.read_state():
                state = driver.state
                
                # Print every 10 samples
                if i % 10 == 0:
                    logger.info(f"\n--- Sample {i} ---")
                    logger.info(f"Report ID: 0x{state.last_report_id:02X}" if state.last_report_id else "Report ID: None")
                    logger.info(f"Extension hex: {state.last_extension_hex or 'None'}")
                    logger.info(f"Gyro raw: X={state.gyro_raw_x}, Y={state.gyro_raw_y}, Z={state.gyro_raw_z}")
                    logger.info(f"Gyro filtered: X={state.gyro_x}, Y={state.gyro_y}, Z={state.gyro_z}")
                    logger.info(f"Accel: X={state.accel_x}, Y={state.accel_y}, Z={state.accel_z}")
                    logger.info(f"Buttons: {state.buttons}")
                    logger.info(f"MotionPlus connected: {state.motionplus_connected}")
                    logger.info(f"Extension connected: {state.extension_connected}")
            
            time.sleep(0.05)  # 20Hz
    
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    
    finally:
        driver.stop_read_loop()
        driver.disconnect()
        logger.info("Disconnected")

if __name__ == "__main__":
    main()
