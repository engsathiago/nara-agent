# Nara

Agente pessoal persistente, com ferramentas, memória e execução multimodelo. A base deriva de um
projeto upstream MIT, com procedência e atribuição preservadas em
[UPSTREAM_PROVENANCE.md](UPSTREAM_PROVENANCE.md). Nara mantém o LLM de raciocínio separado e
substituível por provider.

A especificação do produto está fechada em [NARA_DATASHEET.md](NARA_DATASHEET.md), versão 1.2.
A base e a identidade estão implementadas; as novas capacidades são entregues por fases e provas.

## Executar localmente

```bash
cd /Users/fate/Desktop/Nara
source ./activate
nara --version
nara
```

O comando global `nara` também aponta para este checkout. Estado por perfil: `~/.nara` no
macOS/Linux e `%LOCALAPPDATA%\nara` no Windows. O estado anterior foi preservado na migração.

## Construção do produto

1. Continuidade, efeitos observados e verificação independente.
2. Primeira experiência por voz junto da autonomia.
3. Memória e aprendizado entre sessões, estudo ativo e evolução avaliada.
4. Equipes, frota, voz avançada e escritório visual conforme os gates.
5. Segurança e políticas próprias em etapa posterior separada.

“Ei, Nara” é a frase escolhida. O detector acústico próprio ainda precisa ser treinado e validado;
o runtime exige um modelo explícito e não reutiliza um detector de outra identidade.

## Documentação

- [Especificação consolidada](NARA_DATASHEET.md)
- [Base técnica e uso](NARA.md)
- [Contrato de construção](NARA_BUILD_CONTRACT.md)
- [Arquitetura de evolução](NARA_EVOLUTION.md)
- [Auditoria de voz, autonomia e aprendizado](research/AUDITORIA_VOZ_AUTONOMIA_APRENDIZADO_2026-11-17.md)
- [Validação da migração](research/NARA_RENAME_VALIDATION_2026-11-17.md)

Bibliotecas, modelos, vozes e conteúdos externos mantêm suas identidades e licenças. Repositório
público, domínio, instaladores assinados e feed de atualização próprios serão preparados na fase
de distribuição; URLs herdadas não representam uma publicação oficial da Nara.
