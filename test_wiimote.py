"""Teste melhorado de conexão com Wiimote."""

import sys
import logging
import time
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from wiimote.connection import WiimoteConnection

try:
    import pytest
except Exception:
    pytest = None
from logging_utils import configure_logging

# Configure logging
configure_logging()

logger = logging.getLogger(__name__)


def test_connection_improved():
    """Teste melhorado com múltiplas tentativas."""
    is_pytest = "PYTEST_CURRENT_TEST" in os.environ
    if is_pytest and os.environ.get("WIIMOTE_INTERACTIVE") != "1":
        if pytest is not None:
            pytest.skip("Teste interativo; defina WIIMOTE_INTERACTIVE=1 para executar.")
    logger.info("\n" + "="*70)
    logger.info("🎮 TESTE DE CONEXÃO - WII MOUSE DRIVER")
    logger.info("="*70)
    
    logger.info("\n⚠️  INSTRUÇÃO:")
    logger.info("   1. Pressione os botões 1+2 no Wiimote SIMULTANEAMENTE")
    logger.info("   2. Aguarde os LEDs começarem a PISCAR")
    logger.info("   3. Aperte ENTER aqui para continuar o teste")
    
    input("\n   >>> Pressione ENTER quando os LEDs estiverem piscando...")
    
    logger.info("\n✅ Iniciando teste...")
    
    try:
        # Create connection
        wiimote = WiimoteConnection()
        
        # Find Wiimote
        logger.info("🔍 Procurando Wiimote...")
        device_info = wiimote.find_wiimote(timeout=5)
        
        if device_info is None:
            logger.error("❌ Wiimote não encontrado!")
            return False
        
        # Connect to device
        logger.info("🔌 Abrindo conexão HID...")
        
        # Open device manually
        import hid
        path = device_info.get('path')
        if isinstance(path, str):
            path = path.encode('utf-8')
        
        device = hid.device()
        device.open_path(path)
        logger.info("✅ Conexão HID aberta!")
        
        # Test 1: Send LED command WITHOUT waiting for response first
        logger.info("\n📤 Enviando comando de LED 1...")
        device.write(bytes([0x11, 0x10]))  # LED 1
        time.sleep(0.2)
        
        # Test 2: Try to read data
        logger.info("📥 Aguardando resposta do Wiimote...")
        logger.info("   PRESSIONE E SEGURE um botão por 3 segundos!\n")
        
        data_received = False
        start = time.time()
        
        while time.time() - start < 8:
            try:
                data = device.read(32, 200)
                if data and len(data) > 0:
                    logger.info(f"   ✅ Recebido {len(data)} bytes!")
                    logger.info(f"      {bytes(data).hex()}")
                    data_received = True
                    break
            except:
                pass
        
        if not data_received:
            logger.warning("   ⚠️  Nenhum dado recebido")
            logger.warning("\n   Possíveis problemas:")
            logger.warning("   1. Wiimote sem pilhas ou pilhas fracas")
            logger.warning("   2. Não pressionou botão ou pressionou muito rápido")
            logger.warning("   3. Distância muito grande ou interferência")
            logger.warning("   4. Wiimote pode estar em modo de economia de energia")
            device.close()
            return False
        
        # Test 3: Control LEDs
        logger.info("\n💡 Testando controle de LEDs...")
        
        for led_num in range(1, 5):
            leds = [False, False, False, False]
            leds[led_num - 1] = True
            
            led_byte = sum([
                0x10 if leds[0] else 0,
                0x20 if leds[1] else 0,
                0x40 if leds[2] else 0,
                0x80 if leds[3] else 0,
            ])
            
            logger.info(f"   Acendendo LED {led_num}...")
            device.write(bytes([0x11, led_byte]))
            time.sleep(0.5)
            logger.info("✅")
        
        # All LEDs on
        logger.info("   Acendendo todos LEDs...")
        device.write(bytes([0x11, 0xF0]))
        time.sleep(0.5)
        logger.info("✅")
        
        # Test 4: Rumble
        logger.info("\n📳 Testando vibração...")
        logger.info("   Ligando vibração...")
        device.write(bytes([0x10, 0x01]))
        time.sleep(0.5)
        logger.info("✅")
        
        logger.info("   Desligando vibração...")
        device.write(bytes([0x10, 0x00]))
        time.sleep(0.2)
        logger.info("✅")
        
        # IMPORTANT: Enable continuous reporting mode BEFORE data collection
        logger.info("\n⚙️  Configurando modo de reporte contínuo...")
        # Command: 0x12 = set report mode, 0x04 = continuous, 0x31 = buttons + accel
        device.write(bytes([0x12, 0x04, 0x31]))
        time.sleep(0.5)
        logger.info("   ✅ Modo contínuo ativado!")
        
        # Test 5: Data collection
        logger.info("\n📊 Coletando dados (10 segundos)...")
        logger.info("   Mova o controle, pressione botões e use aceleração!\n")
        
        packets = 0
        start = time.time()
        while time.time() - start < 10:
            try:
                # Use shorter timeout for faster reading
                data = device.read(32, 50)  # 50ms timeout instead of 100ms
                if data and len(data) > 0:
                    packets += 1
                    data_bytes = bytes(data)
                    
                    # Parse the data
                    info = f"Pacote #{packets} ({len(data)} bytes): {data_bytes.hex()}"
                    
                    # Wiimote data format for report mode 0x31:
                    # Byte 0: Report ID (usually 0x31 or 0x20)
                    # Bytes 1-2: Button state
                    if len(data) > 2:
                        buttons = (data[1] << 8) | data[2]
                        button_names = []
                        
                        # Button mappings
                        if buttons & 0x0001: button_names.append("TWO")
                        if buttons & 0x0002: button_names.append("ONE")
                        if buttons & 0x0004: button_names.append("B")
                        if buttons & 0x0008: button_names.append("A")
                        if buttons & 0x0010: button_names.append("MINUS")
                        if buttons & 0x0020: button_names.append("HOME")
                        if buttons & 0x0040: button_names.append("PLUS")
                        if buttons & 0x0080: button_names.append("LEFT")
                        if buttons & 0x0100: button_names.append("RIGHT")
                        if buttons & 0x0200: button_names.append("DOWN")
                        if buttons & 0x0400: button_names.append("UP")
                        if buttons & 0x0800: button_names.append("Z")
                        if buttons & 0x1000: button_names.append("C")
                        
                        if button_names:
                            info += f" | Botões: {', '.join(button_names)}"
                    
                    # Accelerometer data (bytes 3-5 for report mode 0x31)
                    if len(data) > 5:
                        accel_x = data[3]
                        accel_y = data[4]
                        accel_z = data[5]
                        info += f" | Accel: X={accel_x:3d} Y={accel_y:3d} Z={accel_z:3d}"
                    
                    # Motion Plus data (if Wiimote Plus)
                    if len(data) > 8:
                        gyro_x = (data[6] | ((data[9] & 0xFC) << 6)) if len(data) > 9 else 0
                        gyro_y = (data[7] | ((data[9] & 0x03) << 8)) if len(data) > 9 else 0
                        gyro_z = data[8] if len(data) > 8 else 0
                        if gyro_x or gyro_y or gyro_z:
                            info += f" | Gyro: X={gyro_x:5d} Y={gyro_y:5d} Z={gyro_z:3d}"
                    
                    logger.info(f"   {info}")
            except Exception as e:
                pass
        
        if packets > 0:
            logger.info(f"\n✅ Recebidos {packets} pacotes em 10 segundos!")
        else:
            logger.warning("\n⚠️  Nenhum pacote recebido durante coleta")
        
        device.close()
        logger.info("\n✅ TESTE COMPLETO COM SUCESSO!")
        return True
        
    except Exception as e:
        logger.exception(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_connection_improved()
    logger.info("\n" + "="*70 + "\n")
