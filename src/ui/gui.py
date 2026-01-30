"""Modern GUI for Wii Mouse Driver with real-time debug info."""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import threading
import logging
import time
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import Config
from src.wiimote.driver import WiimoteDriver, WiimoteState
from src.mouse.controller_driver import MouseController
from logging_utils import configure_logging

# Configure logging
configure_logging()


class WiimoteGUI:
    """Modern GUI for Wiimote Mouse Driver."""
    
    def __init__(self):
        """Initialize GUI."""
        self.root = tk.Tk()
        self.root.title("Wii Mouse Driver")
        self.root.geometry("700x650")
        self.root.minsize(600, 550)
        self.root.resizable(True, True)
        
        self.config = Config()
        self.running = False
        self.wiimote_thread = None
        self.logger = logging.getLogger(__name__)
        
        # Wiimote driver and mouse controller
        self.driver = None
        self.mouse_controller = None
        
        # Debug info variables
        self.gyro_x = tk.StringVar(value="0")
        self.gyro_y = tk.StringVar(value="0")
        self.gyro_z = tk.StringVar(value="0")
        self.accel_x = tk.StringVar(value="0")
        self.accel_y = tk.StringVar(value="0")
        self.accel_z = tk.StringVar(value="0")
        self.ir_x = tk.StringVar(value="0")
        self.ir_y = tk.StringVar(value="0")
        self.button_pressed = tk.StringVar(value="Nenhum")
        self.auto_mode_text = tk.StringVar(value="Detectando...")
        self.status_text = tk.StringVar(value="Desconectado")
        self.battery_text = tk.StringVar(value="--%")
        self.peripherals_text = tk.StringVar(value="Desconhecido")
        self.motionplus_text = tk.StringVar(value="Desconhecido")
        self.motionplus_toggle_text = tk.StringVar(value="Desativar")
        self.motionplus_enabled = tk.BooleanVar(value=True)
        self.nunchuk_text = tk.StringVar(value="Desconhecido")
        self.profile_text = tk.StringVar(value=self.config.get_active_profile())
        self.control_text = tk.StringVar(value="Desativado")

        # UI update state (thread-safe)
        self._ui_state_lock = threading.Lock()
        self._ui_state = None
        
        self._create_widgets()
        # Start UI polling loop on main thread
        self.root.after(33, self._poll_ui_updates)
    
    def _create_widgets(self):
        """Create GUI widgets."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Title
        title = ttk.Label(main_frame, text="🎮 Wii Mouse Driver", 
                         font=("Arial", 18, "bold"))
        title.grid(row=0, column=0, columnspan=2, pady=10)
        
        # Status
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        status_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(status_frame, text="Conexão:", font=("Arial", 9, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(status_frame, textvariable=self.status_text,
                  font=("Arial", 9, "bold")).grid(row=0, column=1, sticky=tk.W)

        ttk.Label(status_frame, text="Bateria:", font=("Arial", 9, "bold")).grid(
            row=1, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(status_frame, textvariable=self.battery_text).grid(
            row=1, column=1, sticky=tk.W)

        ttk.Label(status_frame, text="Modo Automático:", font=("Arial", 9, "bold")).grid(
            row=2, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(status_frame, textvariable=self.auto_mode_text,
                  font=("Arial", 9, "bold"), foreground="blue").grid(
            row=2, column=1, sticky=tk.W)

        ttk.Label(status_frame, text="Periféricos:", font=("Arial", 9, "bold")).grid(
            row=3, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(status_frame, textvariable=self.peripherals_text).grid(
            row=3, column=1, sticky=tk.W)

        ttk.Label(status_frame, text="MotionPlus:", font=("Arial", 9, "bold")).grid(
            row=4, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(status_frame, textvariable=self.motionplus_text).grid(
            row=4, column=1, sticky=tk.W)
        self.motionplus_btn = ttk.Button(
            status_frame,
            textvariable=self.motionplus_toggle_text,
            command=self._toggle_motionplus,
            width=12,
        )
        self.motionplus_btn.grid(row=4, column=2, sticky=tk.W, padx=(8, 0))

        ttk.Label(status_frame, text="Nunchuk:", font=("Arial", 9, "bold")).grid(
            row=5, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(status_frame, textvariable=self.nunchuk_text).grid(
            row=5, column=1, sticky=tk.W)

        ttk.Label(status_frame, text="Controle:", font=("Arial", 9, "bold")).grid(
            row=6, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(status_frame, textvariable=self.control_text).grid(
            row=6, column=1, sticky=tk.W)

        status_frame.columnconfigure(1, weight=1)
        
        # Sensitivity controls
        sens_frame = ttk.LabelFrame(main_frame, text="Sensibilidade", padding="10")
        sens_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
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
        debug_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N), pady=5)
        debug_frame.columnconfigure(1, weight=1)
        
        # Gyro
        gyro_label = ttk.Label(debug_frame, text="Giroscópio:", font=("Arial", 9, "bold"))
        gyro_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        
        gyro_data_frame = ttk.Frame(debug_frame)
        gyro_data_frame.grid(row=0, column=1, columnspan=6, sticky=tk.W)
        ttk.Label(gyro_data_frame, text="X:", font=("Courier", 9)).pack(side=tk.LEFT)
        ttk.Label(gyro_data_frame, textvariable=self.gyro_x, font=("Courier", 9)).pack(side=tk.LEFT, padx=(2, 10))
        ttk.Label(gyro_data_frame, text="Y:", font=("Courier", 9)).pack(side=tk.LEFT)
        ttk.Label(gyro_data_frame, textvariable=self.gyro_y, font=("Courier", 9)).pack(side=tk.LEFT, padx=(2, 10))
        ttk.Label(gyro_data_frame, text="Z:", font=("Courier", 9)).pack(side=tk.LEFT)
        ttk.Label(gyro_data_frame, textvariable=self.gyro_z, font=("Courier", 9)).pack(side=tk.LEFT, padx=(2, 0))

        # Accel
        accel_label = ttk.Label(debug_frame, text="Acelerômetro:", font=("Arial", 9, "bold"))
        accel_label.grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        
        accel_data_frame = ttk.Frame(debug_frame)
        accel_data_frame.grid(row=1, column=1, columnspan=6, sticky=tk.W)
        ttk.Label(accel_data_frame, text="X:", font=("Courier", 9)).pack(side=tk.LEFT)
        ttk.Label(accel_data_frame, textvariable=self.accel_x, font=("Courier", 9)).pack(side=tk.LEFT, padx=(2, 10))
        ttk.Label(accel_data_frame, text="Y:", font=("Courier", 9)).pack(side=tk.LEFT)
        ttk.Label(accel_data_frame, textvariable=self.accel_y, font=("Courier", 9)).pack(side=tk.LEFT, padx=(2, 10))
        ttk.Label(accel_data_frame, text="Z:", font=("Courier", 9)).pack(side=tk.LEFT)
        ttk.Label(accel_data_frame, textvariable=self.accel_z, font=("Courier", 9)).pack(side=tk.LEFT, padx=(2, 0))
        
        # IR
        ir_label = ttk.Label(debug_frame, text="Sensor IR:", font=("Arial", 9, "bold"))
        ir_label.grid(row=2, column=0, sticky=tk.W, padx=(0, 10))
        
        ir_data_frame = ttk.Frame(debug_frame)
        ir_data_frame.grid(row=2, column=1, columnspan=6, sticky=tk.W)
        ttk.Label(ir_data_frame, text="X:", font=("Courier", 9)).pack(side=tk.LEFT)
        ttk.Label(ir_data_frame, textvariable=self.ir_x, font=("Courier", 9)).pack(side=tk.LEFT, padx=(2, 10))
        ttk.Label(ir_data_frame, text="Y:", font=("Courier", 9)).pack(side=tk.LEFT)
        ttk.Label(ir_data_frame, textvariable=self.ir_y, font=("Courier", 9)).pack(side=tk.LEFT, padx=(2, 0))
        
        # Buttons
        ttk.Label(debug_frame, text="Botão:", font=("Arial", 9, "bold")).grid(
            row=3, column=0, sticky=tk.W)
        ttk.Label(debug_frame, textvariable=self.button_pressed, 
                 font=("Courier", 9, "bold"), foreground="blue").grid(
            row=3, column=1, columnspan=6, sticky=tk.W)
        
        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20, sticky=(tk.W, tk.E))

        self.start_btn = ttk.Button(button_frame, text="▶ Iniciar",
                        command=self._start, width=15)
        self.start_btn.grid(row=0, column=0, padx=5, pady=3)

        self.stop_btn = ttk.Button(button_frame, text="⏹ Parar",
                       command=self._stop, width=15, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=1, padx=5, pady=3)

        ttk.Button(button_frame, text="📐 Calibrar",
              command=self._calibrate, width=15).grid(row=0, column=2, padx=5, pady=3)

        ttk.Button(button_frame, text="📶 Parear",
              command=self._open_pairing_assistant, width=15).grid(row=1, column=0, padx=5, pady=3)

        ttk.Button(button_frame, text="⚙ Configurações Avançadas",
              command=self._open_settings, width=25).grid(row=1, column=1, columnspan=2, padx=5, pady=3)
        
        # Info label
        info_text = ("Pressione 1 no Wiimote para ativar/desativar controle\n"
                    "Pressione 2 no Wiimote para centralizar cursor")
        info_label = ttk.Label(main_frame, text=info_text,
                      font=("Arial", 8), foreground="gray")
        info_label.grid(row=5, column=0, columnspan=2, pady=10)
    
    def _on_sensitivity_change(self, value=None):
        """Handle sensitivity changes."""
        self.config.set('Sensitivity', 'mouse_speed', self.mouse_speed.get())
        self.config.set('Sensitivity', 'smoothing', self.smoothing.get())
        self.config.save()
        if self.mouse_controller:
            self.mouse_controller.reload_settings()

    def _toggle_motionplus(self):
        """Enable/disable MotionPlus usage for testing auto mode."""
        if not self.driver or not self.running:
            messagebox.showwarning(
                "Aviso",
                "Por favor, inicie o driver primeiro antes de alterar o modo."
            )
            return
        
        enabled = not self.motionplus_enabled.get()
        self.motionplus_enabled.set(enabled)
        self.motionplus_toggle_text.set("Desativar" if enabled else "Ativar")
        
        # Preserve control enabled state
        was_control_enabled = self.mouse_controller.enabled if self.mouse_controller else False
        
        # Update driver mode
        if self.driver:
            self.driver.set_motionplus_enabled(enabled)
        
        # Reset motion state and restore control
        if self.mouse_controller:
            self.mouse_controller.reset_motion_state()
            # Restore control enabled state immediately
            self.mouse_controller.enabled = was_control_enabled
            if was_control_enabled:
                self.logger.info("Control state preserved during mode change")
        
        # Update mode display (not connection status)
        mode_name = "Acelerômetro + Giroscópio" if enabled else "Apenas Acelerômetro"
        self.auto_mode_text.set(mode_name)
        
        # Brief button disable to prevent rapid toggling
        if hasattr(self, "motionplus_btn"):
            self.motionplus_btn.config(state=tk.DISABLED)
            self.root.after(1000, lambda: self.motionplus_btn.config(state=tk.NORMAL))
    
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
            self.driver = WiimoteDriver(self.config)
            self.driver.on_driver_state_change = self._on_driver_state_change
            self.driver.set_motionplus_enabled(self.motionplus_enabled.get())
            
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
                self.root.after(0, self._maybe_open_pairing_assistant)
                self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
                return
            
            # Connected!
            self.root.after(0, lambda: self.status_text.set("✅ Conectado"))

            # Optional auto calibration
            if self.config.get_bool('Calibration', 'auto_on_connect', True):
                self.root.after(0, lambda: self.status_text.set("📐 Calibrando..."))
                self.driver.calibrate()
                self.root.after(0, lambda: self.status_text.set("✅ Conectado"))
            
            # Create mouse controller
            self.mouse_controller = MouseController(
                self.config,
                control_state_callback=self.driver.set_control_enabled,
            )
            
            # Setup callbacks
            self.driver.on_state_update = self._on_state_update
            self.driver.on_button_press = self._on_button_press

            # Start background read loop (event queue)
            self.driver.start_read_loop(timeout_ms=10)
            
            # Main loop - read data continuously
            self.driver.running = True
            while self.running:
                self.driver.read_state()
                time.sleep(0.01)  # 100Hz polling
            
            # Cleanup
            self.driver.stop_read_loop()
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
        # Only store state here; UI update happens on main thread in _poll_ui_updates
        with self._ui_state_lock:
            self._ui_state = state
        
        # Process state for mouse control
        if self.mouse_controller:
            self.mouse_controller.process_state(state)
    
    def _on_button_press(self, buttons: list):
        """Handle button press event."""
        # This is called by the driver when buttons change
        pass  # Already handled in _on_state_update

    def _on_driver_state_change(self, driver_state):
        """Handle driver state updates (connect/reconnect)."""
        if driver_state.reconnecting:
            self.root.after(0, lambda: self.status_text.set("🔄 Reconectando..."))
            return
        if driver_state.connected:
            self.root.after(0, lambda: self.status_text.set("✅ Conectado"))
        else:
            self.root.after(0, lambda: self.status_text.set("❌ Desconectado"))
        self.root.after(0, lambda: self._update_driver_fields(driver_state))
    
    def _open_settings(self):
        """Open advanced settings dialog."""
        self._open_advanced_settings()

    def _open_advanced_settings(self):
        """Open advanced settings window."""
        window = tk.Toplevel(self.root)
        window.title("Configurações Avançadas")
        window.geometry("600x700")
        window.resizable(True, True)

        # Create notebook (tabs)
        notebook = ttk.Notebook(window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab 1: Sensibilidades
        sensitivity_tab = ttk.Frame(notebook, padding="10")
        notebook.add(sensitivity_tab, text="Sensibilidades")

        ttk.Label(sensitivity_tab, text="Sensibilidades dos Sensores", 
                 font=("Arial", 11, "bold")).grid(row=0, column=0, columnspan=3, pady=(0, 10), sticky=tk.W)

        # Acelerômetro
        ttk.Label(sensitivity_tab, text="Acelerômetro:").grid(row=1, column=0, sticky=tk.W, pady=5)
        accel_sens = tk.IntVar(value=self.config.get_int('Sensitivity', 'accel_sensitivity', 25))
        ttk.Scale(sensitivity_tab, from_=1, to=100, orient=tk.HORIZONTAL, variable=accel_sens).grid(
            row=1, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Label(sensitivity_tab, textvariable=accel_sens).grid(row=1, column=2)

        # Giroscópio
        ttk.Label(sensitivity_tab, text="Giroscópio:").grid(row=2, column=0, sticky=tk.W, pady=5)
        gyro_sens = tk.IntVar(value=self.config.get_int('Sensitivity', 'gyro_sensitivity', 30))
        ttk.Scale(sensitivity_tab, from_=1, to=100, orient=tk.HORIZONTAL, variable=gyro_sens).grid(
            row=2, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Label(sensitivity_tab, textvariable=gyro_sens).grid(row=2, column=2)

        # IR
        ttk.Label(sensitivity_tab, text="Sensor IR:").grid(row=3, column=0, sticky=tk.W, pady=5)
        ir_sens = tk.IntVar(value=self.config.get_int('Sensitivity', 'ir_sensitivity', 40))
        ttk.Scale(sensitivity_tab, from_=1, to=100, orient=tk.HORIZONTAL, variable=ir_sens).grid(
            row=3, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Label(sensitivity_tab, textvariable=ir_sens).grid(row=3, column=2)

        sensitivity_tab.columnconfigure(1, weight=1)

        # Tab 2: Filtros
        filters_tab = ttk.Frame(notebook, padding="10")
        notebook.add(filters_tab, text="Filtros")

        ttk.Label(filters_tab, text="Configurações de Filtros", 
                 font=("Arial", 11, "bold")).grid(row=0, column=0, columnspan=3, pady=(0, 10), sticky=tk.W)

        # Lowpass Gyro
        ttk.Label(filters_tab, text="Lowpass Gyro (Alpha):").grid(row=1, column=0, sticky=tk.W, pady=5)
        gyro_alpha = tk.DoubleVar(value=self.config.get_float('Filters', 'gyro_lowpass_alpha', 0.25))
        gyro_alpha_scale = ttk.Scale(filters_tab, from_=0.0, to=1.0, orient=tk.HORIZONTAL, variable=gyro_alpha)
        gyro_alpha_scale.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5)
        gyro_alpha_label = ttk.Label(filters_tab, text=f"{gyro_alpha.get():.2f}")
        gyro_alpha_label.grid(row=1, column=2)
        gyro_alpha.trace_add("write", lambda *args: gyro_alpha_label.config(text=f"{gyro_alpha.get():.2f}"))

        # Lowpass Accel
        ttk.Label(filters_tab, text="Lowpass Accel (Alpha):").grid(row=2, column=0, sticky=tk.W, pady=5)
        accel_alpha = tk.DoubleVar(value=self.config.get_float('Filters', 'accel_lowpass_alpha', 0.25))
        accel_alpha_scale = ttk.Scale(filters_tab, from_=0.0, to=1.0, orient=tk.HORIZONTAL, variable=accel_alpha)
        accel_alpha_scale.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=5)
        accel_alpha_label = ttk.Label(filters_tab, text=f"{accel_alpha.get():.2f}")
        accel_alpha_label.grid(row=2, column=2)
        accel_alpha.trace_add("write", lambda *args: accel_alpha_label.config(text=f"{accel_alpha.get():.2f}"))

        filters_tab.columnconfigure(1, weight=1)

        # Tab 3: Calibração
        calibration_tab = ttk.Frame(notebook, padding="10")
        notebook.add(calibration_tab, text="Calibração")

        ttk.Label(calibration_tab, text="Configurações de Calibração", 
                 font=("Arial", 11, "bold")).grid(row=0, column=0, columnspan=3, pady=(0, 10), sticky=tk.W)

        # Auto calibrate
        auto_calib = tk.BooleanVar(value=self.config.get_bool('Calibration', 'auto_on_connect', True))
        ttk.Checkbutton(calibration_tab, text="Auto-calibrar ao conectar", 
                       variable=auto_calib).grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5)

        # Samples
        ttk.Label(calibration_tab, text="Amostras:").grid(row=2, column=0, sticky=tk.W, pady=5)
        samples = tk.IntVar(value=self.config.get_int('Calibration', 'samples', 60))
        ttk.Scale(calibration_tab, from_=10, to=200, orient=tk.HORIZONTAL, variable=samples).grid(
            row=2, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Label(calibration_tab, textvariable=samples).grid(row=2, column=2)

        # Sample delay
        ttk.Label(calibration_tab, text="Delay (ms):").grid(row=3, column=0, sticky=tk.W, pady=5)
        delay = tk.IntVar(value=self.config.get_int('Calibration', 'sample_delay_ms', 5))
        ttk.Scale(calibration_tab, from_=1, to=50, orient=tk.HORIZONTAL, variable=delay).grid(
            row=3, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Label(calibration_tab, textvariable=delay).grid(row=3, column=2)

        calibration_tab.columnconfigure(1, weight=1)

        # Tab 4: Mapeamento de Botões
        buttons_tab = ttk.Frame(notebook, padding="10")
        notebook.add(buttons_tab, text="Botões")

        ttk.Label(buttons_tab, text="Mapeamento de Botões", 
                 font=("Arial", 11, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky=tk.W)

        # Create scrollable frame for button mappings
        canvas = tk.Canvas(buttons_tab, height=400)
        scrollbar = ttk.Scrollbar(buttons_tab, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        button_mappings = {
            'a': ('A', self.config.get('ButtonMapping', 'a', 'left_click')),
            'b': ('B', self.config.get('ButtonMapping', 'b', 'right_click')),
            'one': ('1', self.config.get('ButtonMapping', 'one', 'toggle_control')),
            'two': ('2', self.config.get('ButtonMapping', 'two', 'center_mouse')),
            'plus': ('+', self.config.get('ButtonMapping', 'plus', 'scroll_up')),
            'minus': ('-', self.config.get('ButtonMapping', 'minus', 'scroll_down')),
            'home': ('Home', self.config.get('ButtonMapping', 'home', 'none')),
            'dpadup': ('D-Pad Up', self.config.get('ButtonMapping', 'dpadup', 'key_up')),
            'dpaddown': ('D-Pad Down', self.config.get('ButtonMapping', 'dpaddown', 'key_down')),
            'dpadleft': ('D-Pad Left', self.config.get('ButtonMapping', 'dpadleft', 'key_left')),
            'dpadright': ('D-Pad Right', self.config.get('ButtonMapping', 'dpadright', 'key_right')),
        }

        action_options = ['left_click', 'right_click', 'middle_click', 'toggle_control', 
                         'center_mouse', 'scroll_up', 'scroll_down', 'none',
                         'key_up', 'key_down', 'key_left', 'key_right']

        button_vars = {}
        for idx, (key, (label, current_action)) in enumerate(button_mappings.items()):
            ttk.Label(scrollable_frame, text=f"{label}:").grid(row=idx, column=0, sticky=tk.W, pady=3, padx=5)
            var = tk.StringVar(value=current_action)
            button_vars[key] = var
            combo = ttk.Combobox(scrollable_frame, textvariable=var, values=action_options, state='readonly', width=20)
            combo.grid(row=idx, column=1, sticky=(tk.W, tk.E), pady=3, padx=5)

        scrollable_frame.columnconfigure(1, weight=1)
        canvas.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=1, column=2, sticky=(tk.N, tk.S))
        buttons_tab.columnconfigure(0, weight=1)
        buttons_tab.rowconfigure(1, weight=1)

        # Save button at bottom
        def save_settings():
            # Save sensitivities
            self.config.set('Sensitivity', 'accel_sensitivity', str(accel_sens.get()))
            self.config.set('Sensitivity', 'gyro_sensitivity', str(gyro_sens.get()))
            self.config.set('Sensitivity', 'ir_sensitivity', str(ir_sens.get()))
            
            # Save filters
            self.config.set('Filters', 'gyro_lowpass_alpha', str(gyro_alpha.get()))
            self.config.set('Filters', 'accel_lowpass_alpha', str(accel_alpha.get()))
            
            # Save calibration
            self.config.set('Calibration', 'auto_on_connect', str(auto_calib.get()))
            self.config.set('Calibration', 'samples', str(samples.get()))
            self.config.set('Calibration', 'sample_delay_ms', str(delay.get()))
            
            # Save button mappings
            for key, var in button_vars.items():
                self.config.set('ButtonMapping', key, var.get())
            
            self.config.save()
            messagebox.showinfo("Configurações", "Configurações salvas com sucesso!")
            window.destroy()

        button_frame = ttk.Frame(window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="💾 Salvar", command=save_settings, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="❌ Cancelar", command=window.destroy, width=15).pack(side=tk.RIGHT, padx=5)

    def _calibrate(self):
        """Run calibration if connected."""
        if not self.driver or not self.driver.driver_state.connected:
            messagebox.showwarning("Calibração", "Wiimote não conectado.")
            return

        def _do_calibrate():
            self.root.after(0, lambda: self.status_text.set("📐 Calibrando..."))
            success = self.driver.calibrate()
            if success:
                self.root.after(0, lambda: self.status_text.set("✅ Conectado"))
                self.root.after(0, lambda: messagebox.showinfo("Calibração", "Calibração concluída."))
            else:
                self.root.after(0, lambda: self.status_text.set("❌ Falha na calibração"))
                self.root.after(0, lambda: messagebox.showerror("Calibração", "Falha na calibração."))

        threading.Thread(target=_do_calibrate, daemon=True).start()

    def _open_pairing_assistant(self):
        """Open Bluetooth pairing assistant."""
        window = tk.Toplevel(self.root)
        window.title("Assistente de Pareamento")
        window.resizable(False, False)

        frame = ttk.Frame(window, padding="12")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        ttk.Label(frame, text="Assistente de Pareamento", font=("Arial", 12, "bold")).grid(
            row=0, column=0, columnspan=2, pady=(0, 8))

        instructions = (
            "1) Ative o Bluetooth no Windows.\n"
            "2) Pressione 1 + 2 no Wiimote (LEDs piscando).\n"
            "3) Abra as configurações e conclua o pareamento.\n"
            "4) Clique em 'Verificar Wiimote'."
        )
        ttk.Label(frame, text=instructions, justify=tk.LEFT).grid(
            row=1, column=0, columnspan=2, sticky=tk.W, pady=(0, 8))

        status_var = tk.StringVar(value="Wiimote: não verificado")
        ttk.Label(frame, textvariable=status_var, font=("Arial", 9, "bold")).grid(
            row=2, column=0, columnspan=2, sticky=tk.W, pady=(0, 6))

        ttk.Button(frame, text="Abrir Bluetooth", command=self._open_bluetooth_settings).grid(
            row=3, column=0, sticky=tk.W, padx=(0, 6))
        ttk.Button(
            frame,
            text="Verificar Wiimote",
            command=lambda: self._check_wiimote_presence(status_var),
        ).grid(row=3, column=1, sticky=tk.W)

        ttk.Button(frame, text="Fechar", command=window.destroy).grid(
            row=4, column=0, columnspan=2, pady=(10, 0))

    def _open_bluetooth_settings(self):
        """Open Windows Bluetooth settings using pywin32 when available."""
        try:
            import win32api

            win32api.ShellExecute(0, "open", "ms-settings:bluetooth", None, None, 1)
            return
        except Exception:
            pass

        try:
            os.startfile("ms-settings:bluetooth")
        except Exception as exc:
            messagebox.showerror("Pareamento", f"Não foi possível abrir as configurações.\n{exc}")

    def _check_wiimote_presence(self, status_var):
        """Check if Wiimote appears in HID enumeration."""
        try:
            import hid

            devices = hid.enumerate(WiimoteDriver.NINTENDO_VENDOR_ID)
            found = any(
                device.get('product_id') in [
                    WiimoteDriver.WIIMOTE_PRODUCT_ID,
                    WiimoteDriver.WIIMOTE_PLUS_PRODUCT_ID,
                ]
                for device in devices
            )
            status_var.set("Wiimote: encontrado" if found else "Wiimote: não encontrado")
        except Exception as exc:
            status_var.set(f"Erro ao verificar: {exc}")

    def _maybe_open_pairing_assistant(self):
        """Offer pairing assistant after failed connection."""
        if messagebox.askyesno("Pareamento", "Deseja abrir o assistente de pareamento?"):
            self._open_pairing_assistant()

    def _update_status_fields(self, state: WiimoteState):
        """Update battery and peripherals status."""
        if state.battery_level >= 0:
            self.battery_text.set(f"{state.battery_level}%")
        else:
            self.battery_text.set("--%")

        # Update auto mode display
        if hasattr(state, 'effective_mode'):
            has_gyro = state.motionplus_connected
            if self.driver and not self.driver.motionplus_enabled:
                has_gyro = False
            mode_display = self._format_auto_mode(
                state.effective_mode,
                has_gyro,
                state.ir_visible,
            )
            self.auto_mode_text.set(mode_display)

        if state.extension_connected is None:
            self.peripherals_text.set("Desconhecido")
        elif state.extension_connected:
            self.peripherals_text.set("Extensão conectada")
        else:
            self.peripherals_text.set("Sem extensão")

        if self.driver and not self.driver.motionplus_enabled:
            self.motionplus_text.set("Desativado")
        else:
            self.motionplus_text.set(self._format_connected_state(state.motionplus_connected))
        self.nunchuk_text.set(self._format_connected_state(state.nunchuk_connected))

    def _format_connected_state(self, value):
        if value is True:
            return "Conectado"
        if value is False:
            return "Não conectado"
        return "Desconhecido"

    def _format_auto_mode(self, effective_mode: str, has_gyro: bool, has_ir: bool) -> str:
        """Format auto mode for display."""
        if effective_mode == "MotionPlus":
            if has_gyro and has_ir:
                return "Acelerômetro + Giroscópio + IR"
            elif has_gyro:
                return "Acelerômetro + Giroscópio"
            else:
                return "Acelerômetro"
        elif effective_mode == "Hybrid":
            if has_ir:
                return "Acelerômetro + IR"
            elif has_gyro:
                return "Acelerômetro + Giroscópio"
            else:
                return "Acelerômetro"
        elif effective_mode == "IR":
            if has_ir:
                return "Acelerômetro + IR"
            else:
                return "Acelerômetro"
        elif effective_mode == "Accel":
            return "Acelerômetro"
        else:
            return effective_mode

    def _update_driver_fields(self, driver_state):
        self.control_text.set("Ativado" if driver_state.control_enabled else "Desativado")
        if driver_state.profile:
            self.profile_text.set(driver_state.profile)

    def _poll_ui_updates(self):
        """Poll latest state and update UI on main thread."""
        state = None
        with self._ui_state_lock:
            state = self._ui_state

        if state is not None:
            self.update_debug_info(
                gyro=(state.gyro_x, state.gyro_y, state.gyro_z),
                accel=(state.accel_x, state.accel_y, state.accel_z),
                ir=(state.ir_x, state.ir_y),
                buttons=self.driver.get_pressed_buttons(state.buttons) if state.buttons is not None else None,
            )
            self._update_status_fields(state)
            if self.driver:
                self._update_driver_fields(self.driver.driver_state)

        self.root.after(33, self._poll_ui_updates)
    
    def update_debug_info(self, gyro=None, accel=None, ir=None, buttons=None):
        """Update debug information display."""
        if gyro is not None:
            self.gyro_x.set(f"{gyro[0]:6d}" if gyro[0] is not None else "    --")
            self.gyro_y.set(f"{gyro[1]:6d}" if gyro[1] is not None else "    --")
            self.gyro_z.set(f"{gyro[2]:6d}" if gyro[2] is not None else "    --")

        if accel is not None:
            self.accel_x.set(f"{accel[0]:6d}" if accel[0] is not None else "    --")
            self.accel_y.set(f"{accel[1]:6d}" if accel[1] is not None else "    --")
            self.accel_z.set(f"{accel[2]:6d}" if accel[2] is not None else "    --")
        
        if ir is not None:
            self.ir_x.set(f"{ir[0]:6d}" if ir[0] is not None else "    --")
            self.ir_y.set(f"{ir[1]:6d}" if ir[1] is not None else "    --")
        
        if buttons is not None:
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
