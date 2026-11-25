# Nara

Agente pessoal persistente, com ferramentas, memória e execução multimodelo. A base deriva de um
projeto upstream MIT, com procedência e atribuição preservadas em
[UPSTREAM_PROVENANCE.md](UPSTREAM_PROVENANCE.md). Nara mantém o LLM de raciocínio separado e
substituível por provider.

A especificação do produto está em [NARA_DATASHEET.md](NARA_DATASHEET.md), versão 1.2.
O núcleo e os módulos locais foram implementados e validados; os gates que exigem
hardware, contas externas e VPS são documentados separadamente.

## Executar localmente

```bash
git clone https://github.com/engsathiago/nara-agent.git
cd nara-agent
source ./activate
nara --version
nara
```

O comando global `nara` pode ser instalado para apontar a este checkout. Estado por perfil:
`~/.nara` no macOS/Linux e `%LOCALAPPDATA%\nara` no Windows.
Instalações de código-fonte seguem `main` por padrão. O canal `stable` será habilitado
quando houver uma release versionada publicada neste repositório.

## Construção do produto

1. Continuidade, efeitos observados e verificação independente.
2. Primeira experiência por voz junto da autonomia.
3. Memória e aprendizado entre sessões, estudo ativo e evolução avaliada.
4. Equipes, frota, voz avançada e escritório visual conforme os gates.
5. Políticas próprias centralizadas no PDP; o perfil inicial é `observe_only` e novas regras
   exigem promoção explícita.

“Ei, Nara” é a frase escolhida. O detector acústico próprio ainda precisa ser treinado e validado;
o runtime exige um modelo explícito e não reutiliza um detector de outra identidade.

## Documentação

- [Especificação consolidada](NARA_DATASHEET.md)
- [Base técnica e uso](NARA.md)
- [Contrato de construção](NARA_BUILD_CONTRACT.md)
- [Arquitetura de evolução](NARA_EVOLUTION.md)
- [Auditoria de voz, autonomia e aprendizado](research/AUDITORIA_VOZ_AUTONOMIA_APRENDIZADO_2026-11-17.md)
- [Validação da migração](research/NARA_RENAME_VALIDATION_2026-11-17.md)
- [Publicação pública e validação local](research/NARA_PUBLICATION_2026-11-25.md)

Bibliotecas, modelos, vozes e conteúdos externos mantêm suas identidades e licenças. Este é o
repositório público da Nara. Domínio, instaladores assinados e feed de atualização próprios
dependem da fase de distribuição; URLs herdadas não representam uma publicação oficial da Nara.
