"""Main entry point for Wii Mouse Driver."""

import sys
import argparse
import logging
import yaml
import time
from pathlib import Path

from wiimote.connection import WiimoteConnection
from wiimote.sensors import SensorProcessor
from mouse.controller import MouseController
from mouse.mapping import GestureMapper


def setup_logging(debug=False):
    """Configure logging system."""
    log_level = logging.DEBUG if debug else logging.INFO
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.FileHandler(log_dir / "wii_mouse.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )


def load_config(config_path="config.yaml"):
    """Load configuration from YAML file."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except FileNotFoundError:
        logging.warning(f"Config file {config_path} not found, using defaults")
        return {}
    except yaml.YAMLError as e:
        logging.error(f"Error parsing config file: {e}")
        return {}


def print_banner():
    """Print application banner."""
    banner = """
    ╔═══════════════════════════════════════════════╗
    ║         WII MOUSE DRIVER v0.1.0              ║
    ║   Control your mouse with Wii Remote!        ║
    ╚═══════════════════════════════════════════════╝
    """
    print(banner)


def print_instructions():
    """Print usage instructions."""
    instructions = """
    📋 INSTRUÇÕES:
    
    1. Certifique-se que o Bluetooth está ativo
    2. Pressione os botões 1 + 2 no Wiimote simultaneamente
    3. Aguarde a conexão (LEDs piscarão)
    4. Após conectar, aponte para o Sensor Bar
    
    🎮 CONTROLES PADRÃO:
    - Botão A: Clique esquerdo
    - Botão B: Clique direito
    - Plus (+): Scroll para cima
    - Minus (-): Scroll para baixo
    - Home: Clique do meio
    
    ⚙️  COMANDOS:
    - Ctrl+C: Sair do programa
    - Shake (sacudir): Clique duplo
    
    ═══════════════════════════════════════════════
    """
    print(instructions)


def run_console_mode(config):
    """Run driver in console mode."""
    logger = logging.getLogger(__name__)
    
    print_instructions()
    print("🔍 Procurando Wiimote...")
    print("   Pressione 1 + 2 no controle agora!\n")
    
    wiimote = None
    mouse_controller = None
    sensor_processor = None
    
    try:
        # Initialize Wiimote connection
        wiimote = WiimoteConnection()
        
        # Connect (blocking until found)
        if not wiimote.connect(timeout=30):
            print("❌ Falha ao conectar com Wiimote")
            print("   Verifique se o Bluetooth está ativo e tente novamente")
            return 1
        
        print("✅ Wiimote conectado com sucesso!")
        
        # Initialize sensor processor
        sensor_processor = SensorProcessor(config)
        
        # Initialize mouse controller
        mouse_controller = MouseController(config)
        
        # Calibrate sensors
        print("📐 Calibrando sensores...")
        time.sleep(0.5)
        sensor_processor.calibrate(wiimote)
        print("✅ Calibração concluída!")
        
        print("\n🎮 Driver ativo! Movimente o Wiimote para controlar o mouse.")
        print("   Pressione Ctrl+C para sair.\n")
        
        # Initialize gesture mapper
        gesture_mapper = GestureMapper(config)
        
        # Main loop
        frame_count = 0
        start_time = time.time()
        
        while True:
            # Get sensor data from Wiimote
            raw_data = wiimote.read_data()
            
            if raw_data is None:
                time.sleep(0.001)
                continue
            
            # Process sensor data
            processed_data = sensor_processor.process(raw_data)
            
            # Update mouse position
            mouse_controller.update(processed_data)
            
            # Check for gestures
            gesture = gesture_mapper.detect_gesture(processed_data)
            if gesture:
                mouse_controller.execute_gesture(gesture)
            
            # Handle button presses
            if processed_data.get('buttons'):
                mouse_controller.handle_buttons(processed_data['buttons'])
            
            # Update statistics (every second)
            frame_count += 1
            if frame_count % 100 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed
                battery = processed_data.get('battery', 0)
                
                logger.debug(
                    f"FPS: {fps:.1f} | Battery: {battery}% | "
                    f"IR: {processed_data.get('ir_visible', False)}"
                )
            
            # Small sleep to prevent CPU overuse
            time.sleep(0.001)
    
    except KeyboardInterrupt:
        print("\n\n⏸️  Interrompido pelo usuário")
        logger.info("User interrupted")
    
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        logger.exception("Unexpected error in main loop")
        return 1
    
    finally:
        # Cleanup
        print("🧹 Limpando recursos...")
        
        if mouse_controller:
            mouse_controller.cleanup()
        
        if wiimote:
            wiimote.disconnect()
        
        print("👋 Até logo!")
    
    return 0


def run_gui_mode(config):
    """Run driver with GUI."""
    try:
        from ui.gui import WiimoteGUI
        
        print("🖥️  Iniciando interface gráfica...")
        app = WiimoteGUI(config)
        return app.run()
    
    except ImportError as e:
        print(f"❌ Erro ao importar GUI: {e}")
        print("   Execute: pip install pillow pystray tkinter")
        return 1
    
    except Exception as e:
        logging.exception("Error in GUI mode")
        print(f"❌ Erro na interface gráfica: {e}")
        return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Wii Mouse Driver - Control your mouse with Wii Remote"
    )
    
    parser.add_argument(
        '--gui',
        action='store_true',
        help='Launch with graphical interface'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default='config.yaml',
        help='Path to configuration file (default: config.yaml)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='Wii Mouse Driver v0.1.0'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(debug=args.debug)
    
    # Print banner
    print_banner()
    
    # Load configuration
    config = load_config(args.config)
    
    # Override debug setting from args
    if args.debug:
        if 'advanced' not in config:
            config['advanced'] = {}
        config['advanced']['debug_mode'] = True
    
    # Run appropriate mode
    if args.gui:
        return run_gui_mode(config)
    else:
        return run_console_mode(config)


if __name__ == "__main__":
    sys.exit(main())
