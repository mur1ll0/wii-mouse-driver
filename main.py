"""
Wii Mouse Driver - Main Entry Point
Use your Wiimote as a mouse!
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    """Main entry point for the application."""
    try:
        from src.ui.gui import WiimoteGUI
        
        # Create and run GUI
        app = WiimoteGUI()
        app.run()
        
    except ImportError as e:
        print(f"Erro ao importar módulos: {e}")
        print("\nCertifique-se de que todas as dependências estão instaladas:")
        print("  pip install -r requirements.txt")
        input("\nPressione ENTER para sair...")
        sys.exit(1)
    
    except Exception as e:
        print(f"Erro ao iniciar aplicação: {e}")
        import traceback
        traceback.print_exc()
        input("\nPressione ENTER para sair...")
        sys.exit(1)


if __name__ == "__main__":
    main()
