# Auditoria dos perfis de IA do Instagram para Nara

Data: 2026-11-16
Perfis únicos analisados: [`@fabianocarvalhojr`](https://www.instagram.com/fabianocarvalhojr/) e
[`@eduardocavalcanti`](https://www.instagram.com/eduardocavalcanti/)
Escopo observado: 119 publicações de Fabiano + 120 de Eduardo = 239 publicações

## Conclusão executiva

Os quatro links enviados continham somente dois perfis únicos. A coleta excedeu as 100
publicações pedidas em cada perfil. As legendas das 239 publicações foram triadas e 33 vídeos
relevantes ou ambíguos tiveram o áudio transcrito localmente. Repositórios e alegações que
alterariam a arquitetura foram conferidos em fontes primárias.

O material traz boas descobertas, mas não muda a fundação já escolhida. Ele reforça que o
Nara deve continuar com um único runtime e ganhar capacidades pelas bordas. As novidades de
maior valor são:

1. **Conclusão terminal julgada por outro modelo:** uma missão longa não termina porque o
   executor disse que terminou. Um juiz independente decide entre continuar, concluir ou declarar
   impossibilidade comprovada.
2. **Roteamento em três camadas:** modelo pequeno/classificador para triagem e recuperação,
   modelo executor para construir e testar, e modelo forte independente para arquitetura e
   revisão.
3. **Operação distribuída de verdade:** workers em várias máquinas precisam de inventário de
   capacidade, fila, lease, heartbeat, limite de concorrência, artifact handoff e recuperação.
4. **Interfaces estruturadas antes de visão:** árvore de acessibilidade/DOM para navegador,
   Accessibility tree para aplicativos e simulador iOS controlável para testes móveis.
5. **Learning Fabric ativo:** além de extrair conteúdo de vídeos, transformar material em aula,
   perguntas, exercícios e evals para provar que o agente aprendeu.
6. **Canais de trabalho auditáveis:** cada projeto pode ter um canal com agentes, repositório,
   artefatos, permissões e histórico, sem criar uma segunda fila ou um segundo runtime.

## Como a análise foi feita

- A grade virtualizada de cada perfil foi percorrida até obter 119 e 120 URLs únicas.
- Legendas foram classificadas em agente/core, automação, voz, mídia, design, domínio vertical,
  marketing, trade ou assunto sem relação com Nara.
- 33 vídeos selecionados tiveram o áudio baixado temporariamente e transcrito com MLX Whisper
  Large V3 Turbo em português.
- Nomes, números e alegações úteis foram comparados com repositórios, documentação e páginas
  oficiais.
- Nenhuma curtida, comentário, mensagem, follow, compartilhamento, instalação ou alteração na
  conta do Instagram foi feita.

### Escala de evidência

| Nível | Significado |
| --- | --- |
| Confirmado | Repositório ou documentação primária confirma a capacidade. |
| Parcial | A base existe, mas o Reel mistura capacidade atual, benchmark próprio ou roadmap. |
| Demonstração | O vídeo mostra um happy path, sem provar recuperação, custo ou confiabilidade. |
| Alegação | Não foi possível ligar a promessa a evidência primária suficiente. |

## Qualidade dos dois perfis

### `@fabianocarvalhojr`

É o melhor dos dois como **radar de repositórios, skills e ferramentas novas**. Encontramos boa
densidade de projetos técnicos: MCPs, roteadores, memória, browser automation, skills de design,
vídeo, jogos e modelos locais. A fraqueza é a embalagem de marketing: muitos posts usam CTA para
comentário/direct, números sem contexto e expressões como “grátis”, “mata X” ou “faz sozinho”.

Uso recomendado: fonte de candidatos para o Learning Fabric, nunca fonte final de decisão.

### `@eduardocavalcanti`

É melhor em **casos operacionais, composição de ferramentas e visão de negócio**. Os posts sobre
Advisor, Buzz, múltiplos Macs, Hermes/OpenClaw, Baguette, Laya e navegador estruturado ajudam a
pensar a operação. Ele também costuma reconhecer custo de hardware e limitações. Ainda assim,
parte do conteúdo promove produtos próprios ou apresenta demonstração como prova de produção.

Uso recomendado: fonte de padrões de operação e UX; alegações sobre “melhor agente” ou escala
precisam de benchmark independente.

## Achados de prioridade alta

| Projeto/conceito | Evidência encontrada | Decisão para Nara |
| --- | --- | --- |
| [`vercel-labs/agent-browser`](https://github.com/vercel-labs/agent-browser) | CLI Rust que abre páginas, retorna árvore de acessibilidade compacta com refs e mantém sessão. Possui skills e execução em sandbox | **Prototipar como adapter de navegador.** Comparar com Cua, Playwright e `agent-desktop`; escolher por tarefa, sem substituir o Capability Router |
| [`tddworks/baguette`](https://github.com/tddworks/baguette) | Controle headless de simuladores Apple, taps, swipes, gestos, streaming e device farm | **Adicionar adapter iOS experimental.** Testar app real, Accessibility tree, logs, screenshots e retomada antes de promover |
| [`NandhaKishorM/laya`](https://github.com/NandhaKishorM/laya) | Classificador não autorregressivo para decisões tipadas; o README declara 33 ms em T4 e 100+ idiomas, com limitações documentadas de idioma e carregamento | **Avaliar como System 1 opcional.** Somente triagem, classificação, scoring e roteamento; nunca planejamento, escrita ou verificação final |
| [`vzwjustin/advisor`](https://github.com/vzwjustin/advisor) | Time em camadas: exploradores baratos, executores intermediários e estrategista/revisor forte | **Incorporar o padrão**, não o runtime: pesquisa barata → execução → revisão independente, registrando por que cada modelo foi escolhido |
| [`block/buzz`](https://github.com/block/buzz) | Canais/workspaces com agentes, integração MCP/ACP, serviços de presença, busca e audit log encadeado | **Adaptar a UX de canal por missão/projeto** no Mission Control. Não adotar outro chat, banco ou scheduler |
| comando `/goal` com juiz | Padrão observado: condição de pronto persiste e um segundo modelo avalia cada tentativa de parada | **Transformar em gate terminal do Mission Control:** `continue`, `complete`, `impossible`; só `complete` após evidência, e `impossible` exige causa verificável |
| [`Zackriya-Solutions/meetily`](https://github.com/Zackriya-Solutions/meetily) | Assistente local de reunião com Whisper/Parakeet, diarização e resumo; o post confundiu comparação de velocidade e escopo já entregue | **Reaproveitar padrões de captura e transcrição local** para Voice/Meeting plugin; benchmark PT-BR na máquina antes de escolher ASR |
| [`THU-MAIC/OpenMAIC`](https://github.com/THU-MAIC/OpenMAIC) | Transforma assunto/documentos em aula multiagente, slides, quizzes, simulações e PBL | **Adaptar o ciclo pedagógico** ao Learning Fabric: estudar → explicar → perguntar → testar → corrigir. Não incorporar o runtime completo |
| [Hugging Face Agents Course](https://huggingface.co/learn/agents-course/en/unit0/introduction) e [Context Course](https://huggingface.co/learn/context-course/en/unit0/introduction) | Cursos oficiais com fundamentos, tool use, MCP, skills, subagentes, observabilidade, evals e desafio GAIA | **Usar como currículo de eval**, não dependência. Converter exercícios relevantes em fixtures versionadas do Nara |

## O que muda na arquitetura

### 1. Gate terminal independente

O verificador atual já exige evidência, mas falta tornar explícita a decisão de parada:

```text
executor pede conclusão
  -> juiz recebe objetivo, contrato, artefatos e evidências
  -> continue: há trabalho observável restante
  -> complete: todos os critérios foram provados
  -> impossible: bloqueio estrutural foi provado e alternativas foram esgotadas
```

O juiz não deve receber a conclusão do executor como fato. Para reduzir custo, pode ser um modelo
menor quando o contrato for determinístico; tarefas subjetivas ou de alto impacto usam um modelo
mais forte ou revisão humana.

### 2. Router por função, não por prestígio do modelo

O padrão do Advisor e a proposta do Laya sugerem quatro funções distintas:

| Função | Camada indicada |
| --- | --- |
| Classificar, priorizar, detectar intenção, escolher skill | classificador local ou modelo pequeno |
| Buscar, ler, indexar e resumir evidência | modelo rápido e barato |
| Implementar, operar ferramentas e testar | modelo executor escolhido por capacidade |
| Projetar, criticar e julgar conclusão | modelo forte e independente do executor |

O Nara não deve codificar nomes fixos como Haiku/Sonnet/Opus. O Model Capability Registry
escolhe equivalentes disponíveis em Ollama, OpenAI, Anthropic, Google ou outro provider usando
benchmark observado.

### 3. Workers em múltiplas máquinas

Os vídeos de produção em vários Macs mostram um fluxo plausível, não uma arquitetura confiável.
Para entregar isso de verdade, cada host precisa publicar:

- CPU, RAM, GPU/VRAM, SO, ferramentas, modelos e versões;
- capacidade livre e limite de jobs concorrentes;
- heartbeat, fila local e handles de processos;
- acesso ao Artifact Store por hash, sem copiar todo o contexto;
- custo, temperatura, falhas e tempo estimado;
- lease renovável, cancelamento e reclaim depois de queda;
- teste de compatibilidade antes de receber uma tarefa.

### 4. Browser e mobile como adapters

`agent-browser` e Baguette confirmam a mesma direção do contrato: estrutura antes de pixels.
O Nara deve registrar adapters separados para browser local, browser isolado, Electron,
simulador iOS e, futuramente, Android. A decisão permanece no Capability Router.

## Achados úteis como plugins ou skills

### Mídia e design

| Projeto | Uso possível | Decisão |
| --- | --- | --- |
| [`Tejashmakwana/motionmaxxing`](https://github.com/Tejashmakwana/motionmaxxing) | Skill de motion design com captura de marca, timing medido e inspeção do render | **Skill candidata** do pipeline de vídeo, depois de eval visual e licença |
| [`benjitaylor/skills`](https://github.com/benjitaylor/skills) | `stageshow` para UI fictícia, cards e demonstrações de produto em React | **Skill de apresentação**, não guideline universal de produto |
| [`gamedev-skills/awesome-gamedev-agent-skills`](https://github.com/gamedev-skills/awesome-gamedev-agent-skills) | 79 skills e router que carrega só 2–3 por tarefa/engine | **Adotar o padrão de catálogo sob demanda.** Não carregar dezenas de skills no prompt |
| [`JuneYaooo/rea-video`](https://github.com/JuneYaooo/rea-video) | Decompõe vídeo por plano e distingue filmado, IA ou código | **Referência para o Learning Fabric multimodal**, comparada ao pipeline já projetado |
| [`Leonxlnx/earshot`](https://github.com/Leonxlnx/earshot) | Análise e crítica de áudio local para agentes | **Adapter opcional de verificação de áudio** |
| [`wyzowl/sfx-kit`](https://github.com/wyzowl/sfx-kit) | 320 efeitos sonoros CC0 com metadados para seleção e mixagem | **Biblioteca candidata**, preservando origem e licença por arquivo |
| [`ekcheungAI/foley-skill`](https://github.com/ekcheungAI/foley-skill) | Openverse + Earshot + FFmpeg para sincronizar efeitos e gerar relatório | **Bom contrato de pipeline**, mas validação humana continua necessária |
| [`meituan-longcat/LongCat-Video`](https://github.com/meituan-longcat/LongCat-Video) | Avatar falante local a partir de áudio/imagem | **Plugin futuro de avatar**, não parte da voz central; custo de GPU deve ser medido |

### Domínios verticais

| Projeto | Uso possível | Decisão |
| --- | --- | --- |
| [`pascalorg/editor`](https://github.com/pascalorg/editor) | Editor BIM/arquitetura com CLI e MCP | **Plugin de arquitetura**, caso exista missão real; não core |
| [`BenchUp3D/editor`](https://github.com/BenchUp3D/editor) | Modelagem 3D/woodworking em Rust/WASM, importação `.skp`, medições e testes | **Plugin CAD/marcenaria** depois de prova com arquivo real |
| [`emidio-trancoso/advocacia-aberta`](https://github.com/emidio-trancoso/advocacia-aberta) | 10 protocolos, base jurídica com súmulas, temas e procedência | **Fonte de padrões para plugin jurídico**, nunca conhecimento universal embutido no core; legislação exige atualização e revisão profissional |
| [Model Hardware Standard](https://www.anthropic.com/news/model-hardware-standard-research-preview) | Interface comum para instrumentos de laboratório e orquestração física | **Referência para typed device adapters**. Fora do escopo inicial e sempre com controles específicos do domínio físico |

## Achados para observar, não incorporar agora

- **LongCat Avatar:** tecnicamente real, mas pede GPU forte e não melhora a autonomia central.
- **Pascal, BenchUp e ArtCraft:** ferramentas úteis para tarefas específicas; agregá-las ao core
  aumentaria dependências e superfície sem consumidor imediato.
- **Universal Modder/REA:** bons procedimentos de investigação e verificação quando há autorização,
  mas não justificam clonar produtos ou contornar licenças. O padrão útil é evidência → hipótese →
  experimento reversível → prova.
- **Laya:** números publicados pelo próprio projeto precisam ser reproduzidos em PT-BR e no host
  local. Classificação errada e confiante é um risco documentado pelo próprio README.
- **Advisor:** o desenho em camadas é excelente; os modelos específicos e os ganhos promocionais
  não devem ser congelados no código.
- **Buzz:** é um produto completo e grande. Copiá-lo criaria exatamente o segundo runtime/estado
  que o contrato proíbe.
- **Vídeos com 66 estilos e fábricas de conteúdo:** úteis como catálogo criativo, mas qualidade,
  direitos de mídia, custo e repetibilidade precisam de evals por artefato.

## Conteúdo que deve ser descartado como base do Nara

- trade autônomo, promessas de rendimento e agentes que operam dinheiro sem ledger e autoridade;
- “grátis” sem contabilizar GPU, APIs, tempo, licenças e manutenção;
- engenharia reversa apresentada como permissão para copiar software de terceiros;
- crescimento de rede social, comentários e mensagens automáticas sem autorização explícita;
- compra autônoma por agentes ou x402 antes de orçamento, identidade, recibo e reversão;
- pacotes com centenas de skills carregadas permanentemente;
- comparação de ferramenta baseada somente em estrelas, vídeo curto ou opinião do criador;
- “auto-evolução” que modifica a instalação ativa sem baseline, canário e rollback.

## Novidades em relação à auditoria anterior dos salvos

Já estavam cobertos: Paperclip, Foreman, GBrain, LLMfit, PersonaPlex, Superpowers,
`agent-desktop`, memória contínua, Learning Fabric e a regra de não incorporar outro framework.

Esta auditoria acrescenta de forma material:

1. gate terminal explícito `continue/complete/impossible`;
2. classificador System 1 opcional antes do LLM gerador;
3. roteamento em camadas inspirado no Advisor;
4. canais auditáveis inspirados no Buzz;
5. `agent-browser` como candidato de browser estruturado;
6. Baguette como adapter de testes iOS;
7. currículo ativo e evals inspirados em OpenMAIC/Hugging Face;
8. requisitos concretos para uma frota de workers em múltiplas máquinas;
9. pipeline de verificação de áudio e som com Earshot/SFX Kit;
10. plugins verticais mantidos fora do core.

## Ordem recomendada

1. Entregar o Mission Control e a retomada já definidos.
2. Acrescentar o gate terminal independente ao teste de aceitação.
3. Tornar o Model Capability Registry capaz de separar classificador, pesquisador, executor e
   juiz.
4. Implementar host registry, capacity queue, lease e artifact handoff antes de distribuir jobs.
5. Fazer um benchmark isolado de `agent-browser` contra o adapter existente.
6. Fazer um smoke test isolado do Baguette em um app iOS de fixture.
7. Transformar uma unidade do curso Hugging Face e uma aula OpenMAIC em fixtures do Learning
   Fabric.
8. Só depois avaliar Laya, Meetily, Earshot e skills de mídia como plugins opcionais.

## Critérios de aceitação novos

- Uma missão não conclui se o segundo juiz devolver `continue`.
- `impossible` exige evidência do bloqueio e registro das alternativas tentadas.
- O router explica a escolha de modelo e registra custo, latência e resultado verificado.
- Um worker remoto pode cair e ser substituído sem duplicar uma ação externa.
- Browser e simulador móvel produzem refs/árvore e uma observação posterior à escrita.
- Uma skill descoberta em Reel permanece `discovered` até passar licença, sandbox, eval e
  rollback.
- Uma aula gerada só conta como aprendizado quando o agente resolve um teste que não recebeu no
  contexto de estudo.

## Resultado final da curadoria

### Incorporar ao contrato agora

- gate terminal independente;
- modelo router em camadas;
- host/capacity registry para workers remotos;
- canais por missão como projeção do Mission Control;
- browser/mobile adapters estruturados;
- aprendizagem ativa com avaliação separada.

### Prototipar depois da Fase 1

- `agent-browser`;
- Baguette;
- Laya;
- Meetily/Parakeet em PT-BR;
- OpenMAIC como gerador de currículo;
- Earshot/SFX Kit para mídia.

### Somente como plugins sob demanda

- LongCat Avatar;
- MotionMaxxing e Stageshow;
- Pascal, BenchUp e Advocacia Aberta;
- skills de jogos e de produção de vídeo.

### Não incorporar

- outro runtime completo;
- evolução irrestrita da instalação ativa;
- compra, trade, publicação ou contato externo autônomo sem autoridade explícita;
- cópia de software ou mídia de terceiros sem autorização e licença compatível.
