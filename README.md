# 🎮 Wii Mouse Driver

[English](#english) | [Português](#português)

---

# STILL NOT WORKING!!! Run the test_wiimote.py file if you want to test the connection with the wiimote controller. The Entire system is under working, this project was started on 2026-01-26.

## English

Control your PC mouse using a Wiimote via Bluetooth!

### 📋 Requirements

- **Windows 10/11**
- **Python 3.8+**
- **Wiimote** (with built-in Motion Plus or separate)
- **Bluetooth** on PC

### 🚀 Installation

#### 1. Clone the repository

```bash
git clone https://github.com/your-username/wii-mouse-driver.git
cd wii-mouse-driver
```

#### 2. Install dependencies

```bash
pip install -r requirements.txt
```

**Main dependencies:**
- `hidapi` - HID communication with Wiimote
- `pyautogui` - Mouse control
- `tkinter` - GUI (usually included with Python)

### 🔌 How to connect the Wiimote

#### Step 1: Enable Bluetooth on Windows
- Open **Settings** → **Devices** → **Bluetooth & other devices**
- Make sure Bluetooth is **enabled**

#### Step 2: Pair the Wiimote
1. Click **Add Bluetooth or other device**
2. Select **Bluetooth**
3. On the Wiimote, press **1 + 2** simultaneously (LEDs will start blinking)
4. Wait for **"Nintendo RVL-CNT-01"** or **"Nintendo RVL-CNT-01-TR"** to appear
5. Click on the device and wait for connection (no code needed)
6. Windows may show "Connected" then "Paired"

#### Step 3: Keep the Wiimote active
- Before using the driver, press **1 + 2** again to activate LEDs
- The Wiimote needs to have blinking LEDs to be detected

### 💻 How to use

#### Mode 1: GUI (Recommended)

```bash
python main.py
```

Or use the generated executable (see Build section).

#### Mode 2: Command line

```bash
python -m src.ui.gui
```

### Default controls

| Button | Action |
|--------|--------|
| **1** | Enable/disable mouse control |
| **2** | Center cursor on screen |
| **A** | Left click |
| **B** | Right click |
| **D-Pad** | Keyboard arrows |

### Control modes

- **IR Mode**: Uses infrared sensor (point at screen)
- **MotionPlus Mode**: Uses gyroscope (move the controller)
- **Hybrid Mode**: Combines accelerometer and gyroscope

### ⚙️ Configuration

Edit `config.ini` file to customize:

```ini
[General]
mode = MotionPlus
auto_center = true
debug = false

[Sensitivity]
gyro_x = 15.0
gyro_y = 15.0
smoothing = 0.3

[ButtonMapping]
A = left_click
B = right_click
One = toggle_control
Two = center_mouse
```

### 🧪 Running tests

#### Test Wiimote connection:

```bash
python test_wiimote.py
```

This script tests:
- ✅ Wiimote detection via HID
- ✅ Sending commands (LEDs, rumble)
- ✅ Reading data (buttons, accelerometer, gyroscope)

#### Test protocol:

```bash
python -m pytest tests/
```

### 📦 Build - Create executable

#### Windows

```bash
python build.py
```

Or simply:

```bash
build.bat
```

The executable will be generated in: **`dist/Wii Mouse Driver.exe`**

#### Distribution

After building, copy the `dist/` folder wherever you want. The executable is standalone and doesn't need Python installed.

### 📁 Project structure

```
wii-mouse-driver/
├── main.py              # Main entry point
├── config.ini           # Application settings
├── requirements.txt     # Python dependencies
├── build.py            # Build script
├── build.bat           # Windows build (alternative)
├── src/
│   ├── wiimote/        # Wiimote communication
│   │   ├── driver.py   # Main driver
│   │   └── connection.py
│   ├── mouse/          # Mouse control
│   │   └── controller_driver.py
│   └── ui/             # GUI
│       └── gui.py
└── tests/              # Automated tests
```

### 🐛 Troubleshooting

#### Wiimote not detected
- ✅ Check if it's paired in Windows Bluetooth
- ✅ Press **1 + 2** to activate (LEDs should blink)
- ✅ Check Wiimote batteries

#### Error "hidapi not found"
```bash
pip install hidapi --force-reinstall
```

#### Mouse doesn't move
- ✅ Click **"Start"** in the interface
- ✅ Press **1** on Wiimote to activate control
- ✅ Check if mode is correct (MotionPlus recommended)

#### LEDs turn off quickly
- This is normal. The Wiimote enters power-saving mode.
- Press any button to reactivate.

### 📝 License

MIT License - see [LICENSE](LICENSE)

### 🤝 Contributing

Contributions are welcome! Open issues or pull requests.

### 📧 Contact

For questions or suggestions, open an issue on GitHub.

---

## Português

Controle o mouse do seu PC usando um Wiimote via Bluetooth!

### 📋 Requisitos

- **Windows 10/11**
- **Python 3.8+**
- **Wiimote** (com Motion Plus embutido ou separado)
- **Bluetooth** no PC

### 🚀 Instalação

#### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/wii-mouse-driver.git
cd wii-mouse-driver
```

#### 2. Instale as dependências

```bash
pip install -r requirements.txt
```

**Dependências principais:**
- `hidapi` - Comunicação HID com o Wiimote
- `pyautogui` - Controle do mouse
- `tkinter` - Interface gráfica (geralmente já incluído no Python)

### 🔌 Como conectar o Wiimote

#### Passo 1: Ative o Bluetooth no Windows
- Abra **Configurações** → **Dispositivos** → **Bluetooth e outros dispositivos**
- Certifique-se que o Bluetooth está **ativado**

#### Passo 2: Pareie o Wiimote
1. Clique em **Adicionar Bluetooth ou outro dispositivo**
2. Selecione **Bluetooth**
3. No Wiimote, pressione **1 + 2** simultaneamente (os LEDs começarão a piscar)
4. Aguarde aparecer **"Nintendo RVL-CNT-01"** ou **"Nintendo RVL-CNT-01-TR"**
5. Clique no dispositivo e aguarde conectar (não precisa de código)
6. O Windows pode mostrar "Conectado" e depois "Pareado"

#### Passo 3: Mantenha o Wiimote ativo
- Antes de usar o driver, pressione **1 + 2** novamente para ativar os LEDs
- O Wiimote precisa estar com os LEDs piscando para ser detectado

### 💻 Como usar

#### Modo 1: Interface Gráfica (Recomendado)

```bash
python main.py
```

Ou use o executável gerado (veja seção de Build).

#### Modo 2: Linha de comando

```bash
python -m src.ui.gui
```

### Controles padrão

| Botão | Ação |
|-------|------|
| **1** | Ativar/desativar controle do mouse |
| **2** | Centralizar cursor na tela |
| **A** | Clique esquerdo |
| **B** | Clique direito |
| **D-Pad** | Setas do teclado |

### Modos de controle

- **IR Mode**: Usa o sensor infravermelho (aponte para a tela)
- **MotionPlus Mode**: Usa giroscópio (movimente o controle)
- **Hybrid Mode**: Combina acelerômetro e giroscópio

### ⚙️ Configuração

Edite o arquivo `config.ini` para personalizar:

```ini
[General]
mode = MotionPlus
auto_center = true
debug = false

[Sensitivity]
gyro_x = 15.0
gyro_y = 15.0
smoothing = 0.3

[ButtonMapping]
A = left_click
B = right_click
One = toggle_control
Two = center_mouse
```

### 🧪 Executar testes

#### Testar conexão com o Wiimote:

```bash
python test_wiimote.py
```

Este script testa:
- ✅ Detecção do Wiimote via HID
- ✅ Envio de comandos (LEDs, rumble)
- ✅ Leitura de dados (botões, acelerômetro, giroscópio)

#### Testar protocolo:

```bash
python -m pytest tests/
```

### 📦 Build - Criar executável

#### Windows

```bash
python build.py
```

Ou simplesmente:

```bash
build.bat
```

O executável será gerado em: **`dist/Wii Mouse Driver.exe`**

#### Distribuir

Após o build, copie a pasta `dist/` para onde quiser. O executável é standalone e não precisa de Python instalado.

### 📁 Estrutura do projeto

```
wii-mouse-driver/
├── main.py              # Ponto de entrada principal
├── config.ini           # Configurações da aplicação
├── requirements.txt     # Dependências Python
├── build.py            # Script de build
├── build.bat           # Build Windows (alternativo)
├── src/
│   ├── wiimote/        # Comunicação com Wiimote
│   │   ├── driver.py   # Driver principal
│   │   └── connection.py
│   ├── mouse/          # Controle do mouse
│   │   └── controller_driver.py
│   └── ui/             # Interface gráfica
│       └── gui.py
└── tests/              # Testes automatizados
```

### 🐛 Solução de problemas

#### Wiimote não é detectado
- ✅ Verifique se está pareado no Bluetooth do Windows
- ✅ Pressione **1 + 2** para ativar (LEDs devem piscar)
- ✅ Verifique as pilhas do Wiimote

#### Erro "hidapi not found"
```bash
pip install hidapi --force-reinstall
```

#### Mouse não se move
- ✅ Clique em **"Iniciar"** na interface
- ✅ Pressione **1** no Wiimote para ativar o controle
- ✅ Verifique se o modo está correto (MotionPlus recomendado)

#### LEDs desligam rapidamente
- Isso é normal. O Wiimote entra em modo de economia.
- Pressione qualquer botão para reativar.

### 📝 Licença

MIT License - veja [LICENSE](LICENSE)

### 🤝 Contribuindo

Contribuições são bem-vindas! Abra issues ou pull requests.

### 📧 Contato

Para dúvidas ou sugestões, abra uma issue no GitHub.

---

**Developed with ❤️ using Python and HIDapi | Desenvolvido com ❤️ usando Python e HIDapi**
