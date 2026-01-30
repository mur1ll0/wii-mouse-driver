# PRD + Spec (Spec-Driven Development)

## 1) Resumo do Produto
Driver/aplicação Windows para controlar o mouse/teclado do PC usando um Nintendo Wii Remote (Wiimote) via Bluetooth, com suporte a MotionPlus (giroscópio) e Nunchuk. Sensores de movimento controlam o cursor e botões executam ações configuráveis. Deve permitir calibração, perfis e operação estável com baixa latência.

## 2) Objetivos
- Permitir controle fluido do cursor usando giroscópio (MotionPlus) com fallback para acelerômetro e, se necessário, IR.
- Suportar Nunchuk (stick analógico + botões) como entradas adicionais.
- Mapear botões para ações (mouse/teclado/atalhos) configuráveis.
- Prover GUI simples para iniciar/parar, calibrar e ajustar sensibilidade, com status básico de conexão e bateria.
- Implementar um driver/serviço de comunicação robusto com o Wiimote.

## 3) Não-Objetivos (por enquanto)
- Compatibilidade com macOS/Linux.
- Suporte a múltiplos Wiimotes simultâneos.
- Dashboard com gráficos em tempo real.
- Logging persistente em arquivo.

## 4) Usuários-Alvo
- Usuários Windows 10/11 com Wiimote e Bluetooth.
- Enthusiasts e criadores de setups alternativos para mouse.

## 5) Experiência do Usuário (UX)
- Usuário pareia o Wiimote via Bluetooth ou usa assistente de pareamento na aplicação.
- Abre a aplicação e clica “Start”.
- Pressiona um botão (ex.: 1) para ativar/desativar controle do cursor.
- Move o Wiimote para movimentar o cursor.
- Botões A/B fazem clique esquerdo/direito (configurável).
- Pode calibrar eixo/offset e ajustar sensibilidade.

## 6) Requisitos Funcionais
### 6.1 Conexão
- Detectar Wiimote pareado via HID.
- Conectar e ler pacotes em tempo real.
- Reconectar automaticamente se conexão cair.
- Tentar conexão direta quando o Wiimote entrar em modo de sincronização.
- Se conexão direta falhar, oferecer assistente de pareamento na aplicação.

### 6.2 Sensores
- Ler acelerômetro do Wiimote.
- Ler giroscópio (MotionPlus).
- Ler Nunchuk (stick + acelerômetro + botões).
- Suportar calibração de offset/centro.

### 6.3 Controle de Cursor
- Mapear movimento para delta de mouse usando acelerômetro como base.
- **Detecção automática de recursos** para determinar modo de operação:
  - **Acelerômetro** (base, sempre disponível em todos os Wiimotes)
  - **Acelerômetro + IR** (quando sensor bar detectado)
  - **Acelerômetro + Giroscópio** (quando MotionPlus disponível)
  - **Acelerômetro + Giroscópio + IR** (todos os recursos disponíveis)
- Sistema muda automaticamente entre modos conforme detecta recursos disponíveis.
- Ajustes de sensibilidade por eixo para cada componente (accel, gyro, IR).
- Filtro de suavização (smoothing) configurável.

### 6.4 Mapeamento de Botões
- Mapear botões Wiimote e Nunchuk para ações:
  - mouse: clique esquerdo, direito, arrastar, scroll
  - teclado: teclas simples, combinações
  - sistema: toggle control, center mouse
- Permitir customização via config.ini.

### 6.5 UI
- Exibir status: conectado, **modo automático ativo**, bateria, periféricos conectados (ex.: Nunchuk, MotionPlus).
- Indicador visual de recursos detectados: Acelerômetro (sempre), IR (se detectado), Giroscópio (se disponível).
- Botões: Start/Stop, Calibrar, Configurações Avançadas.
- Tela de configurações para ajustar sensibilidades, mapeamento de botões e parâmetros sem editar config.ini.
- Debug info com valores de sensores em tempo real e modo automático atual.
- Sem gráficos em tempo real.

### 6.6 Persistência e Configuração
- Ler/escrever config.ini.
- Perfis: salvar diferentes configurações e permitir troca rápida.
- Logs apenas em console.

## 7) Requisitos Não Funcionais
- Latência: < 25 ms do input ao cursor.
- Uso de CPU baixo (< 5% em idle).
- Estabilidade: rodar continuamente por horas sem travar.
- Segurança: nenhuma coleta de dados.

## 8) Fluxos Principais (User Stories)
1) **Conectar e controlar**: Como usuário, quero conectar o Wiimote e que o sistema detecte automaticamente os sensores disponíveis para usar o melhor modo de controle possível.
2) **Configurar botões e sensibilidade**: Como usuário, quero uma tela de configurações para ajustar mapeamento de botões, sensibilidade dos sensores e outros parâmetros sem editar arquivos manualmente.
3) **Calibrar**: Como usuário, quero calibrar o centro do movimento para evitar drift.
4) **Usar Nunchuk**: Como usuário, quero usar o analógico do Nunchuk para ações extras.
5) **Ver recursos detectados**: Como usuário, quero ver quais recursos (IR, MotionPlus) foram detectados e qual modo automático está ativo.

## 9) Requisitos Técnicos
- Python 3.8+.
- Dependências: hidapi, pyautogui, tkinter.
- Comunicação HID com Wiimote.
- Loop de leitura contínuo com buffering e timestamp.
- Thread separada para leitura do dispositivo.

## 10) Especificações Técnicas (Spec)
### 10.1 Módulos Principais
- `src/wiimote/connection.py`: descoberta/conexão HID, reconexão.
- `src/wiimote/protocol.py`: parse de pacotes, enums, offsets.
- `src/wiimote/driver.py`: loop principal, eventos, callbacks.
- `src/mouse/controller_driver.py`: traduz sensores em movimento do mouse.
- `src/mouse/mapping.py`: mapear botões para ações.
- `src/ui/gui.py`: UI e controle do driver.

### 10.2 Interfaces
- Driver expõe eventos: `on_connect`, `on_disconnect`, `on_button`, `on_motion`, `on_nunchuk`.
- Config do driver em `config.ini`.

### 10.3 Comportamento Esperado
- Ao conectar: setar LEDs, iniciar modo relatório adequado.
- Ler pacotes em loop com timeout.
- Desconexões tratadas com retry.

## 11) Testes (Critérios de Aceitação)
- `test_wiimote.py` deve conectar e ler dados com Wiimote pareado.
- Teste de protocolo: validar parse de pacotes.
- Teste de mapeamento: botões -> ações corretas.
- Latência medida abaixo do limite.

## 12) Riscos e Mitigações
- **Wiimote não detectado**: instruções claras de pareamento e assistente de pareamento.
- **Drift do gyro**: rotina de recalibração.
- **Bluetooth instável**: reconexão automática.
## 13) Roadmap (Sugestão)
- Fase 1: Conexão + leitura + MotionPlus + botões básicos.
- Fase 2: Nunchuk + mapeamento avançado + UI básica + perfis.
- Fase 3: calibração + reconexão/sincronização + otimização.