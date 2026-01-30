# Tarefa 05 — Mapeamento de Ações + Controle de Mouse

## Objetivo
Traduzir eventos em ações de mouse/teclado e movimentar cursor.

## Escopo
- Engine de mapeamento de botões.
- Controle de cursor (delta, sensibilidade, smoothing).
- Ações de mouse e teclado.
- Consumo contínuo de eventos do loop HID (fila de eventos) para alimentar mapeamento e movimento.

## Arquivos candidatos
- src/mouse/mapping.py
- src/mouse/controller_driver.py

## Entregáveis
- Ações executáveis configuradas pelo config.ini.
- Cursor responsivo com MotionPlus.
- Integração do driver/mapeamento com a fila de eventos HID (leitura em thread) para processar pacotes em tempo real.

## Critérios de aceitação
- Cliques e movimentos funcionais e configuráveis.
- Loop principal do driver consome eventos da fila e aplica mapeamento sem travar.
