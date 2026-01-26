"""Modern GUI for Wii Mouse Driver with real-time debug info."""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import sys
import logging
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import Config
from src.wiimote.driver import WiimoteDriver, WiimoteState
from src.mouse.controller_driver import MouseController

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class WiimoteGUI:
    """Modern GUI for Wiimote Mouse Driver."""
    
    def __init__(self):
        """Initialize GUI."""
        self.root = tk.Tk()
        self.root.title("Wii Mouse Driver")
        self.root.geometry("600x500")
        self.root.resizable(False, False)
        
        self.config = Config()
        self.running = False
        self.wiimote_thread = None
        
        # Wiimote driver and mouse controller
        self.driver = None
        self.mouse_controller = None
        
        # Debug info variables
        self.gyro_x = tk.StringVar(value="0")
        self.gyro_y = tk.StringVar(value="0")
        self.gyro_z = tk.StringVar(value="0")
        self.ir_x = tk.StringVar(value="0")
        self.ir_y = tk.StringVar(value="0")
        self.button_pressed = tk.StringVar(value="Nenhum")
        self.status_text = tk.StringVar(value="Desconectado")
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create GUI widgets."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title = ttk.Label(main_frame, text="🎮 Wii Mouse Driver", 
                         font=("Arial", 18, "bold"))
        title.grid(row=0, column=0, columnspan=2, pady=10)
        
        # Status
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        status_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        status_label = ttk.Label(status_frame, textvariable=self.status_text,
                                font=("Arial", 10, "bold"))
        status_label.pack()
        
        # Mode selection
        mode_frame = ttk.LabelFrame(main_frame, text="Modo de Operação", padding="10")
        mode_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.mode_var = tk.StringVar(value=self.config.get_mode())
        
        modes = [
            ("IR (Sensor Infravermelho)", "IR"),
            ("MotionPlus (Giroscópio)", "MotionPlus"),
            ("Híbrido (IR + Giroscópio)", "Hybrid")
        ]
        
        for i, (text, value) in enumerate(modes):
            rb = ttk.Radiobutton(mode_frame, text=text, variable=self.mode_var,
                                value=value, command=self._on_mode_change)
            rb.grid(row=i, column=0, sticky=tk.W, pady=2)
        
        # Sensitivity controls
        sens_frame = ttk.LabelFrame(main_frame, text="Sensibilidade", padding="10")
        sens_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Mouse speed
        ttk.Label(sens_frame, text="Velocidade do Mouse:").grid(row=0, column=0, sticky=tk.W)
        self.mouse_speed = tk.IntVar(value=self.config.get_int('Sensitivity', 'mouse_speed', 50))
        mouse_scale = ttk.Scale(sens_frame, from_=1, to=100, orient=tk.HORIZONTAL,
                               variable=self.mouse_speed, command=self._on_sensitivity_change)
        mouse_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Label(sens_frame, textvariable=self.mouse_speed).grid(row=0, column=2)
        
        # Smoothing
        ttk.Label(sens_frame, text="Suavização:").grid(row=1, column=0, sticky=tk.W)
        self.smoothing = tk.IntVar(value=self.config.get_int('Sensitivity', 'smoothing', 5))
        smooth_scale = ttk.Scale(sens_frame, from_=0, to=10, orient=tk.HORIZONTAL,
                                variable=self.smoothing, command=self._on_sensitivity_change)
        smooth_scale.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Label(sens_frame, textvariable=self.smoothing).grid(row=1, column=2)
        
        sens_frame.columnconfigure(1, weight=1)
        
        # Debug info
        debug_frame = ttk.LabelFrame(main_frame, text="Debug Info", padding="10")
        debug_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Gyro
        ttk.Label(debug_frame, text="Giroscópio:", font=("Arial", 9, "bold")).grid(
            row=0, column=0, sticky=tk.W)
        ttk.Label(debug_frame, text="X:", font=("Courier", 9)).grid(
            row=0, column=1, sticky=tk.W)
        ttk.Label(debug_frame, textvariable=self.gyro_x, font=("Courier", 9)).grid(
            row=0, column=2, sticky=tk.W)
        ttk.Label(debug_frame, text="Y:", font=("Courier", 9)).grid(
            row=0, column=3, sticky=tk.W, padx=(10, 0))
        ttk.Label(debug_frame, textvariable=self.gyro_y, font=("Courier", 9)).grid(
            row=0, column=4, sticky=tk.W)
        ttk.Label(debug_frame, text="Z:", font=("Courier", 9)).grid(
            row=0, column=5, sticky=tk.W, padx=(10, 0))
        ttk.Label(debug_frame, textvariable=self.gyro_z, font=("Courier", 9)).grid(
            row=0, column=6, sticky=tk.W)
        
        # IR
        ttk.Label(debug_frame, text="Sensor IR:", font=("Arial", 9, "bold")).grid(
            row=1, column=0, sticky=tk.W)
        ttk.Label(debug_frame, text="X:", font=("Courier", 9)).grid(
            row=1, column=1, sticky=tk.W)
        ttk.Label(debug_frame, textvariable=self.ir_x, font=("Courier", 9)).grid(
            row=1, column=2, sticky=tk.W)
        ttk.Label(debug_frame, text="Y:", font=("Courier", 9)).grid(
            row=1, column=3, sticky=tk.W, padx=(10, 0))
        ttk.Label(debug_frame, textvariable=self.ir_y, font=("Courier", 9)).grid(
            row=1, column=4, sticky=tk.W)
        
        # Buttons
        ttk.Label(debug_frame, text="Botão:", font=("Arial", 9, "bold")).grid(
            row=2, column=0, sticky=tk.W)
        ttk.Label(debug_frame, textvariable=self.button_pressed, 
                 font=("Courier", 9, "bold"), foreground="blue").grid(
            row=2, column=1, columnspan=6, sticky=tk.W)
        
        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)
        
        self.start_btn = ttk.Button(button_frame, text="▶ Iniciar",
                                    command=self._start, width=15)
        self.start_btn.grid(row=0, column=0, padx=5)
        
        self.stop_btn = ttk.Button(button_frame, text="⏹ Parar",
                                   command=self._stop, width=15, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=1, padx=5)
        
        ttk.Button(button_frame, text="⚙ Configurações",
                  command=self._open_settings, width=15).grid(row=0, column=2, padx=5)
        
        # Info label
        info_text = ("Pressione 1 no Wiimote para ativar/desativar controle\n"
                    "Pressione 2 no Wiimote para centralizar cursor")
        info_label = ttk.Label(main_frame, text=info_text, 
                              font=("Arial", 8), foreground="gray")
        info_label.grid(row=6, column=0, columnspan=2, pady=10)
    
    def _on_mode_change(self):
        """Handle mode change."""
        mode = self.mode_var.get()
        self.config.set_mode(mode)
        messagebox.showinfo("Modo Alterado", 
                          f"Modo alterado para: {mode}\nReinicie o driver para aplicar.")
    
    def _on_sensitivity_change(self, value=None):
        """Handle sensitivity changes."""
        self.config.set('Sensitivity', 'mouse_speed', self.mouse_speed.get())
        self.config.set('Sensitivity', 'smoothing', self.smoothing.get())
        self.config.save()
    
    def _start(self):
        """Start Wiimote driver."""
        self.running = True
        self.status_text.set("🔄 Conectando...")
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        
        # Start Wiimote thread
        self.wiimote_thread = threading.Thread(target=self._run_wiimote, daemon=True)
        self.wiimote_thread.start()
    
    def _stop(self):
        """Stop Wiimote driver."""
        self.running = False
        self.status_text.set("⏹ Parando...")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
    
    def _run_wiimote(self):
        """Run Wiimote driver in background thread."""
        try:
            # Create driver
            self.driver = WiimoteDriver()
            
            # Try to connect
            self.root.after(0, lambda: self.status_text.set("🔄 Procurando Wiimote..."))
            
            if not self.driver.find_and_connect():
                self.root.after(0, lambda: self.status_text.set("❌ Wiimote não encontrado!"))
                self.root.after(0, lambda: messagebox.showerror(
                    "Erro de Conexão",
                    "Não foi possível encontrar o Wiimote!\n\n"
                    "Certifique-se de que:\n"
                    "1. O Wiimote está pareado no Bluetooth\n"
                    "2. Pressione 1+2 para ativar\n"
                    "3. Os LEDs estão piscando"
                ))
                self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
                return
            
            # Connected!
            self.root.after(0, lambda: self.status_text.set("✅ Conectado"))
            
            # Create mouse controller
            self.mouse_controller = MouseController(self.config)
            
            # Setup callbacks
            self.driver.on_state_update = self._on_state_update
            self.driver.on_button_press = self._on_button_press
            
            # Main loop - read data continuously
            self.driver.running = True
            while self.running:
                self.driver.read_state()
                time.sleep(0.01)  # 100Hz polling
            
            # Cleanup
            self.driver.disconnect()
            self.root.after(0, lambda: self.status_text.set("⏹ Desconectado"))
            
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda: self.status_text.set(f"❌ Erro: {error_msg}"))
            self.root.after(0, lambda: messagebox.showerror("Erro", f"Erro ao executar driver:\n{error_msg}"))
            self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
    
    def _on_state_update(self, state: WiimoteState):
        """Handle Wiimote state update."""
        # Update debug display
        self.root.after(0, lambda: self.update_debug_info(
            gyro=(state.gyro_x, state.gyro_y, state.gyro_z),
            ir=(state.ir_x, state.ir_y),
            buttons=self.driver.get_pressed_buttons(state.buttons) if state.buttons else None
        ))
        
        # Process state for mouse control
        if self.mouse_controller:
            buttons_pressed = self.driver.get_pressed_buttons(state.buttons)
            self.mouse_controller.process_state(state, buttons_pressed)
    
    def _on_button_press(self, buttons: list):
        """Handle button press event."""
        # This is called by the driver when buttons change
        pass  # Already handled in _on_state_update
    
    def _open_settings(self):
        """Open settings dialog."""
        messagebox.showinfo("Configurações", 
                          "Editor de configurações em desenvolvimento.\n"
                          "Por enquanto, edite o arquivo config.ini manualmente.")
    
    def update_debug_info(self, gyro=None, ir=None, buttons=None):
        """Update debug information display."""
        if gyro:
            self.gyro_x.set(f"{gyro[0]:6d}")
            self.gyro_y.set(f"{gyro[1]:6d}")
            self.gyro_z.set(f"{gyro[2]:6d}")
        
        if ir:
            self.ir_x.set(f"{ir[0]:4d}")
            self.ir_y.set(f"{ir[1]:4d}")
        
        if buttons:
            if buttons:
                self.button_pressed.set(", ".join(buttons))
            else:
                self.button_pressed.set("Nenhum")
    
    def run(self):
        """Run the GUI."""
        self.root.mainloop()


def main():
    """Main entry point."""
    app = WiimoteGUI()
    app.run()


if __name__ == "__main__":
    main()
