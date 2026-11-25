# Nara base técnica

Nome definitivo: **Nara**. Projeto: `/Users/fate/Desktop/Nara`. Comandos: `nara`, `nara-agent` e
`nara-acp`. Pacotes e módulos: `nara_*`. Variáveis: `NARA_*`. Serviços: `nara-gateway`,
`nara-serve` e `nara-dashboard`; namespace local `ai.nara.*`.

A base deriva do projeto upstream v0.23.1, congelado no commit
`3b421578588243f920886e6fe79a6faa87ea026e`. A atribuição fica isolada em
`UPSTREAM_PROVENANCE.md`. Nara é um projeto separado da instalação legada.

## Uso

```bash
cd /Users/fate/Desktop/Nara
source ./activate
nara --version
nara
```

O launcher global `nara` aponta para este projeto. Estado no macOS/Linux: `~/.nara`.
Não há alias de estado ou comando para a identidade intermediária do projeto. O comando legado
antigo e seu estado não são alterados por esta migração.

## Especificação e implementação

[NARA_DATASHEET.md](NARA_DATASHEET.md), versão 1.2, é a especificação consolidada. O contrato e o
roteiro detalham continuidade, voz, memória, competências e Evolution Lab com provas por fase.
O LLM de raciocínio permanece separado, via providers substituíveis.

“Ei, Nara” é a frase de ativação definida. O detector próprio está pendente de treino e benchmark.
Um detector externo preservado para pesquisa não é carregado pelo runtime Nara.

A política local existente continua centralizada em `nara_agent/nara_security.py`, ligada por
`agent/nara_security_bridge.py`. Esta migração altera a identidade, não as decisões de política.
O trabalho separado de segurança e políticas próprias permanece na fase posterior do datasheet.

## Recuperação e validação

Backup anterior à migração: `/Users/fate/.local/share/nara/migration-backups/2026-11-17/`.
O backup contém fontes, mapa de renomes e patch do trabalho que já existia antes desta alteração.

Resultados dos checks: [relatório de validação](research/NARA_RENAME_VALIDATION_2026-11-17.md).
