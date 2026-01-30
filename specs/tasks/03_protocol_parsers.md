# Tarefa 03 — Parser de Protocolo (Botões + Sensores)

## Objetivo
Implementar o parser dos reports HID para botões, acelerômetro, MotionPlus e Nunchuk.

## Escopo
- Bitmask de botões.
- Acelerômetro (X/Y/Z).
- MotionPlus (yaw/pitch/roll).
- Nunchuk (stick + botões).

## Arquivos candidatos
- src/wiimote/protocol.py

## Entregáveis
- Funções de parse para cada report type.
- Eventos semânticos padronizados.

## Critérios de aceitação
- Dados convertidos corretamente (com testes unitários).
