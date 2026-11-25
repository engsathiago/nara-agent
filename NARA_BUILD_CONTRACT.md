# Nara — contrato de construção integrada

> Identidade definitiva: **Nara**. A especificação consolidada está em
> [NARA_DATASHEET.md](NARA_DATASHEET.md), versão 1.2. Ela prevalece para fases,
> prioridades, seleção de componentes e critérios de entrega. A fundação de políticas
> versionadas está especificada em `docs/NARA_POLICY_SPEC.md`. Este documento detalha contratos.

## Objetivo deste documento

Este documento transforma a arquitetura-alvo em um contrato executável. Ele
define exatamente qual sistema será a origem de cada capacidade, o que será
reutilizado, adaptado ou reimplementado, onde a capacidade se conecta ao núcleo
novo e qual prova precisa passar antes de ser considerada parte da Nara.

A regra central é:

> Código presente não é capacidade entregue. Uma capacidade só existe quando
> pode ser acionada por uma superfície real, atravessa o mesmo runtime usado em
> produção, persiste o estado necessário, produz evidência observável e passa
> seu teste de aceitação de ponta a ponta.

O nome definitivo é Nara e a frase de ativação é “Ei, Nara”. O modelo acústico próprio
ainda precisa ser treinado e passar pela bancada de reconhecimento.

## Decisões que ficam congeladas

1. **Existe uma autoridade única de missão:** o núcleo Nara derivado da base upstream.
2. **Não será incorporado outro framework de agente inteiro.** EVE, Paperclip,
   Ruflo, CrewAI, LangGraph e projetos semelhantes são referências ou fontes de
   contratos, não runtimes paralelos. Infraestrutura durável pode servir a essa mesma autoridade.
3. **Não haverá um segundo banco para representar o mesmo estado.** Missão,
   tarefa, sessão, memória, artefato e trace terão autoridades explícitas.
4. **Plugins não podem contornar o núcleo.** Toda capacidade usa a API publicada
   de plugins, os hooks do runtime e os serviços compartilhados aprovados.
5. **A interface não antecipa o backend.** Um botão, comando ou painel só aparece
   como funcional quando o caminho real está integrado e verificado.
6. **Política e integridade são coisas diferentes.** A política comportamental
   será modular e controlada pelo projeto. Idempotência, autenticação, isolamento,
   trilhas de auditoria, limites de recursos e rollback são propriedades de
   confiabilidade e permanecem no mecanismo.
7. **Toda promoção é reversível.** Memória, skill, prompt, modelo, plugin e código
   guardam versão, motivo, métricas e caminho de rollback.

## Classificação obrigatória de capacidades

Cada capacidade terá exatamente um destes estados:

| Estado | Significado |
| --- | --- |
| `discovered` | Código ou ideia localizada, ainda não integrada. |
| `wired` | Ligada ao runtime e acionável por ao menos uma superfície real. |
| `verified` | Passou teste de comportamento e teste vertical com perfil temporário. |
| `operational` | Possui diagnóstico, observabilidade, recuperação e documentação. |
| `promoted` | Pode ser habilitada por padrão porque cumpriu as métricas acordadas. |

Somente `operational` ou `promoted` aparece na matriz pública de recursos. Uma
feature flag, uma classe ou uma tela isolada não altera esse estado.

## Arquitetura de autoridade

| Informação | Autoridade única |
| --- | --- |
| Conversa, turns e compactação | SessionDB e runtime atual do Nara |
| Tarefas executáveis e dependências | Kanban atual do Nara |
| Missão, contrato e event log | Mission Control plugin |
| Tool calls e efeitos observados | Receipt Store |
| Arquivos, saídas grandes e provas | Artifact Store endereçado por conteúdo |
| Memórias recuperáveis | `agent/memory_provider.py` e provider selecionado |
| Skills e procedimentos | sistema atual de skills e curator |
| Perfis de agentes e modelos disponíveis | Agent Registry + Model Capability Registry |
| Presença visual dos agentes | projeção somente leitura do estado de missão/worker |
| Traces, resultados e métricas | Experience Ledger + OpenTelemetry local |
| Variantes e promoções | Evolution Lab |
| Configuração | `config.yaml`; `.env` somente para segredos |

## Matriz exata de incorporação

### 1. Runtime e loop principal

- **Origem:** núcleo Nara novo.
- **Decisão:** reutilizar sem criar outro loop.
- **Componentes existentes:** `run_agent.py`, `agent/turn_*.py`, SessionDB,
  tool orchestration e gateway.
- **O que entra de fora:** nada no loop. Padrões externos entram por plugins,
  hooks, skills, providers ou serviços publicados.
- **Prova:** a mesma missão pode começar no CLI, ser observada no Desktop e
  continuar pelo gateway sem criar sessões lógicas concorrentes.

### 2. Mission Control

- **Origem funcional:** EVE Workboard/Mission Control, Paperclip e canais
  auditáveis do Buzz.
- **Substrato real:** Kanban, goals, scheduler e delegação já existentes no
  Nara.
- **Decisão:** reimplementar a camada de missão como plugin Python; não copiar o
  runtime TypeScript do EVE e não criar uma segunda fila de tarefas.
- **Aproveitar do EVE:** contrato de missão, projetos, claim atômico, heartbeat,
  proof, bloqueio, reatribuição, reclaim e visão operacional.
- **Aproveitar do Paperclip:** árvore objetivo-projeto-tarefa, orçamento por
  missão/agente, responsabilidades e histórico de mudanças.
- **Aproveitar do Buzz:** canal por projeto ou missão, membros humanos/agentes,
  repositório e artefatos vinculados, presença e audit log. O canal é uma
  projeção de comunicação; não cria uma segunda fila, missão ou autoridade.
- **Integração:** a missão cria e referencia tarefas no Kanban existente. Goals
  passam a representar o contrato da missão, não uma execução paralela.
- **Prova:** encerrar o processo em pontos predeterminados, reiniciar e concluir
  a missão sem repetir uma ação externa já confirmada.

### 3. Event log, recibos e artefatos

- **Origem funcional:** arquitetura event-sourced do OpenHands, Result Hub do
  EVE e compressão reversível do Headroom.
- **Decisão:** desenvolver contratos próprios e pequenos.
- **Reutilizar:** `agent/persisted_turn_receipt.py`,
  `tools/tool_result_storage.py`, referências de contexto e cards de artefato do
  Desktop onde forem semanticamente compatíveis.
- **Não fazer:** reutilizar o recibo de turn como recibo de efeito externo sem
  distinguir as duas coisas.
- **Receipt mínimo:** intenção, missão, tarefa, agente, ferramenta, alvo,
  idempotency key, horário, resultado observado, artefatos, erro, método de
  verificação e status da verificação.
- **Artifact mínimo:** hash, tipo, tamanho, produtor, missão, caminho físico ou
  URI, versão, metadados e política de retenção.
- **Prova:** uma saída grande sai do contexto, permanece recuperável por hash e
  o verificador consegue reconstruir a evidência original.

### 4. Equipe de agentes

- **Origem:** delegação atual do Nara, padrões de Codex/OpenAI Agents, Gemini
  subagents e organização visual do Paperclip.
- **Decisão:** reutilizar `tools/delegate_tool*.py`, `agent/managed_worker.py` e
  workers atuais; adaptar o dispatcher para consumir tarefas do Mission Control.
- **Não incorporar:** loops de CrewAI, Ruflo ou LangGraph.
- **Contrato do worker:** tarefa, critérios de conclusão, contexto mínimo,
  ferramentas, modelo, orçamento, deadline, formato de saída e lease.
- **Regras:** contexto isolado, claim atômico, heartbeat, cancelamento, limite de
  profundidade e resultado estruturado ligado à tarefa.
- **Execução distribuída:** cada host publica CPU, RAM, GPU/VRAM, SO,
  ferramentas, modelos, versões, capacidade livre e limite de concorrência. O
  dispatcher usa fila, lease, heartbeat, cancelamento, artifact handoff por hash
  e reclaim; descoberta de uma máquina não concede acesso automático aos seus
  arquivos ou segredos.
- **Prova:** três workers executam tarefas independentes em paralelo, uma queda
  faz o lease expirar, apenas um worker recupera a tarefa e a líder integra os
  três resultados sem duplicação.

### 5. Verificação independente

- **Origem:** contratos de conclusão existentes em goals, EVE proof e padrões de
  agentes de longa duração.
- **Decisão:** desenvolver um serviço de verificação ligado à missão.
- **Reutilizar:** `agent/verify/`, goal judge e ferramentas de leitura/teste.
- **Regra:** o relato do executor nunca é prova suficiente.
- **Saída de verificação:** `pass`, `fail` ou `inconclusive`, acompanhada de
  evidências.
- **Gate terminal:** quando um executor pede para encerrar, um juiz separado
  retorna `continue`, `complete` ou `impossible`. `complete` exige `pass` em
  todos os critérios; `impossible` exige causa verificável, alternativas
  tentadas e condição de retomada. O juiz pode ser barato em contratos
  determinísticos, mas não é a mesma instância que executou a tarefa.
- **Prova:** um executor que afirma sucesso sem produzir o arquivo ou estado
  esperado é recusado pelo verificador e a tarefa volta para correção.

### 6. Memória persistente

- **Origem:** interfaces atuais do Nara; conceitos temporais de Graphiti,
  organização de Letta e escopos de Mem0.
- **Decisão:** manter `agent/memory_provider.py` como única porta. Providers
  externos continuam substituíveis.
- **Desenvolver no provider local:** memória de trabalho, episódica, semântica,
  procedimental e reflexiva; proveniência; validade temporal; `supersedes`;
  explicação de recuperação e feedback de utilidade.
- **Não fazer:** copiar todas as mensagens para o prompt, tratar memória como
  instrução ou criar um banco separado por recurso.
- **Prova:** após reinício, recuperar uma decisão correta com sua fonte; depois
  registrar uma correção e impedir que o fato substituído seja apresentado como
  atual, mantendo o histórico consultável.

### 7. Contexto contínuo e compressão reversível

- **Origem:** compressor e Context Engine atuais; padrão CCR do Headroom e
  progressive disclosure do Claude-mem.
- **Decisão:** estender, não substituir.
- **Integração:** resultados grandes viram artefatos e referências pesquisáveis;
  a compactação mantém ponte para turn, recibo e artefato originais.
- **Prova:** uma missão ultrapassa várias janelas de contexto, é retomada após
  reinício e responde corretamente a uma pergunta que exige um detalhe removido
  do prompt ativo, recuperando o original.

### 8. Voz e palavra de ativação

- **Origem:** `tools/voice_mode.py`, `tools/voice_live.py`,
  `tools/wake_word*.py` e implementação Desktop já presente.
- **Decisão:** finalizar um caminho vertical existente antes de adicionar novos
  provedores.
- **Wake word:** local por padrão; nome configurável; modelo definitivo criado
  somente depois da escolha do nome.
- **Conversação:** provider interface com uma implementação principal e fallback
  em pipeline STT → agente → TTS. OpenAI Realtime, Grok Voice, LiveKit ou Pipecat
  entram como adapters, nunca como donos do estado da missão.
- **Reuniões:** padrões do Meetily/Parakeet podem entrar como plugin local de
  captura, diarização e resumo. A escolha de ASR depende de benchmark PT-BR no
  host real; números promocionais de velocidade não são critério de promoção.
- **Integração:** a voz envia turns para a mesma sessão do runtime. Workers podem
  continuar enquanto a interface de voz retorna atualizações curtas.
- **Prova:** acordar pelo nome, conversar em português, interromper a fala,
  solicitar uma missão, receber confirmação, acompanhar o progresso e retomar a
  mesma conversa após reconexão sem criar uma missão duplicada.

### 9. Controle do computador e navegador

- **Origem:** computer use, browser tools e Cua já presentes; padrões do Browser
  Use, Playwright, `vercel-labs/agent-browser`, `agent-desktop`, Baguette e
  CLI-Anything.
- **Decisão:** reutilizar e adicionar um Capability Router; atualizar adapters
  individualmente quando necessário.
- **Ordem obrigatória:** API/MCP → arquivos/terminal → DOM/CDP → acessibilidade →
  visão/coordenadas.
- **Registro de capacidade:** disponibilidade, alvo, custo, latência,
  cancelamento, idempotência e método de verificação.
- **Adapters candidatos:** browser local por DOM/CDP/acessibilidade, browser
  isolado, Electron, simulador iOS e, depois, Android. Baguette é candidato para
  iOS e `agent-browser` para navegação compacta por refs; ambos permanecem
  `discovered` até smoke test e comparação com o caminho atual.
- **Prova:** uma missão combina terminal e navegador, confirma o estado após cada
  escrita e consegue retomar depois que o navegador é encerrado no meio.

### 10. Agenda, autonomia e disponibilidade contínua

- **Origem:** gateway, cron, heartbeat e scheduler atuais.
- **Decisão:** reutilizar. O sistema será dirigido por eventos e jobs; não haverá
  um LLM preso em loop infinito para parecer online.
- **Integração:** launchd/supervisor mantém gateway e scheduler; Mission Control
  acorda workers somente quando existe trabalho, prazo, evento ou recuperação.
- **Prova:** missão agendada executa após reinício da máquina, respeita timezone,
  não dispara duas vezes e registra o motivo de cada wake-up.

### 11. Model gateway e roteamento

- **Origem:** providers e router existentes; fallback do OmniRoute e roteamento
  observado do EVE.
- **Decisão:** estender o router atual.
- **Regras:** modelo fica fixo durante uma sessão; seleção acontece na criação do
  worker ou nova sessão; provider é substituível; roteamento usa capacidade,
  custo, latência e sucesso verificado.
- **Camadas funcionais:** classificador local/modelo pequeno para intenção,
  prioridade e seleção de skill; modelo rápido para busca e leitura; modelo
  executor para construir e testar; modelo forte independente para arquitetura,
  crítica e julgamento terminal. Os nomes dos modelos não são fixados no código.
- **System 1 opcional:** classificadores como Laya podem emitir decisões tipadas
  de baixo risco. Precisam de benchmark próprio em PT-BR, confidence calibration
  e fallback; não geram planos, conteúdo ou aprovação final.
- **Fallback:** modelos locais e remotos são diagnosticados antes de serem
  anunciados como disponíveis.
- **Prova:** falha controlada do provedor aciona fallback compatível sem perder o
  estado da missão; o resultado registra qual modelo foi usado e por quê.

### 12. Protocolos de integração

- **MCP:** ferramentas, recursos, prompts, skills, apps e operações longas.
- **A2A:** agentes remotos opacos e tarefas delegadas entre instalações.
- **Integração:** aproveitar o suporte MCP e o plugin A2A já presentes, elevando
  ambos pelos contratos de missão, receipts e traces.
- **Prova:** uma tarefa remota sobrevive à desconexão, retorna um handle durável,
  entrega artefatos verificáveis e não recebe acesso implícito à memória interna.

### 13. Observabilidade e Experience Ledger

- **Origem:** hooks/resultados do EVE Intelligence, OpenTelemetry GenAI e
  Langfuse como visualizador opcional.
- **Decisão:** reimplementar o ledger no ecossistema Python e emitir convenções
  OpenTelemetry. Exportação externa permanece opt-in; armazenamento local é a
  fonte para evolução.
- **Capturar:** missão, agente, modelo, ferramenta, latência, tokens, custo,
  retries, falhas, artefatos, verificação, intervenção humana e feedback.
- **Não capturar por padrão:** conteúdo sensível integral de prompts ou arquivos.
- **Prova:** selecionar uma missão no Desktop e navegar da conclusão até cada
  task, turn, tool call, artefato, custo e decisão de verificação.

### 14. Evals e Evolution Lab

- **Origem:** EVE eval suite como esqueleto; Promptfoo para campanhas externas;
  GEPA/DSPy para otimização; Agent Lightning apenas como pesquisa futura.
- **Decisão:** desenvolver o Evolution Lab sobre o Experience Ledger.
- **Ordem de mudança automática:** memória → skill → prompt/configuração →
  roteamento → plugin/código → modelo.
- **Gates:** dataset versionado, baseline, variante isolada, critérios mínimos,
  regressões, custo, canário, promoção e rollback.
- **Código:** mudanças são produzidas em branch/worktree isolado e nunca aplicadas
  diretamente na instalação ativa.
- **Prova:** uma falha real vira fixture; uma variante corrige a fixture sem
  regredir o conjunto existente; a variante é promovida em canário e revertida
  automaticamente quando uma regressão injetada aparece.

### 15. Skills e catálogo de especialistas

- **Origem:** sistema atual de skills; Legião-Local como catálogo; conceitos de
  skills verificadas da Anthropic/NVIDIA.
- **Decisão:** converter agentes úteis da Legião em templates ou skills nativos,
  um por vez, quando houver missão consumidora.
- **Admissão:** origem, licença, hash, análise, teste, eval, versão e rollback.
- **Prova:** uma skill recém-admitida melhora a métrica da tarefa alvo, não muda
  o prompt de uma sessão em andamento e pode ser desabilitada sem quebrar o
  runtime.

### 15.1 Learning Fabric multimodal

- **Origem:** pipeline `/watch` do `bradautomates/claude-video`, transcrição
  local com Whisper/MLX, quadros por FFmpeg e a auditoria real de 84 salvos em
  `research/INSTAGRAM_SAVED_AI_AUDIT_2026-11-16.md`.
- **Decisão:** desenvolver ingestão multimodal própria; não instalar o projeto
  de referência como parte do core.
- **Pipeline:** adquirir temporariamente → hash/metadados → transcrição com
  timestamps → cenas/OCR → fusão fala/tela/legenda → afirmações → fontes
  primárias → proposta de memória/skill/experimento/descarte.
- **Gates:** análise nunca instala pacotes nem ativa skills; conteúdo externo não
  concede autoridade; cada proposta carrega fonte, licença, versão, evidência,
  eval, risco e rollback.
- **Persistência:** a mídia original é temporária por padrão. O ledger retém URL,
  hash, timestamps, quadros estritamente necessários, resultados e decisão.
- **Aprendizagem ativa:** uma fonte pode gerar explicação, perguntas, exercícios
  e fixtures, inspiradas no OpenMAIC e nos cursos de Agents/Context da Hugging
  Face. A avaliação usa questões não presentes no contexto de estudo; repetir um
  resumo não conta como aprendizado.
- **Prova:** um Reel em português com nome do repositório apenas na tela é
  transcrito, tem o projeto identificado por quadro/OCR, é conferido na fonte
  oficial e produz uma skill candidata que permanece inativa até passar no eval.
  Em seguida, um teste separado demonstra ou rejeita a transferência do
  procedimento para um caso novo.

### 16. Interface Desktop e identidade visual

- **Origem funcional:** Desktop atual, EVE Mission Control e Paperclip.
- **Origem visual:** JARVIS apenas como referência de presença, waveform e
  estado; não incorporar seu runtime.
- **Decisão:** evoluir a aplicação Desktop existente.
- **Telas:** conversa/voz, missão, equipe, tarefas, artefatos, memória, agenda,
  traces, custos, avaliações e evolução.
- **Canais:** uma missão ou projeto pode ser vista como canal com participantes,
  repositórios, mensagens, tarefas e artefatos. Todos os elementos apontam para
  as autoridades existentes; o canal não possui estado operacional paralelo.
- **Regra:** cada indicador vem de um endpoint real; nenhum número demonstrativo
  entra na interface de produção.
- **Prova:** a mesma missão observada no CLI aparece ao vivo no Desktop, permite
  cancelar/retomar e mostra evidência final consistente com o banco.

### 17. Módulo central de política

- **Origem:** será especificado pelo projeto depois de estabilizar os mecanismos
  de autoridade, receipts e verificação.
- **Decisão:** um único Policy Decision Point com adapters por superfície e
  capacidade; nenhuma regra comportamental espalhada em ferramentas.
- **Separação:** policy decide autoridade; mecanismos continuam responsáveis por
  consistência, segredos, concorrência, idempotência, isolamento e recuperação.
- **Prova:** a mesma decisão é aplicada de forma idêntica no CLI, voz, gateway,
  subagente e execução remota, com versão e explicação registradas.

### 18. Agent Factory e equipe multi-modelo

- **Origem:** delegação atual do Nara; padrões de agentes como ferramentas do
  OpenAI Agents SDK; subagentes isolados do Gemini; organização do Paperclip.
- **Decisão:** desenvolver um Agent Registry e uma Agent Factory sobre o sistema
  atual de delegação, sem criar outro loop de execução.
- **Agente principal:** mantém a missão, o plano, o inventário global de
  capacidades, o orçamento e a responsabilidade pelo resultado final. Ele pode
  executar diretamente ou contratar agentes especializados.
- **Perfis persistentes:** especialistas com nome, papel e histórico próprios,
  por exemplo Pesquisa, Código, Desktop, Auditoria, Memória ou nomes definidos
  pelo produto como Sol e Lua.
- **Workers efêmeros:** agentes criados somente para uma subtarefa e encerrados
  depois da entrega.
- **Agent Profile:** identidade, papel, prompt, modelo/provider, ferramentas,
  MCPs, skills, escopo de memória, orçamento, deadline, limites e contrato de
  saída.
- **Model Capability Registry:** registra modelos locais e cloud disponíveis em
  Ollama e demais providers, contexto, modalidades, tool use, latência, custo,
  disponibilidade e desempenho verificado por categoria de tarefa.
- **Seleção inicial:** requisitos da tarefa eliminam modelos incompatíveis; o
  router escolhe entre os restantes usando resultados históricos, custo e
  latência.
- **Aprendizado:** o Experience Ledger atualiza a competência observada de cada
  combinação agente-modelo-ferramenta por domínio. Exploração controlada compara
  alternativas; exploração nunca substitui todos os workers de uma missão ao
  mesmo tempo.
- **Autoridade:** o líder conhece todas as APIs e capacidades registradas, mas o
  worker recebe somente o subconjunto necessário para sua tarefa. A limitação
  evita interferência entre agentes e melhora a confiabilidade; não cria um
  segundo sistema de políticas.
- **Ciclo de vida:** criar → registrar → atribuir lease → executar → heartbeat →
  entregar → verificar → atualizar reputação → hibernar ou encerrar.
- **Prova:** uma missão de pesquisa e implementação cria três especialistas com
  modelos diferentes, cada um recebe ferramentas distintas, o router explica as
  escolhas, o verificador mede os resultados e a missão seguinte melhora a
  alocação com base nos resultados anteriores.

### 19. Escritório visual de agentes

- **Origem visual:** interfaces de virtual office vistas em projetos multi-agent,
  Mission Control do EVE, organização do Paperclip e linguagem visual do JARVIS.
- **Decisão:** incorporar ao Desktop como uma visualização do estado real, nunca
  como runtime ou simulação independente.
- **Fonte dos dados:** Mission Control, WorkerLease, heartbeat, receipts, traces,
  artifacts e Model Capability Registry.
- **Estados visuais canônicos:** `idle`, `planning`, `working`, `waiting`,
  `verifying`, `blocked`, `completed`, `failed` e `offline`.
- **Ambientes:** sala da líder, pesquisa, desenvolvimento, navegador/desktop,
  verificação, memória/evolução e fila de espera. As salas são filtros visuais;
  não alteram o local real de execução.
- **Cada agente mostra:** nome, papel, modelo, tarefa, duração, custo, estado,
  ferramenta atual, último heartbeat e bloqueio.
- **Interação:** clicar abre missão, contexto concedido, logs, receipts,
  artefatos, consumo e ações permitidas como pausar, cancelar, reatribuir ou
  conversar com o agente.
- **Representação:** pode existir em modo 2D animado, organograma, lista ou mapa
  de dependências. Todos consomem o mesmo event stream e exibem a mesma verdade.
- **Desempenho:** animação roda apenas na interface; fechar o escritório não
  interrompe workers. O backend continua funcional sem Desktop aberto.
- **Prova:** durante uma missão multiagente, cada transição visual corresponde a
  um evento persistido; matar um worker muda sua presença para `offline`, o
  reclaim aparece ao vivo e outro agente assume exatamente a mesma tarefa.

## O que não será incorporado

| Projeto/componente | Decisão |
| --- | --- |
| EVE completo | Não. Portar contratos de Workboard e Intelligence sobre o runtime novo. |
| Projeto legado completo | Não. Usar somente como fonte de casos, comportamento e módulos comprováveis. |
| CrewAI/Ruflo/LangGraph como runtime | Não. Evitar segundo loop, segunda memória e segunda fila. |
| AutoGen | Não adotar; projeto arquivado. |
| JARVIS Kit | Somente referência visual e de ativação. |
| Ovi | Fora do escopo de voz conversacional. |
| `agent_kit` | Somente checklist histórico. |
| Memória externa obrigatória | Não. Providers externos são opcionais e substituíveis. |
| Telemetria externa obrigatória | Não. Exportação sempre opt-in. |

## Gates de entrega

Uma fase só começa depois que o gate anterior está verde no perfil temporário,
no CLI e em pelo menos uma superfície persistente real.

### Gate 0 — baseline confiável

- instalação limpa e comando `nara` funcionando;
- identidade anterior removida das superfícies do produto;
- testes bloqueantes da base verdes;
- inventário de recursos com status real;
- fixture de missão longa definida antes de modificar o runtime.

### Gate 1 — missão que sobrevive

- Mission Control, event log, tasks, receipts e artifacts mínimos;
- kill/restart em cada transição importante;
- nenhuma duplicação de efeitos confirmados;
- verificador independente conclui a fixture.

### Gate 2 — operação observável

- Experience Ledger local;
- árvore missão → task → agent → turn → tool → artifact;
- custo, erros, retries e intervenções visíveis;
- diagnóstico e retenção.

### Gate 3 — equipe real

- dispatcher sobre delegação existente;
- claims, leases, heartbeats, cancelamento e recuperação;
- execução paralela e síntese estruturada;
- orçamento por missão e worker;
- Agent Factory e Model Capability Registry;
- seleção explicável de modelos diferentes por tarefa;
- escritório visual refletindo o estado real dos workers.

### Gate 4 — contexto e memória comprovados

- artefatos endereçados por conteúdo;
- compactação reversível;
- memória temporal com proveniência e correção;
- benchmark de recuperação e de continuidade.

### Gate 5 — acesso integral verificável

- Capability Registry e Router;
- terminal, browser, desktop e execução remota;
- confirmação pós-ação e retomada após falhas;
- ambientes isolados para tarefas de risco técnico.

### Gate 6 — voz integrada

- wake word local;
- português full-duplex e barge-in;
- mesma sessão e mesma missão das outras superfícies;
- reconexão, fallback e indicadores de microfone.

### Gate 7 — evolução automática

- datasets de regressão reais;
- criação automática de candidatos;
- eval comparativo, canário, promoção e rollback;
- evolução de skill/prompt/roteamento antes de autoalteração de código.

## Definição de pronto global

Uma entrega só recebe `operational` quando todos os itens abaixo forem verdadeiros:

1. Possui consumidor real no CLI, Desktop, gateway, voz ou scheduler.
2. O consumidor usa o mesmo caminho de produção, sem mocks ocultando integração.
3. Possui teste de comportamento focado.
4. Possui teste vertical com `NARA_HOME` temporário.
5. Persiste e retoma o estado que promete preservar.
6. Emite traces, recibos e artefatos suficientes para explicar o resultado.
7. Possui doctor/status que distingue disponível, degradado e indisponível.
8. Falhas são visíveis e acionáveis; não são convertidas silenciosamente em sucesso.
9. Possui limite, cancelamento e limpeza de recursos.
10. Possui documentação de operação e caminho de rollback.
11. Foi executada manualmente uma vez em ambiente real suportado.
12. A matriz pública é atualizada a partir da evidência, não da existência do código.

## Regras contra regressões do projeto legado

- Não contar classes, arquivos, plugins instalados ou flags como funcionalidades.
- Não manter comandos que retornam estruturas vazias como se fossem produtos.
- Não criar dashboard antes do endpoint e do banco estarem operacionais.
- Não duplicar missão, tarefa, sessão ou memória em subsistemas diferentes.
- Não adicionar provider sem doctor probe e teste real de chamada.
- Não habilitar adaptação sem baseline e candidatos configurados.
- Não acumular resultados sem triagem, retenção, artefatos e estado terminal.
- Não permitir que o mesmo agente execute e aprove sua própria conclusão.
- Não promover skill criada pelo agente sem replay ou fixture.
- Não iniciar a próxima fase com dívida conhecida no gate anterior.

## Primeiros pacotes de implementação

### WP-00 — baseline e scorecard

Entregar o inventário executável de capacidades, o runner da fixture de missão
longa e o relatório inicial de disponibilidade. Nenhuma nova funcionalidade.

### WP-01 — contratos de missão

Definir schemas versionados para Mission, MissionEvent, Receipt, Artifact,
Verification e WorkerLease, com migração e invariantes.

### WP-02 — Mission Store e projeção

Implementar event log append-only, projeção transacional, idempotency keys e
reconstrução integral do estado.

### WP-03 — ponte para Kanban e goals

Fazer a missão criar, observar e retomar tarefas no Kanban atual; adaptar goals
para contrato de conclusão sem criar outro loop.

### WP-04 — receipts e artifacts

Instrumentar o caminho real de tool execution, armazenar saídas grandes por hash
e ligar evidências ao verificador.

### WP-05 — fixture de continuidade

Executar a missão de aceitação com encerramentos forçados, reinício, subagente,
arquivo, browser simulado/real controlado e relatório verificado.

Somente quando WP-05 estiver verde começa o Experience Ledger e o restante do
roadmap. Assim o primeiro resultado do projeto não será uma coleção maior de
componentes, mas uma prova de que o núcleo novo consegue realmente trabalhar,
falhar, retomar e terminar.
