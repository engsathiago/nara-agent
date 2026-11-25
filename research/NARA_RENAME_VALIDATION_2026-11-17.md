# Nara validação da identidade e da especificação

Data: 17 de novembro de 2026. Branch local: `codex/nara-identity`.

O projeto foi movido de `/Users/fate/Desktop/Athena 2.0` para `/Users/fate/Desktop/Nara`.
A identidade atual usa Nara, comando `nara`, pacotes `nara_*`, variáveis `NARA_*`, serviços e
interfaces com o mesmo nome. O wordmark do terminal e o banner gráfico do site usam Nara; o
bitmap Hermes original fica em `research/upstream-assets/` como referência histórica. Referências externas, atribuições e evidências históricas preservam
suas identidades reais.

## Dados e recuperação

O estado foi movido para `~/.nara`. O alias temporário criado durante a migração foi removido em
22 de novembro de 2026; `~/.nara` é hoje o diretório real e único do estado ativo. Foram
atualizados 154 arquivos de skills, hooks e cron ativos. Conversas e memórias históricas não foram
reescritas.

O comando global `nara` aponta para o novo checkout. Os launchers temporários da identidade
intermediária foram retirados após backup. A instalação Athena antiga permanece independente.

Backup anterior à migração: `/Users/fate/.local/share/nara/migration-backups/2026-11-17/`.
Inclui fontes, patch do trabalho pré-existente, mapa de renomes e backup das skills/hooks/cron.

## Validação executada

| Verificação | Resultado |
| --- | --- |
| `nara --version` e `nara --help` | Executável e pasta nova confirmados, sem inferência de modelo |
| `nara pm lock` | Lock Python atual com o projeto renomeado |
| Instalação Node com lock congelado | Oito workspaces sincronizados |
| Sintaxe Python | 11.148 arquivos analisados sem erro |
| Contratos de identidade, perfis, comandos e wake word | 289 testes aprovados; 14 ignorados por plataforma |
| Política local existente e configuração/CLI de voz | Outros 52 testes aprovados |
| E-mail e identidade de versão após padronizar fixtures | Outros 61 testes aprovados |
| Desktop voz, captura, roteamento e identidade de build | 56 testes aprovados |
| Typecheck Desktop e TUI | Aprovados |
| Builds Desktop, TUI e Web | Aprovados |
| Datasheet e manifestos | Estrutura, tabelas, numeração, JSON e referências locais verificados |
| Guards de CI e lint Python | 13 guards aprovados e Ruff aprovado após ordenar um export renomeado |
| Lint JavaScript de todos os workspaces | Aprovado sem erros, com avisos não bloqueantes |
| `git diff --check` | Aprovado |

São 402 testes Python distintos e 56 testes Desktop nos conjuntos selecionados. As primeiras
asserções de rótulo do detector foram ajustadas ao comportamento correto de identificar o modelo
legado; a reexecução passou. O conjunto completo de testes do repositório não foi executado.

O ratchet global de complexidade (`scripts/check`, etapa `health`) foi interrompido por duração
excessiva na comparação de milhares de renomes. As demais 14 verificações selecionadas (guards e
Ruff) foram concluídas. Essa limitação permanece registrada; não equivale a uma execução integral
de CI aprovada. Imports e exports reordenados pelo lint foram seguidos por novos typechecks,
testes Desktop e builds das três interfaces.

Os builds locais emitiram avisos de bundling e de árvore Git com alterações durante a compilação;
não houve publicação nem geração de instalador assinado.

## Identidade acústica

O produto usa a frase “Ei, Nara”. O modelo acústico recebido da base foi retirado do caminho de
execução e preservado apenas em `research/upstream-assets/`, junto de seu manifesto, como evidência
histórica. O motor openWakeWord exige agora um arquivo `.tflite` configurado explicitamente e
treinado para Nara; sem ele, informa indisponibilidade e a ação corretiva em vez de fingir que a
frase nova foi reconhecida. O detector Nara ainda precisa de treino e benchmark acústico.

## Especificação consolidada

`NARA_DATASHEET.md` versão 1.2 registra nome, personalidade inicial, providers substituíveis,
primeira prova de voz, memória, prática, evolução e critérios de aceitação. As pesquisas anteriores
e o backlog foram incorporados à direção técnica. Segurança e políticas próprias permanecem em
etapa posterior separada, preservando o comportamento já existente nesta migração.

A conclusão desta entrega é a migração funcional de identidade e o fechamento da especificação.
As novas capacidades de autonomia, voz e aprendizado serão implementadas e promovidas por fase.

## Complemento de validação — 22 de novembro de 2026

O guard `scripts/check_product_identity.py` passou a bloquear regressões da identidade anterior
em superfícies ativas. As exceções são limitadas a procedência upstream, evidência de pesquisa,
nomes reais de dependências e URLs externas de plugins que precisam continuar instaláveis.

Não existe ainda repositório público, domínio, feed de atualização ou instalador publicado da
Nara. Endereços Nara presentes na base são contratos de publicação futura e não foram validados
como serviços remotos. O funcionamento confirmado nesta etapa é local; atualização e instalação
remotas só poderão ser promovidas depois que a infraestrutura própria for criada.
