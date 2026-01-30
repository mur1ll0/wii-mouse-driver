#!/usr/bin/env python3
"""
Build script for Wii Mouse Driver using PyInstaller
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import List

def clean_build():
    """Clean previous build artifacts."""
    print("🧹 Limpando builds anteriores...")
    
    dirs_to_remove = ['build', 'dist', '__pycache__']
    files_to_remove = ['Wii Mouse Driver.spec']
    
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"   Removido: {dir_name}/")
    
    for file_name in files_to_remove:
        if os.path.exists(file_name):
            os.remove(file_name)
            print(f"   Removido: {file_name}")

def check_pyinstaller():
    """Check if PyInstaller is installed."""
    try:
        import PyInstaller
        print(f"✅ PyInstaller {PyInstaller.__version__} encontrado")
        return True
    except ImportError:
        print("❌ PyInstaller não encontrado!")
        print("   Instalando PyInstaller...")
        
        result = subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"],
                              capture_output=True)
        
        if result.returncode != 0:
            print("❌ Erro ao instalar PyInstaller!")
            return False
        
        print("✅ PyInstaller instalado com sucesso!")
        return True

def build_executable():
    """Build the executable using PyInstaller."""
    print("\n📦 Gerando executável...")

    extra_binaries: List[str] = []
    try:
        import hid  # type: ignore
        import inspect

        hid_path = Path(inspect.getfile(hid))
        if hid_path.exists():
            extra_binaries.append(f"{hid_path};.")

        # Include any hidapi DLLs if present
        site_packages = hid_path.parent
        for pattern in ("hidapi.dll", "libhidapi-0.dll", "libhidapi.dll"):
            for dll in site_packages.glob(pattern):
                extra_binaries.append(f"{dll};.")
    except Exception:
        pass
    
    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=Wii Mouse Driver",
        "--onefile",
        "--windowed",
        "--add-data", "config.ini;." if sys.platform == "win32" else "config.ini:.",
        "--add-data", "src;src" if sys.platform == "win32" else "src:src",
        "--hidden-import=hid",
        "--collect-binaries=hid",
        "--hidden-import=pyautogui",
        "--hidden-import=pynput",
        "--collect-all=pyautogui",
        "--collect-all=pynput",
        "--collect-submodules=tkinter",
        "--copy-metadata=pyautogui",
        "--copy-metadata=pynput",
        "main.py"
    ]

    for binary in extra_binaries:
        cmd.insert(-1, "--add-binary")
        cmd.insert(-1, binary)
    
    result = subprocess.run(cmd)
    
    if result.returncode != 0:
        print("\n❌ Erro ao gerar executável!")
        return False
    
    return True


def ensure_dependencies():
    """Ensure required packages are installed before building."""
    print("\n📦 Verificando dependências (requirements.txt)...")

    requirements = Path("requirements.txt")
    if not requirements.exists():
        print("⚠️  requirements.txt não encontrado; pulando instalação automática.")
        return True

    result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(requirements)])
    if result.returncode != 0:
        print("❌ Falha ao instalar dependências. Veja a saída acima.")
        return False

    print("✅ Dependências instaladas/atualizadas")
    return True

def copy_resources():
    """Copy additional resources to dist folder."""
    print("\n📋 Copiando recursos adicionais...")
    
    # Copy config file
    if os.path.exists("config.ini"):
        shutil.copy2("config.ini", "dist/config.ini")
        print("   ✅ config.ini copiado")
    
    # Create README in dist
    readme_content = """
Wii Mouse Driver
================

Como usar:
1. Pareie seu Wiimote com o Bluetooth do Windows
2. Pressione 1+2 no Wiimote para ativar (LEDs piscando)
3. Execute "Wii Mouse Driver.exe"
4. Clique em "Iniciar"
5. Pressione 1 no Wiimote para ativar/desativar controle do mouse

Controles padrão:
- A: Clique esquerdo
- B: Clique direito
- 1: Ativar/desativar controle
- 2: Centralizar cursor
- Direcionais: Setas do teclado

Configurações:
Edite o arquivo config.ini para personalizar.
"""
    
    with open("dist/LEIA-ME.txt", "w", encoding="utf-8") as f:
        f.write(readme_content)
    print("   ✅ LEIA-ME.txt criado")

def main():
    """Main build process."""
    print("="*60)
    print("  🎮 Wii Mouse Driver - Build Script")
    print("="*60)
    print()
    
    # Check PyInstaller
    if not check_pyinstaller():
        input("\n❌ Não foi possível continuar. Pressione ENTER...")
        sys.exit(1)

    # Ensure dependencies are installed
    if not ensure_dependencies():
        input("\n❌ Não foi possível instalar dependências. Pressione ENTER...")
        sys.exit(1)
    
    # Clean previous builds
    clean_build()
    
    # Build executable
    if not build_executable():
        input("\n❌ Build falhou! Pressione ENTER...")
        sys.exit(1)
    
    # Copy resources
    copy_resources()
    
    print("\n" + "="*60)
    print("  ✅ Build concluído com sucesso!")
    print("="*60)
    print()
    print(f"📂 Executável gerado em: {os.path.abspath('dist')}")
    print(f"🎮 Arquivo: Wii Mouse Driver.exe")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Build cancelado pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        input("\nPressione ENTER para sair...")
        sys.exit(1)
