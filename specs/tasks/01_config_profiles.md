# Tarefa 01 — Configuração e Perfis

## Objetivo
Consolidar o formato do config.ini, leitura/escrita e suporte a múltiplos perfis com troca rápida.

## Escopo
- Definir schema final do config.ini.
- Implementar loader/saver de configuração.
- Implementar seleção de perfil ativo e troca rápida.

## Arquivos candidatos
- src/config.py
- config.ini

## Entregáveis
- Funções de leitura/escrita com validação básica.
- Perfis suportados e troca por comando.

## Critérios de aceitação
- `config.ini` parseia sem erro.
- Troca de perfil atualiza parâmetros efetivos.
- Config padrão gerada quando ausente.
