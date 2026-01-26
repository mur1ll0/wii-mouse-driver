# Contributing to Wii Mouse Driver

[English](#english) | [Português](#português)

---

## English

Thank you for considering contributing! 🎮

### How to contribute

#### 1. Report bugs

Open an issue describing:
- Python version
- Operating system
- Wiimote model
- Steps to reproduce the bug
- Expected vs actual behavior

#### 2. Suggest improvements

Open an issue with the "enhancement" label describing:
- Desired functionality
- Use case
- Example of how it should work

#### 3. Submit code

1. Fork the project
2. Create a branch for your feature: `git checkout -b feature/feature-name`
3. Commit your changes: `git commit -m 'Add new feature'`
4. Push to the branch: `git push origin feature/feature-name`
5. Open a Pull Request

### Code conventions

- Use **4 spaces** for indentation (no tabs)
- Follow PEP 8
- Add docstrings to public functions
- Comment complex code

### Tests

Run tests before submitting:
```bash
python -m pytest tests/
python test_wiimote.py
```

### Code structure

- `src/wiimote/` - HID communication with Wiimote
- `src/mouse/` - Mouse/keyboard control
- `src/ui/` - Graphical interface
- `tests/` - Automated tests

### Questions?

Open an issue or get in touch!

---

## Português

Obrigado por considerar contribuir! 🎮

### Como contribuir

#### 1. Reportar bugs

Abra uma issue descrevendo:
- Versão do Python
- Sistema operacional
- Modelo do Wiimote
- Passos para reproduzir o bug
- Comportamento esperado vs atual

#### 2. Sugerir melhorias

Abra uma issue com o label "enhancement" descrevendo:
- Funcionalidade desejada
- Caso de uso
- Exemplo de como deveria funcionar

#### 3. Submeter código

1. Faça um fork do projeto
2. Crie uma branch para sua feature: `git checkout -b feature/nome-da-feature`
3. Faça commit das mudanças: `git commit -m 'Adiciona nova feature'`
4. Faça push para a branch: `git push origin feature/nome-da-feature`
5. Abra um Pull Request

### Convenções de código

- Use **4 espaços** para indentação (não tabs)
- Siga PEP 8
- Adicione docstrings em funções públicas
- Comente código complexo

### Testes

Execute os testes antes de submeter:
```bash
python -m pytest tests/
python test_wiimote.py
```

### Estrutura do código

- `src/wiimote/` - Comunicação HID com o Wiimote
- `src/mouse/` - Controle do mouse/teclado
- `src/ui/` - Interface gráfica
- `tests/` - Testes automatizados

### Dúvidas?

Abra uma issue ou entre em contato!

---

**Thank you for contributing! | Obrigado por contribuir!** 🎮
