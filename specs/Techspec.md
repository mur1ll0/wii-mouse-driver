# Techspec — Wii Mouse Driver

> Documento técnico para implementação do projeto baseado no PRD. Focado em Windows 10/11.

## 1) Stack recomendada (linguagem + bibliotecas)
### Linguagem
**Python 3.10+** (compatível com 3.8+), devido ao ecossistema atual do projeto e facilidade de integração com GUI e HID.

### Bibliotecas principais (recomendação)
- **hidapi** via wrapper **`hid`** — comunicação HID direta com o Wiimote.
- **pyautogui** — controle de mouse/teclado (simples e estável).
- **keyboard** (opcional) — envio de teclas mais avançado.
- **tkinter** — GUI leve (já incluído no Python).
- **pywin32** — integração com APIs do Windows (assistente de pareamento).

### Alternativas (caso necessário)
- **pywin32** para integração Windows (notificações, controle mais fino de input).
- **inputs** ou **pynput** para controle de teclado/mouse mais granular.
- **bleak** para BLE (não aplicável ao Wiimote clássico, mas útil para futuros dispositivos).

> Observação: o Wiimote clássico utiliza Bluetooth HID tradicional (não BLE), portanto **hidapi** é a solução principal.

## 2) Arquitetura de alto nível
```
[Wiimote HID] -> [Wiimote Connection] -> [Protocol Parser] -> [Driver Core]
                                                   |                 |
                                                   |                 v
                                                   |           [Mouse Controller]
                                                   |                 |
                                                   v                 v
                                             [Event Bus]        [OS Input]
                                                   |
                                                   v
                                               [UI]
```

### Componentes
- **Connection Layer**: descoberta, conexão, reconexão e leitura HID.
- **Protocol Parser**: decodifica pacotes (botões, acelerômetro, MotionPlus, Nunchuk).
- **Driver Core**: gerenciamento de estado, calibração, filtros e distribuição de eventos.
- **Mouse Controller**: converte movimento em deltas do cursor.
- **Mapping Engine**: mapeia botões para ações.
- **UI**: status, start/stop, troca de perfil, calibração.

## 3) Fluxo de dados
1. Conectar ao dispositivo HID.
2. Ativar modo de relatório adequado (report type).
3. Loop de leitura em thread dedicada.
4. Parser converte bytes em eventos semânticos.
5. Driver aplica calibração e filtros.
6. Mouse Controller gera ações de input.
7. UI consome status e eventos básicos.

## 4) Protocolo Wiimote (resumo técnico)
> **Objetivo**: documentar o mínimo necessário para ler botões, acelerômetro, MotionPlus e Nunchuk.

### 4.1 Canais HID
- **Output report**: enviado ao Wiimote (LEDs, rumble, modo de relatório, leitura de memória).
- **Input report**: recebido do Wiimote (botões/sensores).

### 4.2 Identificadores de relatório (report IDs)
- **0x30**: Botões apenas.
- **0x31**: Botões + acelerômetro.
- **0x32**: Botões + acelerômetro + 8 bytes de extensão.
- **0x33**: Botões + IR (básico).
- **0x34**: Botões + acelerômetro + IR.
- **0x35**: Botões + extensão + IR.
- **0x36**: Botões + acelerômetro + 16 bytes de extensão.
- **0x37**: Botões + IR + 16 bytes de extensão.

> Recomendado: **0x32** (ou 0x36, se precisar de mais dados de extensão).

### 4.3 Botões (bitmask)
- **Byte 0-1**: bitmask dos botões (A, B, 1, 2, Home, D-pad, +, -).

### 4.4 Acelerômetro
- Inclusão no report 0x31/0x32.
- 3 eixos (X/Y/Z), resolução dependente do modo.

### 4.5 MotionPlus (giroscópio)
- Requer habilitar extensão MotionPlus.
- Dados do gyro vêm no bloco de extensão (8 ou 16 bytes dependendo do modo).
- Eixos: **yaw, pitch, roll** (escala depende do modo rápido/lento).

### 4.6 Nunchuk
- Requer habilitar extensão Nunchuk.
- Dados incluem: stick analógico (X/Y), acelerômetro (X/Y/Z) e botões (C/Z).

### 4.7 Inicialização típica (alto nível)
1. Conectar via HID.
2. Ativar rumble/LEDs (opcional).
3. Habilitar extensão (Nunchuk/MotionPlus) via escrita em registros.
4. Definir report mode (0x32 ou 0x36).
5. Iniciar loop de leitura.

> **Nota**: A habilitação da extensão envolve escrita em endereços de memória do Wiimote (comandos 0x16). O parser deve tratar o report de confirmação (0x22) para garantir sucesso.

## 5) Detecção e sincronização
### 5.1 Conexão direta sem pareamento
- Preferir tentativa de conexão direta ao entrar em modo de sincronização.
- Caso não seja possível (limitações do Windows), oferecer assistente de pareamento.

### 5.2 Assistente de pareamento
- GUI orientando o usuário a abrir Bluetooth Settings.
- Verificação periódica por HID a cada 2–3s.

### 5.3 Detecção automática de recursos
- Ao conectar, detectar sensores e extensões disponíveis:
  - **Acelerômetro**: sempre disponível (base)
  - **MotionPlus**: detectado via extensão
  - **IR**: detectado quando sensor bar presente e pontos IR visíveis
  - **Nunchuk**: detectado via extensão
- Sistema muda automaticamente entre modos:
  - **Acelerômetro** (padrão)
  - **Acelerômetro + IR**
  - **Acelerômetro + Giroscópio**
  - **Acelerômetro + Giroscópio + IR**

## 6) Driver Core
### 6.1 Estado interno
- `connected`: bool
- `control_enabled`: bool
- `auto_mode`: accel/accel+ir/accel+gyro/accel+gyro+ir (detectado automaticamente)
- `resources_detected`: dict com accel, gyro, ir, nunchuk (bool)
- `battery_level`: estimado
- `nunchuk_connected`: bool
- `motionplus_connected`: bool
- `ir_active`: bool
- `profile`: ativo

### 6.2 Calibração
- **Calibração simples**: captura baseline (offset) por N segundos e aplica correção contínua.
- Sem ajustes avançados ou perfil por usuário neste momento.

### 6.3 Filtros
- **Low-pass filter** para suavização.
- Parâmetros por eixo configuráveis.

## 7) Mouse Controller
- **Base**: acelerômetro sempre ativo para controle de movimento.
- **Complemento IR**: quando detectado, usa posição absoluta do IR para correção.
- **Complemento Giroscópio**: quando disponível, adiciona rotação ao cálculo do acelerômetro.
- **Modo completo**: combina acelerômetro + giroscópio + IR com pesos configuráveis.
- Sensibilidade por eixo para cada componente (accel_sensitivity, gyro_sensitivity, ir_sensitivity).
- Opção de "auto-center".
- Limite de velocidade do cursor.
- Detecção automática de qual combinação usar baseado em recursos disponíveis.

## 8) Mapping Engine
- Mapeamento via `config.ini`.
- Ações suportadas:
  - mouse: `left_click`, `right_click`, `middle_click`, `scroll_up`, `scroll_down`, `drag_toggle`
  - teclado: `key:A`, `key:CTRL+ALT+DEL`
  - sistema: `toggle_control`, `center_mouse`, `profile_next`, `profile_prev`

## 9) UI (tkinter)
- Status de conexão, bateria, **modo automático ativo**, recursos detectados.
- Indicadores visuais: Acelerômetro (sempre), MotionPlus (se detectado), IR (se ativo), Nunchuk (se conectado).
- Botões: Start/Stop, Calibrar, Configurações Avançadas.
- **Tela de Configurações Avançadas**: 
  - Ajuste de sensibilidades (accel, gyro, IR)
  - Mapeamento de botões
  - Parâmetros de filtros
  - Calibração manual
  - Pesos de combinação (quando múltiplos recursos ativos)
- Assistente de pareamento usando APIs do Windows via `pywin32`.
- Debug info mostrando valores de sensores e modo automático atual.
- Logs apenas em console.

## 10) Configuração (config.ini)
Exemplo:
```
[General]
auto_mode_enabled = true
auto_center = true
profile = default

[Sensitivity]
accel_sensitivity = 25
gyro_sensitivity = 30
ir_sensitivity = 40
smoothing = 5

[Profiles]
active = default
list = default, gaming, media

[ButtonMapping]
A = left_click
B = right_click
One = toggle_control
Two = center_mouse
Plus = profile_next
Minus = profile_prev

[NunchukMapping]
C = left_click
Z = right_click
StickUp = scroll_up
StickDown = scroll_down
```

## 11) Testes
- **Unitários**: parser de protocolo, bitmasks, conversões.
- **Integração**: leitura HID mockada.
- **Manual**: conexão real, latência, drift.

## 12) Critérios de qualidade
- Latência < 25 ms.
- Reconexão automática em até 3s.
- Baixo uso de CPU.

## 13) Riscos técnicos
- Inconsistência de dados do MotionPlus.
- Instabilidade de Bluetooth.
- Permissões do Windows para HID.

## 14) Decisões consolidadas
- HID: **hidapi** via wrapper **`hid`**.
- IR: suportado apenas como **fallback opcional**.
- Calibração: **simples** (baseline/offset).
- Pareamento: **assistente integrado** com APIs do Windows via `pywin32`.