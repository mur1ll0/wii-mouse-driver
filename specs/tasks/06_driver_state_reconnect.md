# Tarefa 06 — Estado do Driver + Reconexão

## Objetivo
Gerenciar estado interno e reconexão automática.

## Escopo
- Estado `connected`, `control_enabled`, `profile`.
- Reconexão automática com backoff.
- Fallback de modo (gyro → accel → IR opcional).

## Arquivos candidatos
- src/wiimote/driver.py
- src/wiimote/connection.py

## Entregáveis
- State machine do driver.
- Estratégia de reconexão robusta.

## Critérios de aceitação
- Reconecta após perda de sinal.
- Mantém estado consistente.
