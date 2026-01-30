# Tarefa 02 — Conexão HID + Loop de Leitura

## Objetivo
Criar camada de conexão HID estável com thread de leitura e fila de eventos.

## Escopo
- Descoberta e abertura do dispositivo.
- Loop de leitura em thread com timeout.
- Emissão de eventos brutos.

## Arquivos candidatos
- src/wiimote/connection.py
- src/wiimote/driver.py

## Entregáveis
- Classe de conexão HID.
- Thread de leitura + fila/buffer.

## Critérios de aceitação
- Conecta e lê pacotes sem travar.
- Reconhece desconexão e finaliza thread.
