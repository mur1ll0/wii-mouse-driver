"""
Wii Mouse Driver - Main Entry Point
Use your Wiimote as a mouse!
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    """Main entry point for the application."""
    def _show_error(title: str, message: str):
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(title, message)
            root.destroy()
        except Exception:
            print(f"{title}: {message}")

    try:
        from src.ui.gui import WiimoteGUI
        
        # Create and run GUI
        app = WiimoteGUI()
        app.run()
        
    except ImportError as e:
        _show_error(
            "Erro de dependências",
            "Erro ao importar módulos:\n"
            f"{e}\n\n"
            "Certifique-se de que todas as dependências estão instaladas:\n"
            "pip install -r requirements.txt",
        )
        sys.exit(1)
    
    except Exception as e:
        import traceback

        traceback.print_exc()
        _show_error("Erro ao iniciar aplicação", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
