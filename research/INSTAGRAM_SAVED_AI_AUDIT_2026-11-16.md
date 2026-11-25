# Auditoria dos salvos do Instagram para Nara

Data: 2026-11-16
Conta analisada: `@engsathiago`
Escopo observado: 84 publicações salvas

## Conclusão executiva

Os salvos contêm material útil, mas misturam demonstrações reais, projetos ainda
experimentais, produtos comerciais, marketing com números inflados e conteúdo pessoal.
O melhor caminho para Nara não é instalar tudo. É incorporar os contratos e as ideias
que sobreviveram à verificação, atrás de plugins e skills, com testes de resultado.

As cinco adições de maior valor são:

1. **Learning Fabric multimodal:** vídeo ou áudio entra, é transcrito localmente, quadros são
   analisados, afirmações são ligadas a fontes primárias, e somente então nasce uma proposta de
   memória, skill ou experimento.
2. **Mission Control multiagente:** hierarquia, tarefas duráveis, orçamento e heartbeats do
   Paperclip, combinados com as estações verificáveis do Foreman.
3. **Memória com procedência:** fatos, correções, retirada e compartilhamento inspirado no
   GBrain, sem criar agora um segundo sistema de memória concorrente.
4. **Autoconsciência operacional:** orçamento de contexto, checkpoints e capacidade real do
   host inspirados no Agent Aware, sem permitir que o agente crie infraestrutura por conta
   própria só porque encontrou uma credencial configurada.
5. **Computer use por acessibilidade:** API/MCP primeiro, árvore de acessibilidade em seguida,
   visão por último, seguindo o desenho do `agent-desktop`.

## Como a análise foi feita

- A grade virtualizada do Instagram foi percorrida até formar a união de 84 URLs únicas.
- Todas as legendas disponíveis foram lidas e classificadas.
- 33 vídeos de IA, automação ou tecnologia tiveram o áudio baixado temporariamente e
  transcrito localmente com `yt-dlp`, FFmpeg e MLX Whisper.
- Para os vídeos em que o nome do projeto aparecia apenas na tela, foram extraídos quadros e
  montadas folhas de contato.
- Repositórios e alegações técnicas importantes foram conferidos em fontes oficiais.
- Nenhuma curtida, comentário, mensagem, compartilhamento ou instalação foi feita.

### Níveis de evidência

- **Confirmado:** repositório ou documentação primária conferida.
- **Demonstração:** o vídeo mostra um fluxo, mas não prova confiabilidade ou qualidade.
- **Alegação:** foi dito pelo criador do Reel; falta prova independente.
- **Descartar como base:** marketing, risco desnecessário ou ausência de evidência operacional.

## Decisão por projeto relevante

| Projeto ou tema | O que o vídeo ensina | Verificação | Decisão para Nara |
|---|---|---|---|
| [bradautomates/claude-video](https://github.com/bradautomates/claude-video) | `/watch`: baixa vídeo, extrai quadros e transcreve | Confirmado; o projeto existe e suporta Claude/Codex. Há issues reais sobre FFmpeg recente, idiomas e alucinação do Whisper | **Adaptar**, não copiar integralmente. Criar pipeline nosso, local, testado em PT-BR |
| [paperclipai/paperclip](https://github.com/paperclipai/paperclip) | Empresa de agentes com CEO, gestores, workers, metas, dashboard e orçamento | Confirmado; budgets, hierarquia e heartbeats estão documentados | **Adotar conceitos** no Mission Control; não substituir o core Hermes/Nara |
| [Vercel Foreman](https://github.com/vercel-labs/eve-software-factory-template) | Ticket passa por classificador, analista, implementador e revisor | Confirmado; template oficial da Vercel | **Adaptar o pipeline de estações** e o revisor independente |
| [garrytan/gbrain](https://github.com/garrytan/gbrain) | Memória compartilhada entre Claude, Codex e Hermes com fonte e correções | Confirmado; também documenta fronteiras de privacidade e captura opt-in | **Incorporar o contrato de procedência** à memória atual; avaliar integração opcional depois |
| [walidboulanouar/agent-aware](https://github.com/walidboulanouar/agent-aware) | Context budget, checkpoint pulse e divisão de trabalho | Confirmado, porém projeto muito pequeno; a história de provisionar Hetzner sozinho não é prova do pacote | **Reimplementar só os mecanismos simples** de contexto e checkpoint |
| [vercel-labs/agent-desktop](https://github.com/vercel-labs/agent-desktop) | Controle de apps por árvore de acessibilidade, com CLI/MCP | Confirmado; não contém modelo e retorna refs acionáveis | **Adotar como adapter opcional** depois de prova E2E em macOS/Windows |
| [obra/superpowers](https://github.com/obra/superpowers) | Metodologia de brainstorming, plano, TDD, depuração e verificação | Confirmado e maduro | **Curar um subconjunto**; não carregar todas as skills em todo turn |
| [affaan-m/ECC](https://github.com/affaan-m/ECC) | 71 agentes, 314 skills e 98 comandos | Contagens e grande adoção confirmadas; é um ecossistema grande, não um único “superagente” | **Usar como catálogo de padrões**, importando somente itens avaliados |
| [GoogleChrome/modern-web-guidance](https://github.com/GoogleChrome/modern-web-guidance) | Atualiza agentes com práticas web modernas e evals | Confirmado; suporta Codex e busca local | **Adotar como skill de desenvolvimento web**, com telemetria desativável |
| [AlexsJones/llmfit](https://github.com/AlexsJones/llmfit) | Detecta hardware, estima fit e mede tokens/s | Confirmado; `bench` separa estimativa de medição | **Integrar ao Model Registry** como diagnóstico, nunca como verdade sem benchmark |
| [anomalyco/rune](https://github.com/anomalyco/rune) | UI Rust/GPU, modo headless, PNG, árvore de elementos e input roteirizado | Confirmado, mas pre-release | **Observar e prototipar isoladamente**; não reescrever o Desktop agora |
| [openfilm/openfilm](https://github.com/openfilm/openfilm) | Agente de vídeo com editor real e exportação | Confirmado; projeto ativo e MIT | **Plugin opcional de mídia**, após provar render, edição e exportação E2E |
| [NVIDIA/personaplex](https://github.com/NVIDIA/personaplex) | Voz duplex em tempo real com personalidade | Confirmado; requer infraestrutura/modelo adequado | **Pesquisa para voz avançada**; MVP continua Whisper/Piper ou APIs substituíveis |
| [lcsmotta7/trunk-and-branches-isaque-2](https://github.com/lcsmotta7/trunk-and-branches-isaque-2) | Qwen 4B congelado com colunas DoRA/O-LoRA e roteamento | Monografia e artefatos existem; poucos usuários e pouca validação externa | **Experimento de laboratório**, não base do aprendizado contínuo |
| [666ghj/MiroFish](https://github.com/666ghj/MiroFish) | População sintética de agentes para testar ideias | Repositório real; não há prova de que personagens sintéticos preveem clientes reais | **Usar como ideação adversarial**, nunca como validação de mercado |
| [Gathin23/cleanyourtv](https://github.com/Gathin23/cleanyourtv) | ADB, backup, desativação reversível de bloat e launcher | Confirmado; não remove permanentemente e possui restore | **Skill de dispositivo separada**, somente por modelo e com confirmação |
| [devlikeapro/waha](https://github.com/devlikeapro/waha) | API HTTP para múltiplas sessões de WhatsApp | Projeto real, mas a postagem promove atraso aleatório para evitar bloqueio | **Não usar evasão de bloqueio**; priorizar API oficial e uso transacional |
| [Google Maps Scraper Kit](https://github.com/herbertcarnaubadesouza/google-maps-claude-kit-sales) | Extrai leads do Google Maps para CSV/Excel | Repositório real, pequeno; Reel promete substituir marketing | **Não incorporar no core**; eventual plugin deve respeitar termos, privacidade e uso legítimo |
| [ashhart/OpenBOT](https://github.com/ashhart/OpenBOT) | Interface local que reúne CLIs como Claude, Codex e OpenCode | Reimplementação real, muito inicial | **Extrair ideias de UI e backend**, não trocar Nara por ele |

## O que os vídeos realmente ensinaram

### Agentes, memória e autonomia

- A “Sexta-Feira” demonstra wake name, memória, controle de Windows, Spotify e navegador.
  A ideia boa é uma interface de voz sempre disponível sobre o mesmo runtime; a demonstração
  não prova recuperação, segurança, idempotência ou funcionamento prolongado.
- Agent Aware mostra que o agente precisa conhecer contexto restante, ferramentas e recursos.
  O correto é expor capacidades declaradas e medidas, não permitir descoberta oportunista de
  contas e credenciais.
- Foreman e Paperclip reforçam a mesma conclusão: autonomia confiável depende de tickets,
  critério de pronto, workers com papéis claros, orçamento, revisão e auditoria.
- GBrain traz o melhor padrão de memória encontrado: fatos com fonte, correção, retirada,
  separação entre memória durável e estado temporário, e compartilhamento explícito.
- ECC prova que catálogos grandes são úteis, mas também mostra o risco de contexto permanente,
  hooks e comandos demais. Nara deve carregar catálogo leve e corpo sob demanda.

### Aprender assistindo

O pipeline correto não é “vi um vídeo, virou skill”. Deve ser:

```text
URL/arquivo
  -> aquisição temporária
  -> hash e metadados
  -> transcrição local com timestamps
  -> seleção de cenas + OCR
  -> fusão fala/tela/legenda
  -> extração de afirmações e nomes
  -> busca das fontes primárias
  -> classificação de evidência e risco
  -> proposta: memória, skill, experimento ou descarte
  -> eval isolado
  -> aprovação/promoção/rollback
```

Cada saída deve guardar:

- URL e data de observação;
- trechos com timestamp, sem copiar mídia permanentemente por padrão;
- quadros usados como evidência;
- nomes e links confirmados;
- afirmações conflitantes;
- licença e atividade do projeto;
- custo, dependências e permissões;
- decisão `adopt`, `adapt`, `watch` ou `discard`;
- eval que precisa passar antes da promoção.

### Voz e presença contínua

A Atlas local mostrou uma arquitetura simples e plausível: Qwen/llama.cpp, Whisper, Piper,
serviços separados, Rust como coordenador e Flutter como cliente. Para Nara:

- wake word local e barato;
- VAD e streaming;
- ASR/TTS trocáveis;
- interrupção da fala;
- sessão de voz ligada à mesma conversa durável;
- câmera e reconhecimento facial separados e opt-in;
- nenhum dado biométrico na memória geral;
- confirmação explícita antes de ações externas relevantes.

PersonaPlex deve ser avaliado depois como modo full-duplex, não como pré-requisito do MVP.

### Modelos e autoevolução

- LLMfit ajuda a escolher modelos possíveis, mas a seleção final precisa de benchmark local.
- “Trunk and Branches” é pesquisa de fine-tuning modular, não substitui memória, evals ou
  promoção controlada.
- BitNet, Colibri e motores de offload são alternativas de serving. Não tornam automaticamente
  um modelo grande rápido ou bom; capacidade de armazenamento não é throughput utilizável.
- WhiteRabbitNeo/Deep Hat não é política de segurança. Um modelo sem recusas não substitui
  autorização, escopo, auditoria, validação de argumentos ou limites operacionais.

## Alegações que não devem entrar no projeto como fatos

- Estrelas do GitHub provam interesse, não confiabilidade.
- “Autoconsciente” significa introspecção programada, não consciência.
- Milhares de agentes sintéticos não equivalem a clientes reais.
- Um modelo caber no disco/RAM não significa que terá velocidade útil.
- “Open source” não significa grátis para operar; APIs, GPU, voz, vídeo e hospedagem custam.
- Um vídeo de interface não prova recuperação após falha, cancelamento ou resultado correto.
- Backtest e simulação de trade não garantem retorno e não autorizam execução financeira.
- Scraping gratuito não elimina aquisição de clientes e pode violar termos ou privacidade.
- Evasão de bloqueio do WhatsApp não é uma capacidade aceitável para o agente.

## Atualização proposta para o contrato de Nara

### Novo módulo: Learning Fabric

Responsabilidades:

1. `media-ingest`: URL/arquivo, cache temporário, hash, licença e descarte.
2. `asr`: Whisper/MLX local por padrão; provider remoto opcional.
3. `vision-sampler`: cortes de cena, OCR e quadros sob orçamento.
4. `claim-extractor`: projetos, comandos, números e promessas.
5. `source-verifier`: documentação, GitHub, paper e licença.
6. `knowledge-proposal`: memória/skill/experimento/descarte.
7. `skill-lab`: sandbox, testes, custo, risco, canário e rollback.
8. `learning-ledger`: evidência completa e decisão humana.

### Gates mínimos

- Nenhum pacote é instalado durante a análise.
- Nenhuma skill aprendida ganha execução automática sem eval.
- Conteúdo de terceiros nunca concede permissão.
- Ação financeira, credencial, publicação e modificação externa continuam em gates separados.
- Aprendizado não pode reescrever o core ativo; produz branch/plugin/skill candidata.
- Toda promoção inclui rollback e versão da fonte.

## Ordem recomendada de implementação

1. Criar o contrato `LearningArtifact` e o ledger local.
2. Implementar ingestão de vídeo local com o mesmo caso real usado nesta auditoria.
3. Acrescentar transcrição com timestamps, cenas e OCR.
4. Implementar verificador de fontes e licença.
5. Produzir propostas de skill sem instalação.
6. Conectar propostas ao Evolution Lab e aos evals.
7. Adicionar Mission Control com tickets, orçamento e worker receipts.
8. Integrar contexto/checkpoints do Agent Aware.
9. Criar wake word + voz sobre a mesma sessão.
10. Só então avaliar promoção automática de mudanças de baixo risco.

## Resultado da curadoria

### Adotar primeiro

- `claude-video` como referência do pipeline, reimplementado e corrigido para PT-BR;
- Paperclip + Foreman para Mission Control;
- GBrain para o contrato de memória;
- Superpowers e Modern Web Guidance como skills selecionadas;
- LLMfit para diagnóstico do Model Registry;
- `agent-desktop` como adapter de acessibilidade.

### Adaptar depois

- OpenFilm, PersonaPlex, Rune, CleanYourTV, MiroFish e OpenBOT.

### Somente observar

- Trunk and Branches, Colibri/offload extremo, Deep Hat e ferramentas comerciais de geração.

### Não incorporar

- trade autônomo;
- disparo em massa ou evasão de bloqueio;
- scraping sem contrato de uso legítimo;
- criação espontânea de infraestrutura usando credenciais encontradas;
- instalação automática de tudo que aparece em Reel.
