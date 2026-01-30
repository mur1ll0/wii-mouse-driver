# Tarefa 04 — Calibração e Filtros

## Objetivo
Implementar calibração simples (baseline/offset) e filtros de suavização.

## Escopo
- Calibração de gyro e acelerômetro.
- Low-pass filter configurável.

## Arquivos candidatos
- src/wiimote/driver.py
- src/mouse/filters.py

## Entregáveis
- Função `calibrate()`.
- Filtros aplicados nos dados de sensores.

## Critérios de aceitação
- Redução de drift perceptível.
- Parâmetros configuráveis via config.ini.
