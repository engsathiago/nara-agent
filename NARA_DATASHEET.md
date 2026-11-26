# Nara — Especificação consolidada do produto

Versão do documento: 1.3
Data: 2026-11-23
Estado: implementação local consolidada; capacidades externas continuam condicionadas aos seus gates
Nome definitivo: **Nara**
Comando: `nara`
Frase de ativação do produto: **“Ei, Nara”**, com detector próprio ainda a treinar e validar

## 1. Resumo do produto

Nara é uma agente pessoal autônoma, persistente e multimodelo. Ela conversa por
texto e voz, opera o computador, navega na internet, cria equipes temporárias de agentes,
trabalha durante horas ou dias, recupera-se de interrupções, verifica os próprios resultados e
transforma experiências comprovadas em memória, skills e melhorias versionadas.

Não será apenas um chatbot com muitas ferramentas. O produto será organizado ao redor de
**missões duráveis**:

> A pessoa entrega um objetivo. A Nara define o que significa terminar, planeja, escolhe os
> agentes e modelos, executa, observa o resultado, corrige falhas, comprova a conclusão e guarda o
> que aprendeu para a próxima missão.

O diferencial pretendido não é possuir uma função que nenhum outro projeto tenha. É integrar as
melhores funções sob uma única autoridade de missão, com memória compartilhada, execução
durável e provas reais de funcionamento.

**Prioridade desta revisão:** registrar a aceitação local de execução, retomada, aprendizado,
evolução, equipes, frota local, voz lógica, escritório visual, laboratórios e políticas. As próximas
promoções dependem de dataset acústico, VPS, credenciais, contas ou dados futuros e não são
simuladas pela implementação local.

“Aprender” terá três significados explícitos:

1. **Factual:** reter, recuperar e corrigir fatos com fonte.
2. **Procedimental:** extrair procedimentos, testá-los em tarefas novas e reutilizá-los.
3. **Evolutivo:** comparar mudanças no sistema e promover somente melhorias demonstradas.

Alterar pesos do modelo é uma linha futura de treinamento, distinta de memória, skills e
otimização de prompts. Não é requisito para a primeira autonomia útil. Acesso amplo será feito
por adapters observáveis; a competência será medida por tarefa, sem promessa de “fazer tudo”.

## 2. Ficha técnica resumida

| Item | Definição |
| --- | --- |
| Categoria | Agente pessoal autônomo e plataforma local de agentes |
| Base técnica | Projeto upstream MIT v0.23.1, congelado no commit `3b421578588243f920886e6fe79a6faa87ea026e`; procedência em `UPSTREAM_PROVENANCE.md` |
| Projeto local | `/Users/fate/Desktop/Nara` |
| Identidade atual | Nara |
| Comando principal | `nara` |
| Versão local da base observada | base v0.23.1 mais a linha Nara publicada em `engsathiago/nara-agent`; manifesto limpo fixa cada release por commit e SHA-256 |
| Licença da base | MIT |
| Runtime principal | Python 3.14 |
| Desktop | Electron/TypeScript |
| Interfaces | CLI/TUI, Desktop, Web e gateways de mensagens |
| Estado local | `~/.nara` no macOS/Linux e `%LOCALAPPDATA%\nara` no Windows |
| Modelos | Qwen 3.5 4B local via Ollama como baseline validado; modelos locais ou cloud continuam substituíveis por provider |
| Protocolos | MCP, ACP e A2A onde aplicável |
| Extensão | Plugins, skills, adapters e serviços opcionais |
| Política atual | PDP Nara `default-observe-only-v1`, sem regras adicionais de recusa; limites do LLM/provedor continuam existindo |
| Palavra de ativação | “Ei, Nara”; modelo acústico próprio pendente de treino e avaliação |
| Política futura | Novas regras entram somente por versão staged, promoção explícita e rollback no módulo central já implementado |
| Prioridade de construção | Continuidade → aprendizado entre sessões → estudo ativo → evolução → escala → interfaces |
| Publicação | Repositório e documentação Pages públicos em `github.com/engsathiago/nara-agent` e `engsathiago.github.io/nara-agent/docs/`; instalador de fonte disponível; instalador assinado e feed próprio ainda pendentes |

## 3. Estado de implementação registrado

A fundação abaixo deriva da base registrada na versão 0.1. A identidade técnica foi migrada para
Nara: pasta, executáveis, pacotes, imports, variáveis, serviços e superfícies. As verificações da
migração ficam em `research/NARA_RENAME_VALIDATION_2026-11-17.md`. Em 23 de novembro de 2026, os
pacotes de autonomia, memória, aprendizado, evolução, especialistas, frota local, voz lógica,
Nara Office, laboratórios, política e recuperação passaram pela aceitação local descrita nesta
seção. Gates que dependem de hardware, dados, credenciais ou infraestrutura externa permanecem
explicitamente separados.

### 3.1 Concluído na fundação

- projeto separado da instalação legada;
- base upstream v0.23.1 preservada como núcleo;
- renomeação de produto, pacotes, executáveis, diretórios e variáveis para Nara;
- comando local `nara` funcionando no ambiente do checkout;
- Qwen 3.5 4B local respondendo via Ollama com contexto configurado em 64 mil tokens e chamada real
  da ferramenta `nara_policy_status` confirmada no loop completo do agente;
- gateway instalado como serviço de usuário do macOS, supervisionado por `launchd`, com início no
  login e reinício automático após falha;
- dados isolados no namespace `~/.nara`;
- identidade consolidada em `/Users/fate/Desktop/Nara`, comando `nara` e namespace `NARA_*`;
- migração do estado para `~/.nara`, com o alias temporário de compatibilidade já removido;
- política local concentrada em `nara_agent/nara_security.py`;
- ponte única de política em `agent/nara_security_bridge.py`;
- modo local inicial permissivo, posteriormente centralizado no PDP versionado em `observe_only`;
- CLI/TUI, Desktop, gateways, ferramentas, plugins, skills, cron, memória e delegação herdados da
  base;
- plugin oficial REA 0.2.0 instalado e habilitado em `~/.nara/plugins/rea`, com servidor MCP
  `rea-agents@6.7.0` inicializado e 207 ferramentas enumeradas;
- Ghidra 12.1.4 e JDK 21 detectados pelo REA para análise nativa; Hopper, IDA, JADX e Kuna permanecem
  engines opcionais não configurados;
- documentação de arquitetura evolutiva, contrato de construção e pesquisas de mercado.

### 3.2 Disponível na base, mas ainda não promovido como diferencial Nara

Essas capacidades possuem código ou interfaces herdadas. Elas precisarão de testes verticais no
produto novo antes de serem anunciadas como prontas:

- conversa no terminal e no Desktop;
- seleção de providers e modelos;
- execução de terminal, arquivos, navegador e computer use;
- gateways para Telegram, Discord, Slack, WhatsApp, Signal, e-mail e outras plataformas;
- tarefas agendadas e cron;
- delegação para subagentes;
- memória persistente e busca de sessões;
- criação e uso de skills;
- MCP, ACP e plugins;
- backends local, Docker, SSH e sandboxes remotos;
- ferramentas de voz e wake word presentes no código;
- dashboard e observabilidade já existentes na base.

### 3.2.1 Núcleo de continuidade e aceitação local operacionais

- WP-00: scorecard executável e fixture versionada de continuidade em
  `evals/mission_continuity/`;
- WP-01: contratos versionados e invariantes para missão, evento, recibo, artefato, verificação e
  lease de worker;
- WP-02: plugin `mission_control` com event log SQLite append-only, projeção transacional,
  idempotência, reconstrução e CLI `nara mission`;
- WP-03: pedido de tarefa persistido antes do efeito, criação pela API pública
  `ctx.dispatch_tool("kanban_create")`, vínculo ao ID canônico do Kanban e sincronização pelos
  hooks de conclusão e bloqueio;
- WP-04: Receipt Store de efeitos externos no mesmo event log, Artifact Store endereçado por
  SHA-256, hooks reais `pre_tool_call`/`post_tool_call`, offload de resultados grandes e gate de
  verificação independente para todos os critérios da missão;
- WP-05: fixture vertical que delega o efeito a outro processo, injeta queda depois da escrita e
  antes da confirmação, reconstrói a missão em nova instância, reconcilia por hash, observa o
  resultado por browser controlado e conclui somente após reabrir as evidências;
- prova executada em perfil temporário: scorecard sem bloqueadores, código de queda 86, um único
  efeito, dois receipts confirmados, artefato recuperável e missão concluída com zero critérios
  pendentes.

WP-00 a WP-05 estão `operational` no perfil local suportado. A líder está ligada ao goal da
sessão, ao Capability Router, ao cron canônico, ao supervisor, aos leases reais do Kanban e ao
Experience Ledger. A aceitação manual `nara-local-acceptance-20261123` percorreu sete eventos
duráveis, anexou o manifesto de release por conteúdo, exigiu verificador diferente do executor e
terminou `completed` com a verificação `pass`. A conversa textual e uma chamada real de ferramenta
também passaram com o provider Ollama. Voz acústica, gateways de contas externas e frota remota não
são inferidos dessa promoção local e mantêm seus próprios gates.

O Experience Ledger local registra fatos de tool calls e LLM calls por missão, tarefa, agente,
sessão e turno, mantendo hash/tamanho no lugar do conteúdo integral. `nara mission ledger` reúne
essa telemetria com eventos, receipts, artefatos e verificações da autoridade canônica.

A ponte inicial da Fase 1B também está `verified` por testes: o wake da CLI consulta a missão ativa
antes de abrir sessão nova; wake, transcrição e barge-in entram como eventos da mesma missão sem
persistir o texto integral; os estados de presença têm contrato único. A bancada em
`evals/voice_presence/` mede áudio PCM16 real e recusa promoção com amostra insuficiente. O detector
acústico “Ei, Nara” continua deliberadamente não promovido até receber o conjunto PT-BR definido na
seção 22 e passar o benchmark no hardware real.

O primeiro incremento executável da Fase 2 está `verified`. O provedor
`nara_temporal` foi mantido como extensão instalável independente, respeitando o limite do runtime
que fecha `plugins/memory/` para novos provedores internos. Ele persiste as cinco camadas, fonte,
validade, correções, candidatos e recibos de recuperação em SQLite por perfil. A recuperação atual é
um baseline lexical explicável e uma busca híbrida local opcional com `embeddinggemma`,
testada em bancada sintética PT-BR reservada. O resultado não demonstra qualidade geral em
tarefas reais variadas. O Learning Lab extrai procedimentos apenas de missões concluídas com prova
independente, separa desenvolvimento de holdout, materializa skills nativas somente depois de ganho
sem regressão e faz rollback sem apagar a evidência.

O gateway revisa periodicamente missões concluídas com prova e propõe de forma idempotente
candidatas procedimentais inativas. O CLI permite executar a consolidação imediatamente e
avaliar a transferência com um executável congelado, casos reservados e artefatos verificáveis
antes da promoção. Deduplicação e correção semântica entre experiências diversas ainda exigem
avaliação adicional.

A fixture `phase2-learning-transfer-v1` atravessa a demonstração prioritária: a missão A sofre uma
queda real após o efeito, reconstrói e verifica; uma candidata é extraída; três casos reservados
medem `0,5` de ganho médio sobre o baseline sem regressão; a skill é promovida; uma sessão nova
recupera a lição e conclui uma missão B diferente; por fim uma correção temporal substitui o fato
atual e conserva o original no histórico. Isso verifica o caminho integrado determinístico, mas não
substitui a futura bancada estatística com modelos e tarefas reais variadas.

O primeiro incremento da Fase 3 também está `verified`. O System Competence Registry é separado do
catálogo de modelos e mede a combinação versionada de skill, template, modelo, ferramentas e
ambiente. Falhas observadas pelos hooks de ferramentas e pelo supervisor geram lacunas duráveis e
priorizadas; troca de ambiente ou combinação volta a competência para `untested` e mostra a prova
anterior apenas como `outdated`. Planos de estudo exigem fonte e versão, reservam desenvolvimento e
holdout sem interseção e recusam promoção sem artefato verificável.

A fixture `phase3-competence-study-v1` começa com uma falha real: o baseline de ZIP encontra apenas
o arquivo da raiz e perde um membro aninhado. O artefato da falha abre a lacuna; exercícios separados
validam o novo procedimento; três archives reservados medem ganho médio positivo sem regressão; uma
missão de prova conserva os hashes e somente então resolve a lacuna e registra competência
demonstrada. A infraestrutura está ligada ao runtime e às ferramentas `nara_competence_status` e
`nara_gap_record`. A geração autônoma da candidata por pesquisa/modelo real ainda precisa atravessar
essa mesma bancada antes de a Fase 3 receber `operational`.

O primeiro incremento da Fase 4 está `verified`. O Evolution Lab congela desenvolvimento, holdout,
limite de regressão, ganho mínimo e custo antes da avaliação; armazena cada variante por SHA-256;
reabre os mesmos bytes antes do canário e da ativação; fixa sessões em andamento à versão anterior;
e mantém histórico de promoção e rollback. O Experience Ledger recebe o custo e o resultado da
avaliação. A fixture `phase4-evolution-fabric-v1` promove o hash exato de uma variante que melhora o
holdout, injeta uma regressão no canário, restaura o baseline e conserva a versão da sessão antiga.

O Learning Fabric desse incremento ingere documentos, sites materializados, imagens, áudio e vídeo
como originais endereçados por conteúdo. Texto local é extraído; áudio/vídeo pode ser transcrito
por um backend local instalado, com idioma configurável, hash próprio da transcrição e ligação
ao original. Vídeo amostra quadros para OCR local e registra hash, instante e texto por evidência,
mesclando a fala e o texto da tela sem perder erros parciais. Sem backend, permanece em
`needs_extraction` com erro visível; transcrição fornecida
também recebe hash próprio. Claims só podem
citar trechos existentes e permanecem candidatas até verificador e evidência. A mesma fixture
ingere documento e áudio com transcrição e prova a procedência. Entendimento completo de cenas,
timestamps por palavra, download,
GEPA/DSPy e otimização por modelos continuam sujeitos aos gates desta fase antes de `operational`.

O primeiro incremento da Fase 5 está `verified`. O `pre_llm_call` da líder executa uma resolução
leve em cada pedido, usando apenas metadados; tarefas simples permanecem com a Nara, e só o
especialista escolhido tem suas instruções completas carregadas por `nara_specialist_get`. O
Resolver consulta skills instaladas, competências observadas, modelos configurados e o catálogo
Legião por referência local, sem copiar seu conteúdo pessoal para o repositório. O catálogo real
desta máquina foi inspecionado pelo adapter: 91 agentes, 91 comandos e 11 orquestradores, e a busca
por análise de planilha selecionou `analista_dados` com o hash do prompt preservado.

O Agent Factory produz planos reproduzíveis com especialista, hash do prompt, modelo, provider,
ferramentas e orçamento. A fixture `phase5-dynamic-team-v1` resolveu três competências distintas,
carregou exatamente os três prompts escolhidos, abriu leases, executou três workers em paralelo,
produziu artefatos separados, sintetizou e concluiu a missão somente após quatro verificações. Ela
mostrou ganho de paralelismo e cobertura sobre o baseline determinístico. A promoção completa da
fase ainda exige repetir o comparativo com chamadas reais de LLM e custo/qualidade em tarefas
representativas, em vez de considerar quantidade de workers como sucesso.

O gate local da Fase 6 está `verified`. O Fleet Registry registra ambiente, endpoint, capacidades e
heartbeat, enquanto o Mission Store continua sendo a autoridade única dos leases. O scheduler
recusa host incompatível, preserva handoff por hash, expira o lease do host perdido e só reatribui
quando não há efeito incerto. Receipts confirmados entram na lista explícita de operações que o novo
worker deve pular; receipts pendentes ou `unknown` produzem `reconcile_required`.

A fixture `phase6-local-fleet-failover-v1` inicia dois processos isolados: host A aplica um efeito,
grava estado parcial e morre com código 87; a coordenadora confirma o efeito por observação, entrega
o artefato ao host B, retoma com novo lease e conclui a missão com exatamente um efeito. O adapter e
o contrato estão prontos para transporte remoto, mas a Fase 6 não recebe `operational` antes do
mesmo cenário atravessar SSH/VPS real, queda de rede e incompatibilidade de ambiente observada.

### 3.3 Gates externos e ampliações restantes

- treino e benchmark do detector acústico “Ei, Nara” com dataset PT-BR e hardware real;
- smoke de frota em VPS/SSH real, incluindo queda de rede e incompatibilidade observada;
- credenciais e contas para validar providers cloud e gateways de mensagens escolhidos;
- adapters de ASR/OCR/site e busca híbrida somente quando vencerem as bancadas reservadas;
- benchmark estatístico de equipes e aprendizado com tarefas e modelos variados;
- Nara Memory Gateway para clientes externos autenticados;
- período futuro de paper trading com uma fonte de cotações configurada;
- publicação, assinatura de instaladores e feed próprio, todos dependentes de infraestrutura e
  autorização do proprietário.

## 4. Regra principal de construção

Uma função não será considerada pronta apenas porque existe código, uma classe, uma tela ou uma
demo. Ela só será entregue quando:

1. puder ser acionada por uma interface real;
2. atravessar o mesmo runtime usado pelo produto;
3. persistir o estado necessário;
4. produzir recibos e artefatos observáveis;
5. sobreviver aos cenários de falha definidos;
6. passar por verificação independente;
7. possuir diagnóstico e caminho de recuperação.

Estados oficiais de uma capacidade:

| Estado | Significado simples |
| --- | --- |
| `discovered` | Encontramos a ideia ou o código. Ainda não faz parte do produto. |
| `wired` | Está conectado e pode ser chamado. |
| `verified` | Passou por teste real de comportamento. |
| `operational` | Possui diagnóstico, recuperação e documentação. |
| `promoted` | Pode ficar habilitado por padrão. |

Somente capacidades `operational` ou `promoted` serão mostradas ao usuário como funções prontas.

## 5. Visão de funcionamento

```text
Pessoa / voz / Desktop / terminal / mensageiros / API
                         │
                         ▼
                 Nara Mission Control
              objetivo, estado, tarefas e provas
                         │
       ┌─────────────────┼─────────────────┐
       ▼                 ▼                 ▼
 contexto e memória   líder e equipe   competências e orçamento
       │                 │                 │
       └─────────────────┼─────────────────┘
                         ▼
                Capability Router
        API · arquivos · terminal · web · apps · voz
                         │
                         ▼
            recibos · artefatos · eventos · custos
                         │
               ┌─────────┴─────────┐
               ▼                   ▼
       verificador independente   Evolution Lab
       prova que terminou          aprende e melhora
                                      │
                                      ▼
                          lacunas → estudo → prática
                                      │
                                      ▼
                         prova em tarefa nova → skill
```

Segurança, privacidade e políticas próprias passam por um módulo central versionado. O perfil
inicial permanece `observe_only` e novas regras só entram por promoção explícita.

## 6. Experiência esperada do usuário

Exemplo de missão:

> “Pesquise os melhores fornecedores, monte uma comparação, entre nos sites, peça os dados que
> estiverem disponíveis, crie a planilha e me apresente a recomendação.”

Fluxo esperado:

1. Nara transforma o pedido em uma missão.
2. Registra objetivo, limites, prazo e o que contará como concluído; pergunta apenas quando faltar informação necessária.
3. Divide o trabalho em tarefas dependentes.
4. Escolhe agentes, modelos, ferramentas e máquinas adequadas.
5. Executa primeiro com a menor equipe suficiente e paraleliza quando houver benefício esperado.
6. Mostra progresso sem interromper o trabalho.
7. Guarda cada efeito externo como recibo.
8. Entrega arquivos e evidências como artefatos.
9. Um agente diferente verifica os critérios de conclusão.
10. A missão termina somente depois da verificação.
11. Procedimentos úteis viram memória ou skill candidata, com origem e versão.
12. A skill é testada em uma tarefa nova, em outra sessão, antes da promoção.
13. Lacunas encontradas entram em uma fila de estudo, prática e reavaliação.

## 7. Componentes do produto

### 7.1 Autoridade única sobre a missão

**Função:** manter uma única autoridade sobre objetivo, tarefas, memória, recibos e conclusão,
com o núcleo Nara como loop principal de agente.

**Decisão:** evitar frameworks completos concorrentes comandando as mesmas missões. Bibliotecas,
serviços e uma infraestrutura de execução durável podem ser usados sob essa autoridade.

Antes de construir filas, timers e retomada do zero, comparar uma implementação mínima local com
infraestrutura pronta, incluindo Temporal. LangGraph será referência de persistência e recuperação;
sua adoção não é obrigatória e dependerá de benefício demonstrado e integração sem estado duplicado.

O componente de durabilidade não será uma segunda líder ou memória. Os eventos, estados e IDs
terão proprietários definidos, e telas ou índices serão projeções dessas fontes de verdade.

**Prova de conclusão:** uma conversa iniciada no CLI pode ser observada no Desktop e continuada
por um gateway sem criar outra missão ou sessão lógica. Falhas e retomadas usam os mesmos IDs.

### 7.2 Mission Control

**Função:** ser o cérebro operacional durável da autonomia.

Cada missão guardará:

- objetivo;
- contrato de conclusão;
- restrições, orçamento e prazo;
- tarefas e dependências;
- agentes responsáveis;
- estado atual e próximo passo;
- tentativas, erros e bloqueios;
- recibos, artefatos e evidências;
- checkpoint de retomada;
- versões de plano, skills, prompts, adapters, configuração e runtime usados;
- operações com resultado desconhecido e procedimento de reconciliação;
- motivo de conclusão, falha ou cancelamento.

Estados mínimos:

`draft`, `planned`, `running`, `waiting`, `verifying`, `needs_input`, `completed`, `failed` e
`cancelled`.

**Inspirações:** EVE Workboard, Paperclip e canais do Buzz, reimplementados sobre a base atual.

**Não será feito:** instalar esses runtimes completos como autoridades concorrentes da missão.
Uma fila ou motor de execução poderá servir à mesma autoridade, com contrato explícito.

Falhas recuperáveis acionam leitura do estado, diagnóstico e replanejamento. O supervisor detecta
repetição sem progresso e troca a estratégia; esgotar tentativas não comprova impossibilidade.
Uma retomada continua com as versões registradas ou executa uma migração explícita e registrada.

### 7.3 Event Log

**Função:** registrar cada transição da missão como evento imutável.

O estado atual será reconstruído a partir dos eventos. Isso permitirá explicar decisões, retomar
o trabalho e evitar repetir ações já concluídas.

### 7.4 Receipt Store

**Função:** registrar o efeito observado de cada ação importante.

Cada recibo conterá:

- intenção;
- missão e tarefa;
- agente e modelo;
- ferramenta e alvo;
- chave de idempotência;
- horário;
- resultado observado;
- erro, quando houver;
- artefatos produzidos;
- forma e estado da verificação;
- ID da operação no destino, quando disponível;
- tentativas e versão do adapter;
- estado do efeito: `pending`, `confirmed`, `failed` ou `unknown`.

A intenção e a chave estável serão persistidas antes da chamada externa. A chave precisa ser
aceita pelo destino para deduplicar efeitos; guardá-la apenas localmente não fornece essa garantia.
Se o destino aplicar a ação e a confirmação se perder, a operação ficará `unknown`, mesmo sem
recibo de sucesso. A retomada consultará o destino e reconciliará o efeito antes de qualquer retry.

Sem chave aceita ou consulta conclusiva, não há garantia geral de execução única. A tarefa manterá
a incerteza explícita, aguardará evidência ou solicitará a informação necessária. Uma leitura antes
da escrita, isoladamente, também não elimina corridas e duplicações.

### 7.5 Artifact Store

**Função:** guardar arquivos, relatórios, imagens, vídeos, logs e provas fora do contexto do
modelo.

Os artefatos serão endereçados por hash e ligados à missão. O contexto ativo carrega referências,
não cópias completas de todos os arquivos.

### 7.6 Verificador independente

**Função:** impedir que o executor declare sucesso sem prova.

O verificador recebe o objetivo, os critérios e os artefatos. Ele não recebe a conclusão do
executor como fato.

Resultado técnico:

- `pass`: critério comprovado;
- `fail`: critério reprovado;
- `inconclusive`: evidência insuficiente.

Gate terminal:

- `continue`: ainda existe trabalho observável;
- `complete`: todos os critérios foram comprovados;
- `impossible`: existe impedimento estrutural comprovado e alternativas foram esgotadas.

O juiz final será uma instância diferente daquela que executou a tarefa. Essa separação reduz
influência direta do executor, mas não elimina erros compartilhados entre modelos.

Ordem de evidências preferida:

1. verificação determinística ou consulta ao sistema de destino;
2. execução e inspeção do artefato produzido;
3. observação independente da interface ou do ambiente;
4. julgamento por modelo, com rubrica explícita, para critérios qualitativos.

Exemplos: executar o programa e seus testes relevantes, reabrir o documento, recalcular a planilha,
consultar o registro criado e conferir fontes. Uma resposta persuasiva do executor ou do juiz não
substitui esses resultados. Ausência de prova produz `inconclusive`, não `pass`.

### 7.7 Agente líder

**Função:** manter responsabilidade pela missão inteira.

A líder:

- entende o objetivo;
- cria e atualiza o plano;
- conhece capacidades disponíveis;
- monta a equipe;
- controla orçamento e prazo;
- acompanha bloqueios;
- integra resultados;
- chama o verificador;
- apresenta o resultado final.

### 7.8 Agent Factory

**Função:** criar agentes especializados sob demanda, começando por uma líder e poucos workers.

O dispatcher compara a execução com um agente e com equipe: qualidade verificada, tempo total,
custo e retrabalho. Delegação é preferida em partes independentes, com entradas e saídas claras.
Mais agentes ou três modelos diferentes não serão requisitos artificiais de conclusão.

Papéis possíveis, habilitados conforme a missão:

- planejador;
- pesquisador;
- programador;
- operador de navegador/desktop;
- analista de documentos;
- agente de voz;
- crítico;
- verificador;
- curador de memória;
- criador de skills;
- watchdog;
- roteador de modelos.

Cada agente recebe somente:

- a tarefa;
- o contexto necessário;
- as ferramentas permitidas para aquela tarefa;
- modelo e provider;
- orçamento e prazo;
- critério de conclusão;
- formato de saída.

Podem existir agentes persistentes com nome e histórico, com papéis de especialidade, e workers efêmeros que
desaparecem depois da entrega.

### 7.9 Model Capability Registry

**Função:** conhecer e medir os modelos disponíveis.

Para cada modelo serão registrados:

- provider;
- local ou cloud;
- janela de contexto;
- modalidades;
- uso de ferramentas;
- custo;
- latência;
- disponibilidade;
- qualidade medida por categoria de tarefa;
- falhas e taxa de sucesso verificado.

O sistema não codificará permanentemente “modelo X é o melhor”. A escolha mudará conforme o
resultado medido.

### 7.10 Roteamento em camadas

| Trabalho | Camada preferida |
| --- | --- |
| Classificar intenção, prioridade ou escolher skill | classificador local ou modelo pequeno |
| Buscar, ler e resumir fontes | modelo rápido e econômico |
| Programar, operar ferramentas e testar | modelo executor adequado ao domínio |
| Projetar arquitetura, criticar e verificar | modelo forte e independente |

Classificadores como Laya serão avaliados apenas para decisões tipadas de baixo risco. Eles não
receberão autoridade para planejar, escrever conteúdo ou aprovar o resultado final.

### 7.11 Workers distribuídos

**Função:** usar vários computadores como uma única frota.

Cada máquina publicará:

- CPU, RAM, GPU e VRAM;
- sistema operacional;
- modelos e ferramentas instalados;
- capacidade livre;
- limite de trabalhos simultâneos;
- saúde e último heartbeat;
- custo e desempenho observado.

O dispatcher utilizará fila, lease, cancelamento, artifact handoff e reclaim. Se uma máquina
cair, outro worker poderá assumir a tarefa sem repetir uma ação externa já confirmada.

### 7.12 Memória em cinco camadas

| Camada | Conteúdo | Retenção |
| --- | --- | --- |
| Trabalho | próximo passo, hipóteses e dados temporários | missão atual |
| Episódica | conversas, eventos, chamadas e recibos originais | histórico pesquisável |
| Semântica | pessoas, preferências, projetos, decisões e fatos | entre sessões |
| Procedimental | skills, playbooks e automações verificadas | versionada |
| Reflexiva | falhas recorrentes e estratégias melhores | somente após avaliação |

Cada memória durável terá fonte, data, escopo, confiança, validade e relação `supersedes` quando
corrigir uma informação anterior.

O resumo nunca substituirá o original. Quando necessário, a Nara recuperará a conversa, o
recibo ou o artefato que sustenta a memória.

Um processo de consolidação em segundo plano revisará experiências concluídas, eliminará
redundâncias, proporá correções e ligará fatos a procedimentos. Fatos observados e hipóteses terão
estados distintos. Consolidação não poderá ressuscitar informação substituída ou trocar a origem
por um resumo sem evidência. Busca e atualização serão avaliadas separadamente da geração de texto.

### 7.13 Contexto contínuo

**Função:** trabalhar além de uma janela de contexto sem esquecer a missão.

O modelo receberá apenas:

1. identidade e instruções estáveis;
2. missão e contrato de conclusão;
3. estado atual e próximo passo;
4. memórias relevantes;
5. artefatos necessários;
6. mensagens recentes.

Resultados grandes sairão do prompt e virarão artefatos pesquisáveis. A compactação manterá links
para os dados originais.

#### 7.13.1 Nara Memory Gateway

**Função:** oferecer uma interface única para que a própria Nara e clientes externos autorizados
consultem e proponham informações para a mesma memória canônica, sem criar um cérebro concorrente
em cada provider.

O gateway será exposto por MCP e API local. Codex, Claude, ChatGPT, Grok, agentes locais e futuras
interfaces poderão recuperar contexto da Nara sem copiar toda a base para o prompt ou manter uma
memória paralela. Missões, fatos e procedimentos continuam pertencendo ao runtime Nara.

Operações conceituais:

- `memory.search`: buscar apenas os trechos relevantes para a tarefa e o escopo atual;
- `memory.get`: recuperar o original, a fonte e o histórico de correções;
- `memory.propose`: propor uma nova memória sem promovê-la automaticamente;
- `memory.correct`: propor correção ligada à informação anterior por `supersedes`;
- `memory.receipt`: explicar o que foi recuperado, por quê, de onde e em qual versão.

Cada leitura respeitará usuário, perfil, projeto, missão, agente e validade. Cada escrita externa
entrará como candidata com autor, origem, data, confiança e evidência. Consolidação ou verificação
decidirá se ela será promovida, mesclada, mantida como hipótese ou rejeitada. Um resumo nunca
substituirá silenciosamente o original.

O gateway não enviará a memória inteira ao modelo. Busca híbrida, filtros de escopo e orçamento de
contexto selecionarão o menor conjunto suficiente. A mesma consulta deverá produzir um recibo
inspecionável para que a pessoa entenda qual lembrança influenciou a resposta ou a ação.

### 7.14 Capability Router

**Função:** escolher a forma mais confiável e econômica de agir.

Ordem preferida:

1. API ou conector estruturado;
2. arquivo ou terminal;
3. DOM/CDP do navegador;
4. árvore de acessibilidade;
5. visão e coordenadas;
6. intervenção humana quando o resultado não puder ser observado.

Cada capacidade declarará disponibilidade, custo, latência, cancelamento, idempotência e forma de
verificação.

### 7.15 Controle do computador

Escopo planejado:

- arquivos e pastas;
- terminal e processos;
- navegador local e isolado;
- aplicativos desktop;
- Electron;
- APIs e MCPs;
- máquinas remotas por SSH ou A2A;
- simulador iOS;
- Android em fase posterior;
- câmera, microfone e outros dispositivos somente por adapters explícitos.

O sistema observará novamente o alvo depois de ações com efeito para confirmar o resultado.

### 7.16 Voz e palavra de ativação

**Objetivo:** permitir conversa natural semelhante a um assistente sempre disponível.

Recursos:

- wake word local e configurável;
- conversa em português;
- streaming de voz;
- interrupção enquanto a Nara fala;
- detecção de fim de fala;
- STT, LLM e TTS substituíveis;
- voz ligada à mesma sessão durável do texto;
- acompanhamento falado de missões longas;
- modo de reunião com captura, diarização, transcrição e resumo;
- nome Nara e frase “Ei, Nara” definidos; treino e benchmark próprios do detector como entrega necessária.

OpenAI Realtime, LiveKit, Pipecat, PersonaPlex, Whisper, Parakeet e opções locais serão adapters,
não donos da memória ou da missão.

### 7.17 Agenda e operação contínua

**Função:** ficar disponível sem manter um LLM pensando em loop infinito.

O gateway e o scheduler serão mantidos por supervisor do sistema. Workers acordarão por evento,
prazo, mensagem, recuperação ou trabalho pendente.

Recursos:

- cron e tarefas recorrentes;
- timezone explícito;
- prevenção de execução duplicada;
- jobs retomáveis;
- entrega de resultados em qualquer canal configurado;
- watchdog para travamentos e prazos.

### 7.18 Protocolos e integrações

- **MCP:** ferramentas, recursos, prompts, apps e operações longas;
- **ACP:** integração com agentes e ambientes compatíveis;
- **A2A:** delegação para agentes remotos opacos;
- **plugins:** capacidades opcionais sem aumentar o core;
- **skills:** conhecimento procedimental carregado sob demanda;
- **gateways:** mensageiros e canais externos;
- **APIs:** conectores diretos quando forem mais confiáveis que a interface visual.

As regras de acesso das integrações serão definidas no módulo separado da Fase 9.

### 7.19 Experience Ledger

**Função:** registrar o que realmente funcionou.

Para cada missão:

- modelos e estratégia usados;
- ferramentas acionadas;
- tempo, tokens e custo;
- falhas, retries e correções;
- intervenções humanas;
- critérios aprovados ou reprovados;
- artefato final;
- feedback do usuário;
- lições candidatas.

Esse ledger será a matéria-prima da evolução, não uma impressão subjetiva do modelo.

Também registrará versões, IDs das avaliações, tarefas em que a lição foi reutilizada, vínculo
com lacunas de competência e diferenças frente ao baseline. O custo de estudar, avaliar e
consolidar memória entra no custo total da melhoria.

### 7.20 Learning Fabric multimodal

**Função:** aprender com experiências e código desde o início; ampliar depois para documentos,
sites, áudio e vídeo. A ingestão multimodal completa não será pré-requisito para aprender.

O primeiro ciclo será: missão real → diagnóstico → procedimento candidato → avaliação em sessão
nova → promoção ou rejeição. A prova utilizará tarefas diferentes das usadas na extração.

Estudo ativo partirá de lacunas priorizadas no System Competence Registry, com objetivo de estudo,
fontes, exercício, resultado observado e teste de transferência. Ler ou resumir um conteúdo não
será registrado como domínio da competência.

Pipeline:

```text
fonte
  -> aquisição temporária
  -> hash e metadados
  -> transcrição e timestamps
  -> cenas, quadros e OCR
  -> fusão de fala, tela e legenda
  -> extração de afirmações e projetos
  -> verificação em fontes primárias
  -> proposta de memória, skill, experimento ou descarte
  -> avaliação isolada
  -> promoção ou rejeição
```

Aprendizagem ativa:

- gerar explicação do conteúdo;
- formular perguntas e exercícios;
- testar o agente em casos que não estavam no material de estudo;
- registrar onde errou;
- promover somente a competência demonstrada.

As regras de autoridade de conteúdo externo e instalação serão especificadas na Fase 9.
Procedência e teste de competência fazem parte do aprendizado desde as primeiras fases.

### 7.21 Skills e catálogo de especialistas

**Função:** adicionar conhecimento sem inflar o prompt permanente.

Fontes:

- catálogo atual de skills;
- Legião-Local;
- projetos públicos analisados;
- procedimentos aprendidos em missões reais;
- skills criadas pelo próprio Evolution Lab.

Cada skill candidata precisará de origem, licença, hash, versão, análise, teste, eval e rollback.
O router carregará somente as skills necessárias para a tarefa atual.

Uma skill incluirá entradas, pré-condições, passos, saídas esperadas, falhas conhecidas e forma de
verificação. Procedimentos estáveis poderão virar scripts ou ferramentas reutilizáveis com testes
relevantes. A promoção exige reuso em caso novo; salvar um texto não comprova aprendizado.

#### 7.21.1 Specialist Resolver e uso do Legião

**Função:** verificar, no início de cada missão e quando surgir uma nova subtarefa, se já existe um
especialista adequado e qual modelo demonstrou melhor capacidade para executá-la.

Toda missão passará por uma resolução leve de competência. Isso não significa criar um worker para
cada pergunta simples. A Nara continuará executando diretamente quando delegar custar mais do que
ajudar. Quando a tarefa exigir especialização, o resolver seguirá este fluxo:

1. transformar a tarefa em um contrato de competência, modalidade, ferramentas, ambiente, custo,
   prazo e critério de conclusão;
2. consultar System Competence Registry, skills instaladas, módulos de domínio e Legião-Local;
3. filtrar candidatos por pré-condições, validade, ferramentas, licença, histórico e disponibilidade;
4. consultar o Model Capability Registry para combinar o especialista com o LLM mais adequado;
5. comparar execução direta, um especialista ou uma pequena equipe pelo ganho esperado;
6. instanciar somente os escolhidos com contexto mínimo, ferramentas, orçamento e formato de saída;
7. verificar o resultado e registrar agente, modelo, custo, falhas e qualidade no Experience Ledger;
8. criar ou estudar um especialista novo somente quando os candidatos existentes não atenderem.

O Legião será o primeiro catálogo privado de templates especializados, não um runtime concorrente.
Suas instruções descrevem papéis, métodos e cadeias; a Nara fornece missão, memória, modelo,
ferramentas e verificação. Um template não ficará preso a um provider: requisitos de capacidade
serão separados da escolha do LLM para que o mesmo especialista possa usar modelo local ou cloud.

O roteamento não será baseado apenas no nome ou na descrição do agente. Cada combinação
`especialista + modelo + ferramentas + versão` acumulará resultados por categoria de tarefa. A
seleção privilegiará competência demonstrada, disponibilidade e custo total. A decisão produzirá
um recibo explicando por que o especialista e o LLM foram escolhidos, quais alternativas existiam e
se houve fallback. Preferência explícita da pessoa prevalece quando o modelo puder executar a tarefa.

Os 91 templates e 11 orquestradores já recuperados do Legião não serão carregados juntos no prompt.
Busca por metadados e competência apresentará poucos candidatos; somente as instruções escolhidas
entrarão na sessão do worker. Orquestradores do Legião podem servir como templates de fluxo, mas a
Nara permanece a única autoridade sobre missão, memória, orçamento e conclusão.

### 7.22 Evolution Lab

**Função:** permitir evolução automática avaliada, iniciando por skills e ampliando o alvo conforme os resultados.

Ordem de mudanças, da mais simples para a mais arriscada:

1. contexto temporário;
2. memória;
3. skill ou playbook;
4. prompt, configuração ou roteamento;
5. plugin ou código;
6. ajuste ou treinamento de modelo.

Toda variante passará por:

- hipótese explícita;
- dataset ou fixture versionada;
- baseline;
- execução isolada;
- separação entre material de estudo, conjunto de desenvolvimento e conjunto de prova reservado;
- comparação de qualidade, custo total e regressões;
- prova em tarefas novas e sessões novas, sem expor a solução esperada ao executor;
- canário;
- promoção versionada;
- monitoramento;
- rollback automático.

Mudanças de código serão produzidas em branch/worktree isolado. A instalação ativa não será
reescrita diretamente pelo agente.

O avaliador poderá usar referências e resultados esperados que não são expostos ao executor.
A variante não editará o conjunto de prova, a rubrica ou o avaliador para aprovar a si mesma.
Se o conjunto reservado for usado para guiar uma nova otimização, deixará de ser prova reservada
e deverá ser substituído. Múltiplas execuções registrarão variabilidade e falhas, sem escolher
apenas a melhor tentativa.

Comparações mínimas:

- mesmo modelo, ferramentas e orçamento, com e sem experiência retida;
- baseline e variante em tarefas não usadas na otimização;
- qualidade, custo, latência, intervenções e regressões por categoria.

GEPA e Agent Lightning Skill serão as referências principais do protótipo. DSPy é biblioteca
opcional; o candidato upstream de autoevolução exige correção e validação da exportação antes de adoção.
O estado de cada recurso externo será verificado na integração: evolução de código, prompts e
loop contínuo não será presumida implementada pela descrição geral de um projeto.

### 7.23 Desktop e escritório visual

Telas planejadas:

- conversa e voz;
- projetos e missões;
- canais por missão;
- equipe de agentes;
- tarefas e dependências;
- artefatos;
- memória;
- agenda;
- custos e orçamento;
- traces e recibos;
- avaliações;
- Evolution Lab;
- configurações de providers, modelos, ferramentas e políticas.

O escritório visual mostrará agentes reais, não personagens decorativos.

Estados visuais:

`idle`, `planning`, `working`, `waiting`, `verifying`, `blocked`, `completed`, `failed` e
`offline`.

Cada agente mostrará:

- nome e papel;
- modelo;
- missão e tarefa;
- duração e custo;
- ferramenta atual;
- último heartbeat;
- bloqueio;
- artefatos e resultado.

Fechar o Desktop não interromperá os workers. A animação será apenas uma projeção do event stream.

### 7.24 System Competence Registry

**Função:** medir o que a Nara inteira consegue executar, além da capacidade isolada do modelo.

Cada competência registrará:

- tarefa e domínio, com pré-condições e ambiente de execução;
- modelos, ferramentas, adapters e versões necessários;
- evidências, data e conjunto de avaliação;
- taxa de sucesso, falhas, custo e tempo observados;
- limites conhecidos, validade e gatilhos de reavaliação;
- skills relacionadas e lacunas ainda abertas.

As classificações distinguirão competência não testada, em prática, demonstrada e desatualizada.
Elas não substituem os estados de entrega da seção 4: uma integração pode ser operacional sem
ter competência demonstrada em todos os usos. Mudanças de modelo, ferramenta ou ambiente exigem
reavaliação proporcional ao impacto. O catálogo não afirmará domínio universal a partir de um caso.

### 7.25 Fila de lacunas e estudo ativo

**Função:** transformar dificuldades observadas em trabalho de aprendizado autônomo.

Fluxo:

1. detectar uma falha ou falta de competência e preservar sua evidência;
2. distinguir problema de acesso, ferramenta, conhecimento, procedimento ou verificação;
3. priorizar pelo impacto em missões e recorrência, considerando custo e tempo;
4. definir o resultado de aprendizado e pesquisar documentação e exemplos;
5. praticar em ambiente de teste com feedback observável;
6. avaliar em caso novo, sem reutilizar a solução do exercício;
7. atualizar skill e competência apenas após ganho demonstrado;
8. registrar falha, alternativa ou bloqueio quando o estudo não resolver a lacuna.

A fila usará as mesmas missões, eventos e artefatos do produto. Estudo em segundo plano acordará
por eventos ou agenda e terá orçamento e critério de parada; não haverá loop permanente de LLM.

### 7.26 Avaliação longitudinal do aprendizado

**Função:** comprovar que experiência anterior melhora trabalho futuro.

A bancada combinará tarefas reais representativas com referências como PAST-Bench. Usará sessões
novas, condições equivalentes e controles com persistência ligada e desligada. Provas serão
separadas por fatos, procedimentos, busca proativa e substituição de informação desatualizada.

Além da nota final, os traces deverão demonstrar que a lição foi salva, recuperada e aplicada.
Serão relatados resultados negativos, regressões, custo de aprendizado e variação entre tentativas.
O baseline será mantido; um resultado isolado ou um benchmark público não comprova capacidade geral.

### 7.27 Segurança, privacidade e políticas próprias

**Estado registrado:** o PDP versionado está ativo em `default-observe-only-v1`. Sem regras
promovidas, ele observa e registra sem acrescentar recusas próprias; continuam valendo os limites do
modelo e do provider. Versões de produção podem exigir confirmação exata de uso único ou negar uma
ação, sempre com explicação, promoção atômica e rollback.

O mesmo módulo atende CLI, voz, gateway, subagentes e frota. A camada de privacidade começa com
telemetria, transcrição, câmera, biometria e traces sensíveis desligados e retenção de mídia em
zero. Regras concretas para instalação de pacotes, ações comerciais, publicações, contato externo
ou bots entram somente depois de revisão e promoção explícita pelo proprietário.

Idempotência, integridade do estado, locks, leases, validação de formatos, recuperação e versões
continuam nas fases iniciais porque são necessários para executar e retomar corretamente.

### 7.28 Nara Trading Lab

**Função:** adicionar pesquisa de mercado, avaliação de estratégias e operação financeira como um
módulo de domínio opcional, sem transformar trading em responsabilidade permanente do core.

O Trading Lab será um plugin com serviço próprio e adapters de dados e corretoras. Ele reutilizará
Mission Control, memória, Agent Factory, Model Capability Registry, eventos, recibos, artefatos,
agenda, verificador e escritório visual da Nara. Não terá outra líder, outra memória nem um loop de
autonomia concorrente. Quando o laboratório estiver desativado, seus especialistas e ferramentas
não serão enviados aos modelos nem aumentarão o core.

Uma instalação da Nara poderá manter vários laboratórios isolados, por exemplo `Cripto Pesquisa`,
`Ações Brasil` e `Carteira Longo Prazo`. Cada laboratório terá universo de ativos, moeda, fontes,
benchmark, estratégia, orçamento, modo operacional, credenciais, histórico e limites próprios.

#### 7.28.1 Como a pessoa usará

Pela conversa ou voz:

> “Nara, crie um Trading Lab para estudar Bitcoin e Ethereum. Comece somente com pesquisa e
> backtest; compare com comprar e manter e me mostre os riscos.”

Pelo Nara Office, a pessoa acompanha o estado persistido do laboratório. Pela conversa, a líder usa
as ferramentas `nara_trading_init`, `nara_trading_backtest` e `nara_trading_status`. Uma superfície
CLI dedicada poderá oferecer comandos equivalentes sem criar outra autoridade de estado; os
comandos `nara trading ...` ainda não são declarados como existentes.

Depois da criação, pedidos comuns serão naturais:

- “Analise por que o laboratório não abriu posição hoje.”
- “Compare a estratégia atual com buy-and-hold, incluindo taxas e slippage.”
- “Rode novamente sem usar notícias posteriores à data simulada.”
- “Mostre quais agentes discordaram e quais evidências usaram.”
- “Pause novas ordens, mas continue coletando dados.”

No escritório visual, o Trading Lab será uma sala da Nara. Cada analista, comitê ou executor exibido
corresponderá a um agente ou serviço real. Clicar nele mostrará tarefa, modelo, dados, decisão,
custo, estado, exposição, artefatos e recibos. A sala é uma projeção dos mesmos eventos persistidos,
não uma simulação decorativa.

**Implementado e verificado localmente:** o módulo persistente cria laboratórios isolados nos modos
research, backtest e paper; importa CSV por hash; impede duplicatas e ordem temporal inválida; gera
sinais apenas com linhas anteriores; calcula custos, slippage, drawdown e benchmark; e reproduz a
mesma execução pelo hash de dataset e configuração. O ledger paper tem idempotência, saldo único da
carteira, limites por ordem/posição, pausa e kill switch. `live_available` permanece falso por
construção e não existe adapter capaz de enviar ordem real nesta entrega.

#### 7.28.2 Modos e progressão

1. **Research:** coleta e analisa dados; não produz ordens.
2. **Backtest:** reproduz estratégias em dados históricos versionados.
3. **Paper:** acompanha o mercado e simula ordens em tempo real, sem capital real.
4. **Live:** envia ordens a uma corretora somente após gates próprios, políticas da Fase 9 e
   habilitação explícita para o laboratório e a conta escolhidos.

A progressão não será automática por tempo de uso. Cada mudança de modo exige evidências e um gate
registrado. Pesquisa, backtest e paper poderão evoluir antes do módulo de políticas próprio; modo
live dependerá também da especificação e da validação da Fase 9.

#### 7.28.3 Componentes internos

- **Market Data Layer:** dados de mercado versionados, calendário, notícias e fundamentos;
- **Research Desk:** especialistas em técnico, fundamentos, macro, notícias e sentimento conforme o domínio;
- **Investment Committee:** compara propostas, registra divergências e produz decisão tipada;
- **Portfolio Engine:** calcula exposição, concentração, caixa e rebalanceamento de forma determinística;
- **Risk Guard:** valida limites e pode vetar qualquer proposta antes da execução;
- **Execution Adapter:** converte uma ordem validada para a API da corretora e reconcilia o resultado;
- **Trading Ledger:** preserva dado usado, decisão, ordem, execução, custo, posição e resultado;
- **Evaluator:** compara estratégia, benchmark, drawdown, risco, custos e estabilidade fora da amostra.

LLMs poderão pesquisar, argumentar e propor. Cálculos de posição, limites, saldo, risco, validação de
ordem e reconciliação serão determinísticos. O executor não receberá autoridade direta para ignorar
o Risk Guard. Uma mensagem de sucesso do modelo nunca substituirá o recibo da corretora.

Backtests deverão impedir vazamento temporal, registrar dataset e versão do código, incluir taxas e
slippage e comparar com benchmarks simples. Resultados de uma janela não comprovam vantagem. Paper
trading medirá comportamento em tempo real antes de qualquer avaliação de modo live.

### 7.29 Nara Reverse Engineering Lab

**Função:** investigar software e artefatos autorizados, explicar como uma função observada trabalha
e produzir reconstruções independentes sustentadas por evidências.

O laboratório será um módulo de domínio da Nara baseado no plugin oficial REA. O pacote instalado
fornece a skill `reverse-engineer-anything` e um servidor MCP fixado em `rea-agents@6.7.0`. Suas 207
ferramentas ficam atrás da busca sob demanda e não entram permanentemente no contexto do modelo.

Exemplo de uso:

> “Nara, analise este aplicativo Electron, descubra como a sincronização funciona, mostre as
> evidências e implemente uma versão compatível no nosso projeto.”

O Specialist Resolver identificará o tipo de alvo e combinará o REA com templates do Legião ou
skills da Nara, por exemplo especialistas em Electron, Android, binários nativos, redes, firmware,
arquitetura e testes. O modelo será escolhido pelo Model Capability Registry; REA fornece as
ferramentas e evidências, não outro agente líder.

Rotas principais:

- repositório com fonte completa: ferramentas normais de código, sem iniciar REA desnecessariamente;
- Electron/JavaScript ou .NET empacotado: inspeção estática do artefato;
- binário nativo: inventário e decompilação pelo Ghidra atualmente disponível;
- APK Android: inventário estático; análise profunda depende do adapter JADX configurado;
- firmware, captura de rede ou processo: provider específico e escopo declarado;
- comportamento em execução: captura separada que pode iniciar ou controlar o alvo;
- reconstrução: implementação nova ligada às evidências, limitações e testes de equivalência.

O padrão inicial será somente leitura: identificar formato, calcular hashes, preservar o artefato,
inventariar componentes e produzir um plano de investigação. Executar o alvo, anexar debugger,
injetar instrumentação, alterar dispositivo, instalar APK, acessar rede ou sobrescrever arquivo são
efeitos distintos e permanecerão visíveis no plano e nos recibos. Execuções não assistidas não
usarão essas operações interativas ou mutáveis.

Cada conclusão relevante apontará para uma evidência reproduzível: arquivo, endereço, função,
string, chamada, captura, hash ou comparação. Hipótese e fato observado terão estados diferentes.
O laboratório não alegará recuperar o código-fonte original; seu produto será compreensão técnica
e reconstrução própria adequada ao projeto da pessoa.

**Estado atual:** catálogo local corrigido para a origem pública real
repositório externo oficial registrado em `plugin-catalog/rea.yaml`, no commit fixado
`1690b63a...`; REA instalado, habilitado,
validado e descoberto pela Nara. O handshake MCP retornou servidor `rea` 6.7.0 e 207 ferramentas.
Análise nativa está disponível com Ghidra 12.1.4. O roteamento automático completo pelo Specialist
O roteamento automático e a projeção visual do laboratório agora estão implementados no Mission
Control. A prova local de 2026-11-22 executou `rea-agents@6.7.0` sobre fixtures próprias: o catálogo
reportou 207 ferramentas, a análise JavaScript foi concluída sem executar o artefato e o Ghidra
12.1.4 recuperou a função nativa `value * 7 + 3` a partir do binário Mach-O preservado por SHA-256.
Providers opcionais ausentes (Hopper, IDA, JADX e Kuna) continuam declarados como indisponíveis pelo
doctor e não são simulados como presentes.

## 8. Plugins e recursos opcionais estudados

Esses componentes não entrarão no core. Serão avaliados somente quando houver uma missão real que
justifique a integração.

| Área | Candidatos | Uso possível |
| --- | --- | --- |
| Browser estruturado | agent-browser, Browser Use, Playwright, Cua | navegação por DOM, acessibilidade ou ambiente isolado |
| Desktop | agent-desktop, Cua | controle de aplicativos por acessibilidade e visão |
| iOS | Baguette | simuladores, gestos, logs e device farm |
| Voz | Whisper, Parakeet, Realtime, LiveKit, Pipecat, PersonaPlex | STT, conversa full-duplex e TTS |
| Reuniões | Meetily e padrões semelhantes | captura, diarização, transcrição e resumo |
| Classificação | Laya ou modelo pequeno local | intenção, prioridade e decisões tipadas |
| Educação | OpenMAIC e cursos Hugging Face | aulas, exercícios e fixtures de avaliação |
| Vídeo | OpenFilm, Rea Video, MotionMaxxing | análise, edição e verificação de vídeo |
| Áudio | Earshot, SFX Kit e Foley Skill | análise, efeitos e sincronização |
| Avatar | LongCat Avatar | presença visual opcional |
| Arquitetura/CAD | Pascal e BenchUp | plugins de domínio |
| Jurídico | Advocacia Aberta e fontes oficiais | plugin jurídico com revisão profissional |
| Jogos | skills de Godot, Unity, Unreal e web | especialistas carregados sob demanda |
| Memória | provider atual, conceitos de Graphiti, Letta, Mem0 e GBrain | procedência, temporalidade e recuperação |
| Evals e transferência | PAST-Bench, Promptfoo e evals próprios | ganho entre sessões, controles com/sem experiência e regressões |
| Evolução de skills | DSPy/GEPA e candidato upstream de autoevolução | propor variantes e avaliar antes de promover |
| Consolidação de memória | padrões de Letta | revisão de experiências e organização em segundo plano |
| Execução durável | Temporal e conceitos de persistência do LangGraph | comparar com implementação local mínima, sem segunda autoridade de missão |
| Trading Lab | Aivy, Crewless Capital, AI Market Maker e AIRP | módulo opcional de pesquisa, backtest, paper e execução condicionada a gates |
| Reverse Engineering Lab | REA, Ghidra e especialistas do Legião | análise de artefatos, evidência e reconstrução independente sob demanda |

As referências são candidatas, não integrações já concluídas. A avaliação publicada do PAST-Bench
relata melhoria dependente de modelo e capacidade; seu uso não garante o mesmo ganho na Nara.
O README do candidato upstream de autoevolução declara a otimização de skills implementada. A inspeção
posterior identificou desacoplamento entre predictor otimizado e texto exportado da skill, com
correção proposta ainda aberta. O pacote é referência a corrigir e validar, não integração pronta.
Descrições de ferramentas, prompts, código e ciclo contínuo também exigem prova própria.

## 9. O que não será incorporado

- outro framework completo como autoridade concorrente sobre as mesmas missões;
- fontes de verdade concorrentes para as mesmas missões ou memórias; índices e projeções são permitidos;
- interface bonita sem backend real;
- centenas de skills carregadas em todo turn;
- loop infinito de LLM para parecer sempre online;
- treinamento de pesos como dependência das primeiras entregas;
- equipes maiores sem benefício observado frente ao baseline;
- promoção por melhora apenas nos exercícios usados durante a otimização;
- conclusão baseada somente no relato do executor;
- memória sem fonte ou validade;
- autoedição direta da instalação ativa;
- dependência obrigatória de um único provider.

## 10. Dados e armazenamento; privacidade em etapa posterior

Requisitos iniciais para continuidade e aprendizado:

- local-first quando possível;
- memória identificada por usuário, projeto, missão e agente para recuperação correta;
- originais pesquisáveis e resumos ligados às fontes;
- artefatos com hash, origem, produtor, versão e vínculo com a missão;
- exportação e backup do estado para recuperação;
- retenção de datasets, versões e resultados necessários para reproduzir avaliações;
- separação entre estado de execução, índices de busca e conjuntos de prova.

Os princípios de privacidade da versão 0.1 agora possuem implementação central: telemetria,
conteúdo sensível em traces, transcrição, biometria e câmera começam desligados; retenção de mídia
começa em zero; segredos são redigidos; configuração e exportação passam por ferramentas próprias.

## 11. Requisitos de confiabilidade

- intenção e chave estável persistidas antes de ações externas;
- deduplicação no destino quando suportada e reconciliação de efeitos incertos;
- estado `unknown` explícito quando não houver confirmação, sem repetição cega;
- confirmação do estado depois de cada escrita relevante;
- checkpoint em transições importantes;
- leases e heartbeats para workers;
- cancelamento propagado;
- limite de profundidade e orçamento por missão;
- recuperação depois de queda de processo ou máquina;
- não repetir ações confirmadas e medir duplicações em falhas injetadas;
- registrar limites de garantia em destinos sem deduplicação ou consulta conclusiva;
- versões de plano, skill, adapter e configuração associadas à execução e à retomada;
- artefatos endereçados por conteúdo;
- logs e traces navegáveis;
- verificação independente apoiada em medições externas e testes relevantes;
- versões e rollback para toda promoção;
- testes com perfil temporário, nunca com o estado pessoal do usuário.

## 12. Métricas do produto

### Resultado

- percentual de missões concluídas e verificadas;
- percentual de critérios sustentados por evidência;
- qualidade do artefato final;
- satisfação e correções pedidas pelo usuário.

### Continuidade

- taxa de retomada correta depois de interrupção;
- ações externas repetidas indevidamente;
- tarefas perdidas ou duplicadas;
- tempo de recuperação.

### Eficiência

- tempo por resultado;
- custo e tokens por missão;
- uso de modelos pequenos versus fortes;
- quantidade de contexto recuperado;
- paralelismo útil versus retrabalho;
- ganho de equipe frente a um agente sob orçamento equivalente;
- custo total incluindo estudo, consolidação e avaliação.

### Aprendizado

- memórias recuperadas corretamente;
- skills reutilizadas;
- melhoria medida depois de uma promoção;
- regressões e rollbacks;
- redução de intervenção humana em tarefas repetidas;
- ganho em tarefas novas, em sessões novas, com e sem experiência retida;
- proporção de lições salvas, recuperadas e aplicadas com evidência;
- lacunas detectadas, competências demonstradas e tempo até demonstração;
- custo de aquisição e manutenção de cada competência;
- regressões por domínio, variação entre tentativas e desatualização de skills.

## 13. Roadmap — autonomia e aprendizado primeiro

As fases definem prioridade de construção e dependências. Recursos existentes da base podem ser
usados antes de sua fase de ampliação, desde que verificados na missão consumidora. Interface
mínima, ferramentas reais e observabilidade acompanham o núcleo desde a Fase 1. Não é necessário
concluir frota, voz ou escritório visual para demonstrar autonomia e aprendizado.

### Fase 0 — Fundação e identidade Nara

- base v0.23.1 congelada, identidade, comando e estado próprios;
- arquitetura e contrato de entrega registrados;
- baseline permissivo migrado para o PDP versionado `observe_only`, sem regras adicionais.

**Situação:** base herdada e identidade Nara consolidada. Validações atuais da migração são
registradas separadamente, sem transformar capacidades planejadas em recursos prontos.

### Fase 1 — Autonomia operacional e continuidade

- missão, tarefas, eventos, recibos e artefatos mínimos, com contrato de conclusão;
- uma líder, supervisor e ferramentas reais de arquivos, terminal e navegador;
- Capability Router mínimo, reaproveitando adapters existentes;
- execução por eventos, agendamento mínimo e diagnóstico de falta de progresso;
- checkpoint, retomada, IDs estáveis e versões de execução;
- intenção persistida, idempotência e reconciliação de resultados `unknown`;
- verificação objetiva, avaliador independente e gate terminal;
- CLI ou visão mínima do Desktop para progresso e artefatos;
- decisão documentada sobre durabilidade local mínima versus infraestrutura pronta.

**Gate:** uma missão útil executa várias etapas; o processo cai em pontos predeterminados, inclusive
após um efeito externo e antes do recibo. Ao reiniciar, a Nara reconcilia o resultado e continua
sem duplicação nos destinos suportados. Onde não houver prova, preserva a incerteza. A conclusão é
sustentada por artefatos inspecionados e estado observado.

#### Fase 1B — Primeira experiência por voz junto da autonomia

- reaproveitar captura, pre-roll, interrupção, recuperação e WebRTC herdados;
- nome, estados de presença e frase “Ei, Nara” definidos;
- manter o detector legado identificado como legado até existir modelo acústico próprio;
- benchmark PT-BR do detector, ASR, turnos e TTS;
- comparar caminho herdado com Pipecat restrito à mídia;
- comandos falados ligados à mesma sessão e missão de texto;
- separar interrupção de fala, correção do pedido e cancelamento da missão.

**Gate:** chamar a agente, iniciar uma tarefa, interromper a fala, corrigir o pedido e consultar a
mesma missão. Reconexão não duplica a solicitação; a voz só anuncia resultados comprovados. O
reconhecimento “Ei, Nara” só é considerado pronto após seu teste acústico, não pelo nome do arquivo.

### Fase 2 — Memória e aprendizado mínimo entre sessões

- arquivo episódico, memória com fonte, validade, correção e busca híbrida;
- recuperação do original depois de compactação;
- Experience Ledger e consolidação mínima em segundo plano;
- extração de procedimento de missão real e skill candidata versionada;
- bancada inicial com desenvolvimento e prova reservada separados;
- comparação em sessões novas com e sem experiência, sob condições equivalentes;
- promoção ou rejeição da skill conforme transferência, custo e regressões.

**Gate:** a missão A termina após uma interrupção e gera uma lição. Em nova sessão, a missão B,
diferente dos exercícios de desenvolvimento, recupera e aplica a lição com ganho frente ao baseline.
Uma correção posterior substitui a informação antiga sem fazê-la voltar como atual. Repetições e
traces distinguem ganho de aprendizado de variação aleatória.

**Primeira demonstração integrada:** executar → interromper → retomar → verificar → aprender →
resolver outra tarefa. Este é o marco prioritário antes de ampliar equipes, frota ou interfaces.

### Fase 3 — Lacunas de competência, estudo e prática autônomos

- System Competence Registry, distinto do registro de modelos;
- fila priorizada de lacunas com origem, diagnóstico, impacto e orçamento;
- pesquisa em documentação e exemplos, com objetivo de aprendizado explícito;
- exercícios e prática em ambiente de teste com feedback observável;
- teste de transferência reservado e atualização da competência demonstrada;
- reavaliação quando ferramentas, ambiente ou procedimentos mudarem.

**Gate:** uma falha real gera uma lacuna; Nara pesquisa, pratica e resolve um caso novo que antes
não resolvia, sem receber a solução do teste. Se não houver ganho, registra a tentativa e mantém
a competência como não demonstrada, em vez de promovê-la.

### Fase 4 — Evolution Lab e Learning Fabric ampliados

- otimização de skills com GEPA, Agent Lightning Skill e DSPy opcional;
- validar identidade entre variante avaliada, exportada e recarregada; pacote upstream somente após correção;
- ingestão progressiva de documentos, sites, áudio e vídeo, com procedência;
- separação entre estudo, desenvolvimento e prova; baseline e regressões por domínio;
- ampliação gradual para prompts, roteamento, ferramentas, plugins e código;
- mudanças em ambiente isolado, promoção versionada, canário e rollback;
- custo e benefício de cada experimento registrados no ledger;
- treinamento de pesos como experimento futuro opcional, sem bloquear esta fase.

**Gate:** uma variante melhora tarefas novas sob condições comparáveis, sem regressão fora dos
limiares definidos antes do experimento. Uma regressão injetada provoca rollback e preserva o estado.
Uma tarefa em andamento mantém suas versões ou usa migração explícita.

### Fase 5 — Equipes dinâmicas e roteamento multimodelo

- Agent Registry e Agent Factory com poucos papéis necessários;
- Model Capability Registry e seleção por resultados medidos;
- Specialist Resolver em cada missão e nova subtarefa, sem delegação obrigatória para pedidos simples;
- Legião-Local indexado por competências e carregado somente para os workers escolhidos;
- seleção conjunta de template, LLM, ferramentas e orçamento, com recibo e fallback;
- delegação com entradas, saídas, dependências e integração verificáveis;
- roteamento em camadas e workers locais paralelos;
- comparação de equipe versus um agente, incluindo comunicação e retrabalho.

**Gate:** em tarefas representativas, a equipe apresenta ganho medido de qualidade ou tempo dentro
do orçamento acordado. Tarefas sem benefício permanecem com uma agente. Quantidade de workers ou
diversidade de modelos, isoladamente, não conta como sucesso. Em um conjunto com competências
distintas, o resolver encontra um especialista existente do Legião, escolhe o modelo por evidência,
explica a decisão e supera ou iguala o baseline sem catálogo dentro do orçamento definido.

### Fase 6 — Acesso ampliado a aplicativos e frota

- ampliar os adapters de desktop, apps e máquinas remotas;
- inventário de máquinas e competências por ambiente;
- fila, lease, heartbeat, cancelamento, artifact handoff e reclaim;
- reconciliação de efeitos na troca de worker e diagnóstico de incompatibilidade;
- iOS experimental e Android posterior conforme demanda real.

**Gate:** uma máquina cai durante uma missão e outra retoma com os artefatos e versões corretos.
Efeitos confirmados não são repetidos; operações incertas são reconciliadas conforme o contrato do
destino. Capacidades indisponíveis no novo ambiente produzem replanejamento ou bloqueio explícito.

### Fase 7 — Voz integrada à mesma autonomia

- detector treinado para “Ei, Nara”, português e streaming;
- interrupção de fala, reconexão e providers substituíveis;
- mesma missão e memória usadas pelo texto;
- acompanhamento de trabalho longo e modo reunião opcional.

**Gate:** iniciar por voz, continuar por texto, interromper e reconectar preserva a mesma missão e
não duplica a solicitação. O trabalho segue sem depender da conexão de áudio.

**Implementado e verificado localmente:** o bridge de voz vincula texto e voz à mesma missão,
persiste estados de presença e reconexão e distingue solicitação, correção, interrupção apenas da
fala e cancelamento explícito da missão. Os recibos preservam hash e tamanho, não a transcrição em
claro. A promoção do detector acústico “Ei, Nara” continua bloqueada pelo próprio gate desta seção:
ela exige o conjunto PT-BR reservado e a medição no hardware real, e não é anunciada como concluída.

### Fase 8 — Desktop completo e escritório visual

- canais, tarefas, agentes, artefatos, competências e fila de estudo;
- memória, custos, avaliações e Evolution Lab observáveis;
- escritório 2D ou mapa como projeção dos eventos reais;
- controles de acompanhamento independentes da janela aberta.

**Gate:** cada estado visual corresponde a um evento persistido; fechar e reabrir a interface não
interrompe missões nem perde o histórico de execução e aprendizado.

**Implementado e verificado localmente:** o plugin `Nara Office` projeta somente os stores canônicos
de Mission Control, competências, frota e Evolution Lab. Missões, tarefas, leases, recibos,
artefatos, verificações e lacunas vêm de estado persistido; listas vazias aparecem como vazias e não
geram agentes decorativos. A API autenticada, o manifesto, o frontend e o teste de ausência de dados
fictícios fazem parte do plugin, sem acoplamento novo no core. O build Web real foi produzido e
servido em `127.0.0.1:9119`; a API autenticada respondeu `200` e projetou a missão de aceitação
concluída com um artefato e uma verificação aprovada.

### Trilha opcional A — Nara Trading Lab

Esta trilha é um módulo consumidor do core, não uma fase obrigatória para declarar a Nara funcional.
Ela poderá avançar em paralelo depois que os contratos necessários de missão, eventos, memória e
verificação estiverem operacionais.

#### A1 — Pesquisa e backtest reproduzível

- plugin carregado sob demanda e primeiro adapter de dados;
- laboratório, universo de ativos, benchmark e orçamento persistidos;
- equipe mínima de pesquisa e comitê com saídas tipadas;
- datasets versionados, prevenção de vazamento temporal, taxas e slippage;
- relatório com benchmark, drawdown, exposição, estabilidade e limitações.

**Gate:** outra execução com o mesmo dataset, código e configuração reproduz o resultado dentro da
tolerância declarada. O relatório distingue retorno bruto, custos e benchmark e preserva as fontes.

**Estado:** gate local aprovado pelo teste reproduzível do módulo. A prova financeira fora da
amostra continua sendo uma avaliação por laboratório e não uma alegação de vantagem de mercado.

#### A2 — Paper trading contínuo

- ingestão em tempo real, agenda de mercado e posições simuladas;
- Portfolio Engine e Risk Guard determinísticos;
- reconciliação de ordens simuladas, pausas, retomada e kill switch;
- painel e sala visual alimentados por eventos reais do laboratório;
- avaliação em período futuro, não usado para escolher a estratégia.

**Gate:** o laboratório opera pelo período definido antes do teste sem capital real, respeita todos
os limites, reconcilia quedas e reporta desempenho líquido e falhas. Nenhuma ordem chega à corretora.

**Estado:** motor, ledger, limites, idempotência, pausa e kill switch estão implementados. O período
futuro contínuo será medido quando uma fonte de cotações paper for configurada; nenhuma ordem real é
tecnicamente possível no módulo atual.

#### A3 — Execução live condicionada

- adapter de corretora validado em ambiente de teste;
- credenciais e conta isoladas por laboratório;
- limites por ordem, ativo, período, perda, exposição e concentração;
- aprovação, pausa, desligamento e auditoria conforme a política futura;
- rollout canário com capital e universo explicitamente limitados.

**Gate:** depende da Fase 9, de autorização explícita e de critérios financeiros e operacionais
definidos antes do canário. A existência de lucro em backtest ou paper não promove o modo live.

### Trilha opcional B — Nara Reverse Engineering Lab

Esta trilha começa com a integração REA já instalada e amplia a experiência como módulo nativo da
Nara. Ela não bloqueia as fases principais.

#### B1 — Artefatos estáticos e evidência

- manter REA fixado, habilitado e descoberto pelo runtime;
- rotear automaticamente entre código-fonte normal, JavaScript/Electron, .NET e binário nativo;
- usar Ghidra para uma fixture nativa e REA estático para uma fixture Electron/JavaScript;
- guardar hashes, plano, ferramentas chamadas, evidências e limitações como artefatos da missão;
- verificar uma conclusão repetindo a inspeção em sessão nova.

**Gate:** pedidos em linguagem natural escolhem a rota correta sem carregar todas as ferramentas;
duas classes de artefato produzem conclusões verificáveis e repetíveis, ligadas ao original.

**Estado:** gate local aprovado com fixture JavaScript/Electron e binário nativo próprio. O roteador
preservou hashes, selecionou REA estático e REA+Ghidra, e a análise externa repetível produziu
evidência sem modificar os originais.

#### B2 — Android, firmware e runtime controlado

- configurar e validar providers adicionais somente quando houver caso consumidor;
- separar inspeção estática, execução, debugger, instrumentação e modificação de dispositivo;
- integrar capturas de rede e processo ao Event Log e Receipt Store;
- impedir operações mutáveis em execuções não assistidas.

**Gate:** uma investigação de teste atravessa análise estática e observação controlada sem alterar o
artefato original; cada efeito possui recibo e o sistema recupera a sessão após interrupção.

#### B3 — Reconstrução independente

- transformar evidências em especificação comportamental;
- implementar a função no projeto de destino sem copiar artefato não autorizado;
- comparar original e reconstrução por testes e casos observáveis;
- registrar incertezas e diferenças conhecidas.

**Gate:** uma função reconstruída passa por testes definidos antes da implementação e cada decisão
técnica importante aponta para evidência ou requisito próprio, não para suposição do modelo.

### Fase 9 — Segurança e políticas próprias

- especificação própria de segurança, autoridade e permissões;
- módulo central de políticas, regras de confirmação e explicações;
- autenticação, proteção de segredos, isolamento de perfis e integrações;
- privacidade, telemetria, retenção, exclusão e exportação;
- testes de consistência em CLI, voz, gateway, subagentes e execução remota.

**Gate:** critérios serão definidos no documento separado desta fase. A implementação das regras
será comprovada em todas as superfícies antes de considerá-las prontas.

**Implementado e verificado localmente:** a especificação está em
`docs/NARA_POLICY_SPEC.md`. O PDP versionado oferece `allow`, confirmação exata de uso único e
`deny`, com explicação, promoção atômica e rollback. CLI, voz, gateway, subagente e frota produziram
a mesma decisão nas provas reservadas. Alvos dos recibos de política são hashes; recibos de efeitos
removem segredos. Telemetria, transcrição, câmera e biometria começam desligadas e a retenção de
mídia começa em zero. O perfil distribuído continua `observe_only`, sem regras adicionais e sem
recusas próprias, até o proprietário aprovar um conjunto de produção e os atores dos gateways/VPS
serem validados no ambiente de destino.

### Fase 10 — Produto distribuível e operação sustentável

- repositório, releases e instaladores próprios;
- atualização e rollback com compatibilidade de missões em andamento;
- documentação de usuário, diagnóstico e recuperação;
- backup e restauração de missões, memória, skills e avaliações;
- validação de instalação e atualização nas plataformas escolhidas.

**Gate:** instalar, atualizar, retomar uma missão e restaurar backup preserva o estado e as versões
necessárias. A distribuição pública usa também os critérios definidos na Fase 9.

**Implementado e verificado localmente:** a operação está documentada em
`docs/NARA_OPERATIONS.md`. O instalador e o updater existentes continuam sendo a autoridade; o
manifesto Nara acrescenta hashes do Mission Control, memória temporal, avaliações, documentação e
instaladores. A prova vertical cria uma missão em execução, memória, skill aprendida e resultado de
holdout, executa o backup/importador reais e confirma os quatro no perfil restaurado. Publicação e
assinatura não são executadas automaticamente; exigem autorização explícita e um commit limpo. A
validação Linux/VPS permanece um gate de ambiente até a máquina prometida ser fornecida. No macOS,
o gateway foi instalado como LaunchAgent e comprovado sob supervisão do `launchd`.

## 14. Riscos principais

| Risco | Resposta prevista |
| --- | --- |
| Muitas funções que não conversam | autoridade única de missão, contratos e testes verticais |
| Agente afirma que terminou sem terminar | verificador independente e gate terminal |
| Perda de contexto | estado fora do prompt, artefatos, memória com fonte e checkpoints |
| Ação externa duplicada ou incerta | intenção durável, deduplicação no destino e reconciliação de `unknown` |
| Custo excessivo | roteamento em camadas, orçamento e ledger |
| Centenas de skills degradam o agente | catálogo sob demanda e eval de admissão |
| Memória errada se torna verdade | fonte, validade, confiança, correção e `supersedes` |
| Autoevolução quebra o produto | versões por execução, isolamento, baseline, canário e rollback |
| “Aprender” apenas repete exercícios | sessões novas, prova reservada e controle com/sem experiência |
| Mais agentes aumentam custo e retrabalho | comparação com uma agente e delegação seletiva |
| Especialista ou LLM errado para a tarefa | resolução por competência observada, recibo da escolha, fallback e comparação com baseline |
| Verificador repete o erro do executor | priorizar medições objetivas e preservar `inconclusive` |
| Catálogo afirma capacidade não demonstrada | prova por ambiente, validade e reavaliação |
| Dependência de um provider | providers substituíveis e registry de capacidades |
| Interface vira apenas demonstração | dados somente de endpoints e eventos reais |
| Segurança de máquinas e integrações | especificação e validação separadas na Fase 9 |
| Conteúdo de estudo incorreto | procedência, verificação de fontes e teste de competência; regras de autoridade na Fase 9 |

## 15. Diferenciais esperados

1. **Missões que sobrevivem à conversa e ao reinício.**
2. **Conclusão comprovada por agente independente.**
3. **Equipe criada conforme a necessidade, com modelos diferentes.**
4. **Memória recuperável com fonte, validade e correção.**
5. **Acesso integrado a terminal, navegador, Desktop, voz e máquinas remotas.**
6. **Escritório visual refletindo trabalho real.**
7. **Aprendizado entre sessões desde as primeiras fases, ampliado depois para multimodal.**
8. **Evolução automática com baseline, canário e rollback.**
9. **Detecção de lacunas, estudo autônomo e competência demonstrada em tarefas novas.**
10. **Uma autoridade de missão, com infraestrutura substituível e sem estados concorrentes.**
11. **Segurança, privacidade e políticas próprias em módulo central versionado.**
12. **Módulos de domínio, como Trading Lab, que reutilizam a mesma autonomia sem inflar o core.**
13. **Legião usado como catálogo vivo, com especialista e LLM escolhidos por evidência.**
14. **Engenharia reversa integrada por REA, Ghidra e reconstrução rastreável.**

## 16. Definição de produto final

Nara estará pronta como produto quando uma pessoa puder:

1. chamar a agente por texto ou voz;
2. entregar uma missão de várias horas;
3. acompanhar agentes e tarefas em tempo real;
4. fechar a interface ou reiniciar a máquina;
5. voltar e encontrar a missão no estado correto;
6. receber um resultado com arquivos, fontes, custos e provas;
7. pedir explicação de cada decisão;
8. corrigir uma memória ou política;
9. reutilizar o que foi aprendido em uma missão nova, com ganho demonstrado;
10. identificar lacunas e acompanhar estudo, prática e prova de competência;
11. distinguir capacidades demonstradas de planos, hipóteses e tentativas sem ganho;
12. atualizar ou reverter o sistema sem perder o estado ou alterar silenciosamente missões em curso;
13. ativar módulos de domínio sem criar outra memória, outra líder ou outro produto desconectado;
14. entender por que um especialista e um modelo foram escolhidos para cada tarefa delegada.

## 17. Diretrizes de implementação

Estas diretrizes orientam o datasheet atualizado. Não representam implementação concluída nem
autorização de publicação, alteração de políticas ou execução de ações externas.

### Arquitetura e continuidade

- Manter Nara como núcleo e uma autoridade sobre cada missão.
- Permitir bibliotecas e infraestrutura durável sem uma segunda líder ou fonte concorrente de estado.
- Construir primeiro execução real, retomada, reconciliação, recibos, artefatos e verificação objetiva.
- Associar versões de plano, skill, adapter e configuração às execuções.

### Aprendizado e autonomia

- Entregar aprendizado mínimo entre sessões na Fase 2 e estudo ativo na Fase 3.
- Manter originais pesquisáveis, procedência, validade e correções de memória.
- Separar estudo, desenvolvimento e prova; avaliar transferência com e sem experiência retida.
- Manter registro das competências do sistema e fila priorizada de lacunas.
- Consultar Legião, skills e módulos antes de criar um especialista novo.
- Escolher template e LLM separadamente, usando resultados medidos da combinação completa.
- Registrar a justificativa do roteamento e atualizar sua evidência após verificação.
- Expandir para multimodal e evolução do sistema após provar o ciclo mínimo.
- Tratar treinamento de pesos como linha futura opcional.

### Escala, acesso e interfaces

- Priorizar adapters observáveis de API, terminal, DOM e acessibilidade.
- Ampliar equipes e modelos somente quando houver ganho medido.
- Construir frota depois do ciclo de continuidade e aprendizado.
- Manter voz e texto ligados à mesma missão; escritório visual projeta eventos reais.
- Permitir fechar a interface sem interromper o trabalho.
- Implementar domínios especializados como plugins consumidores dos contratos do core.
- Manter pesquisa, backtest, paper e live como modos distintos no Trading Lab.

### Evolução, segurança e produto

- Avaliar mudanças em ambiente separado, com baseline, versões e rollback.
- Deixar segurança e políticas próprias para a Fase 9, em especificação separada.
- Manter confiabilidade de execução e integridade do estado desde a Fase 1.
- Preparar distribuição própria na Fase 10, após os gates aplicáveis.

## 18. Decisões de produto consolidadas

| Tema | Decisão para implementação |
| --- | --- |
| Nome | Nara; nome técnico `nara`, pacotes `nara_*`, variáveis `NARA_*` |
| Estado e projeto | `/Users/fate/Desktop/Nara`; estado por perfil em `~/.nara` |
| Ativação | “Ei, Nara”; detector próprio a treinar e validar |
| Personalidade | Próxima, calma, objetiva e clara; português brasileiro como experiência inicial |
| Líder e especialistas | Nara é a líder; workers são identificados pelo papel e pela missão |
| LLM de raciocínio | Serviço substituível por provider; memória e missões pertencem ao runtime Nara |
| Áudio inicial | Local no Mac como caminho prioritário; cloud opcional por adapter |
| Voz e aprendizado | Prova mínima de voz na Fase 1B; aprendizado entre sessões na Fase 2 |
| Modelos de áudio | Baselines e finalistas da seção 21; escolha operacional determinada pelo benchmark |
| Primeiro sistema | macOS e Apple Silicon; Windows preservado no código e validado antes de distribuição |
| Canais | CLI e Desktop primeiro; gateways existentes reaproveitados conforme missão consumidora |
| Primeira frota | Uma máquina local; inventário e expansão após continuidade e aprendizado |
| Interface | Nara Office funcional como projeção autenticada do estado canônico; animações futuras não criam um segundo runtime |
| Especialistas | Resolver consulta Legião, skills, módulos e competências; escolhe template e LLM por resultados medidos |
| Trading Lab | Plugin opcional; pesquisa e backtest primeiro, paper depois e live somente após gates e Fase 9 |
| Reverse Engineering Lab | REA oficial como ferramenta; Ghidra atual para nativos; demais providers somente por demanda validada |
| Segurança e políticas | PDP e privacidade implementados; perfil inicial `observe_only`, regras futuras exigem promoção explícita |
| Distribuição | Repositório, documentação Pages e instalador de fonte públicos; instaladores assinados e feeds ainda dependem dos respectivos gates da Fase 10 |

Credenciais, orçamento, máquinas adicionais e contas de mensageiros são parâmetros de instalação,
não pendências da arquitetura. A primeira prova usa arquivos locais e destinos de teste; limites
numéricos de custo e latência são declarados por experimento, antes da execução. As políticas de
retenção e autoridade continuam reservadas ao documento próprio da Fase 9.

## 19. Próxima entrega e critério de prioridade

As provas locais das Fases 1 a 10 e das trilhas A1/A2 e B1 foram implementadas. A documentação,
o manifesto e o pacote local foram registrados, e o repositório, o site Pages e seus catálogos estão
públicos e foram validados por HTTP em 2026-11-25. Depois vêm a instalação e os gates de
**implantação externa**: repetir o failover em VPS/SSH, medir
o wake word com dataset PT-BR, ligar apenas as contas e providers escolhidos e executar o período
paper em dados futuros. Cada resultado volta ao mesmo Mission Control, Event Log, Receipt Store,
memória, política e Nara Office.

A prova integrada local já demonstrou:

> Nara recebe uma tarefa, executa, é interrompida, retoma, entrega evidências, extrai um
> procedimento e melhora o desempenho em uma tarefa nova usando o que aprendeu.

Os próximos passos não alteram a arquitetura aprovada. Eles promovem capacidades dependentes do
ambiente somente depois de repetir seus gates com dados, credenciais e máquinas reais.

## 20. Referências para implementação

Fontes consultadas na análise de 2026-11-17. Descrevem referências externas, não validação do código
Nara. Versões e compatibilidade deverão ser verificadas quando cada integração for construída.

- [Procedência da base](UPSTREAM_PROVENANCE.md): origem, commit e licença.
- [Letta — Memory & dreaming](https://docs.letta.com/configuration/memory): consolidação em segundo plano.
- [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence): persistência e retomada.
- [LangGraph — Fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance): retries, efeitos externos e resultado desconhecido.
- [Temporal — Activity Definition](https://docs.temporal.io/activity-definition): execução durável, retries e idempotência no destino.
- [DSPy — GEPA](https://github.com/stanfordnlp/dspy/blob/main/docs/docs/api/optimizers/GEPA/overview.md): otimização de componentes textuais com feedback de execução.
- Candidato upstream de autoevolução, identificado na pesquisa técnica: referência de otimização de skills, com outros alvos ainda planejados no README consultado.
- [PAST-Bench — artigo](https://arxiv.org/abs/2608.04003) e [código](https://github.com/Gen-Verse/PAST-Bench): avaliação longitudinal e comparação com/sem experiência.
- [Anthropic — Multi-agent research system](https://www.anthropic.com/research/multi-agent-research-system): benefícios, custos e limites de equipes de agentes.
- [Aivy](https://github.com/jmgomezl/aivy): referência de escritório visual, contas de agentes, limites de gasto e eventos verificáveis.
- [Crewless Capital](https://github.com/enuno/crewless-capital): separação entre artefatos analíticos de LLM e serviços determinísticos de risco, carteira e execução.
- [AI Market Maker](https://github.com/olaxbt/ai-market-maker): mesas especializadas, veto de risco, backtests, benchmarks e rastreabilidade.
- [AIRP](https://github.com/Aditya083103/AIRP---Autonomous-Investment-Research-Platform): comitê multiagente, contraditório e visualização do fluxo de análise.
- [REA — Reverse Engineer Anything](https://github.com/morluto/rea): MCP, CLI, evidências e fluxos de investigação de artefatos e comportamento.
- REA externo fixado em `plugin-catalog/rea.yaml`: pacote portátil, skill adaptada e servidor REA fixado para o runtime da Nara.

## 21. Componentes selecionados e contratos de integração

As decisões abaixo fecham a direção técnica. Uma seleção para benchmark não equivale a recurso
pronto. Cada incorporação usa plugin, adapter, provider ou serviço com consumidor real; o núcleo
Nara permanece a autoridade sobre sessão, missão, memória, efeitos e conclusão.

### 21.1 Presença e voz

| Camada | Direção escolhida | Alternativa e prova |
| --- | --- | --- |
| Presença | Estados `armed`, `listening`, `thinking`, `speaking`, `followup`, `reconnecting` e `mic_unavailable` | Estado deriva da captura e da missão reais |
| Nome | Adapter pyopen-wakeword existente com detector próprio “Ei, Nara” | Sherpa/micro-wake-word se o benchmark justificar; idioma do modelo é verificado |
| Mídia | Reutilizar o caminho herdado e comparar Pipecat como serviço restrito à voz | LiveKit é alternativa; evitar duas autoridades de conversa |
| Início e fim de fala | Silero VAD + Smart Turn como primeiro protótipo | Fim de turno sem cortar hesitações, com avaliação PT-BR |
| ASR no Mac | Whisper por MLX/whisper.cpp como baseline | Qwen3-ASR como finalista comparativo |
| TTS no Mac | Kokoro como baseline leve; Qwen3-TTS 0.6B como primeiro finalista | VoxCPM2 e OmniVoice depois, se houver ganho; Piper como fallback avaliado |
| Full duplex local | Haru em experimento separado | Modelo base de pesquisa; exige ponte e fidelidade ao backend antes de promoção |
| Cloud opcional | Adapter GPT-Live já presente como caminho comparativo | Backend permanece escolhido separadamente; não torna cloud uma dependência |

A presença e o áudio podem continuar enquanto a Nara trabalha numa missão. O fluxo mantém IDs de
sessão, turno, missão, delegação e geração de áudio. Uma interrupção invalida áudio atrasado sem
repetir a tarefa. “Pare de falar” interrompe reprodução; “cancele a missão” é uma transição distinta.
Correções atualizam a tarefa existente e preservam efeitos confirmados.

A frase configurada não certifica o modelo. O runtime não carrega um detector de outra identidade
como se fosse Nara. O detector próprio só será promovido após exemplos positivos e negativos em
português.

### 21.2 Continuidade e operação

Reusar goals, Kanban, SessionDB, scheduler, delegação, captura e verificador atuais. O Mission
Control acrescenta contrato de missão, eventos e referências a esses componentes. Comparar execução
durável mínima local com Temporal quando sua infraestrutura compensar; nenhum motor adicional vira
uma segunda líder. Extrair os padrões de progresso incremental e passagem de contexto dos
harnesses de longa duração da Anthropic.

O verificador recebe evidências diretamente, não somente o relato do executor. Arquivos devem ser
reabertos, programas executados e destinos consultados conforme o critério. O recebimento local de
um resultado não substitui reconciliação de uma operação `unknown`.

O Capability Router compara agent-browser, Browser Use, agent-desktop e Cua por tarefa. CLI-Anything
é candidato para aplicações de domínio. OpenHands pode ser worker especializado, quando houver
consumidor e benefício medido. Equipes e frota dependem de ganho frente a uma agente.

### 21.3 Memória, prática e evolução

A primeira melhoria usa o mesmo LLM e muda fatos ou procedimentos. Experience Ledger conecta
resultado observado, lição, skill, reuso e avaliação. System Competence Registry mede a competência
da Nara inteira e alimenta a fila de lacunas: falhar → diagnosticar → estudar → praticar → provar
em tarefa nova. OpenMAIC contribui com o método pedagógico, sem trazer outro runtime.

A memória atual é o baseline. Hindsight é o primeiro candidato de memória de experiência; Letta
inspira consolidação; Graphiti atende relações temporais se a demanda justificar. Mem0 e OpenViking
ficam como comparativos. Escolher uma autoridade para cada informação, sem instalar todas essas
memórias em paralelo. Lossless Claw e Headroom fornecem padrões de contexto recuperável, adaptados
à fonte de verdade da Nara.

GEPA e Agent Lightning Skill orientam o Evolution Lab. Variantes devem mudar o artefato que será
exportado, recarregado e usado no runtime real. O pipeline upstream de autoevolução fica condicionado
à correção e à prova desse vínculo. DGM e Darwinian Evolver são referências posteriores para código.
Treinamento de pesos permanece um experimento separado, opcional.

O catálogo Legião-Local alimenta templates privados de competências, carregados sob demanda. Suas
91 instruções não são 91 workers em execução. Materiais EVE, o projeto legado, JARVIS-Kit e pesquisas
anteriores fornecem partes e contratos; o núcleo Nara continua único.

### 21.4 Memory Gateway e Trading Lab

O Nara Memory Gateway será a fronteira de interoperabilidade da memória. MCP e API serão projeções
do armazenamento canônico, com autenticação e permissões adicionadas na Fase 9. Clientes externos
podem buscar, recuperar originais e propor alterações; somente o pipeline da Nara promove memória
durável. Toda recuperação relevante gera recibo com consulta, filtros, itens, versões e fontes.

O Trading Lab será distribuído como plugin de domínio e serviço opcional. Seu manifesto declarará
adapters, modelos, dados, corretoras e modos disponíveis. O plugin consome APIs publicadas do core;
o core não importa o Trading Lab. Estado financeiro detalhado fica no serviço do laboratório, com
referências nos eventos, recibos e artefatos canônicos da missão.

Padrões selecionados para protótipo:

- escritório e atividade financeira observável inspirados no Aivy, sem presumir sua arquitetura;
- artefatos tipados e separação determinística de risco e execução do Crewless Capital;
- Risk Guard, benchmarks e rastreabilidade do AI Market Maker;
- comitê, contraditório e fluxo ao vivo do AIRP;
- Mission Control, memória, verificador, evolução e escritório visual permanecem da Nara.

O primeiro consumidor será um laboratório de pesquisa/backtest com dados públicos ou de teste. Um
adapter de paper trading será o segundo. Nenhum adapter live será requisito do primeiro release e
nenhuma credencial real será necessária para provar a arquitetura.

### 21.5 Specialist Resolver, Legião e REA

O Specialist Resolver será uma etapa do planejamento, não um novo agente permanente. Ele recebe o
contrato de tarefa e consulta índices leves antes de qualquer instrução extensa entrar no prompt.
O índice do Legião conterá identificador, competências, entradas, saídas, ferramentas, modalidades,
pré-condições, domínio, custo esperado, versão e resultados observados. O texto completo do template
será carregado somente depois da seleção.

A escolha do LLM será independente do template. Model Capability Registry fornecerá resultados por
tipo de tarefa; System Competence Registry fornecerá resultados da combinação completa. O resolver
produzirá candidatos e uma decisão tipada. Agent Factory materializará o worker, e Mission Control
continuará dono da missão. Experience Ledger atualizará a evidência para roteamentos futuros.

Contrato mínimo de decisão:

```text
tarefa + critério de conclusão
  -> competências e ferramentas necessárias
  -> candidatos do Legião, skills e módulos
  -> modelos capazes e disponíveis
  -> estimativa de ganho, custo e latência
  -> execução direta | especialista | pequena equipe
  -> recibo da seleção
  -> resultado verificado
  -> atualização da competência observada
```

REA é o primeiro exemplo concreto desse contrato. Uma tarefa sobre artefato empacotado ativa a
skill `reverse-engineer-anything`; o tipo de alvo restringe as ferramentas; o especialista do
Legião fornece método e conhecimento de domínio; o modelo escolhido raciocina sobre a evidência;
e a Nara integra, verifica e preserva o resultado. Para um repositório com fonte completa, o mesmo
resolver evita REA e usa as ferramentas normais de código.

O pacote REA permanece fora do core em `~/.nara/plugins/rea`. Sua origem e commit ficam registrados
no catálogo, e seu MCP é descoberto pela infraestrutura portátil de plugins. A Nara não mantém uma
cópia própria das 207 ferramentas nem codifica nomes específicos no loop central.

## 22. Aceitação da voz e do aprendizado

Metas iniciais propostas para calibrar no Mac M4 de 24 GB, não medições já obtidas:

| Prova | Critério de início |
| --- | --- |
| Detector “Ei, Nara” | Pelo menos 100 chamadas em cenários definidos; alvo de 95% de detecção |
| Falsos disparos | Pelo menos 8 horas de negativos; alvo de até 1 disparo no conjunto, sem extrapolar garantia estatística |
| Interrupção | 50 casos, preservando o começo da fala; medir p50/p95 de detecção e silêncio do bot |
| Primeira resposta curta | Alvos iniciais: p50 até 1,2 s e p95 até 2,5 s após fim de fala, no perfil avaliado |
| Parada da fala | Alvo inicial p95 até 400 ms após começo de interrupção detectável |
| Português | Nomes, valores, horários, números, hesitações e comandos longos; separar erros críticos do WER médio |
| Recuperação | Queda de áudio, sleep/wake e troca de microfone não duplicam pedidos nem perdem missão |
| Aprendizado | Tarefa A gera lição; nova sessão B reservada melhora frente ao controle sem experiência |
| Evolução | Variante exportada é a avaliada; regressão injetada provoca rollback e preserva estado |
| Memory Gateway | Dois clientes recuperam a mesma memória válida e o original; correção substitui a versão anterior sem apagar o histórico |
| Trading backtest | Dataset, código e configuração versionados reproduzem resultado; taxas, slippage e benchmark aparecem separados |
| Trading paper | Período futuro definido previamente, zero ordens reais, limites respeitados e quedas reconciliadas sem duplicação |
| Trading live | Fora do primeiro release; exige Fase 9, autorização explícita, canário limitado, kill switch e recibo da corretora |
| Especialista do Legião | Tarefas distintas recuperam poucos candidatos, carregam somente o escolhido e registram o motivo da escolha |
| Especialista + LLM | Modelo escolhido por capacidade observada; fallback funciona e a combinação é comparada ao baseline direto |
| REA discovery | Plugin habilitado aparece como MCP portátil; handshake informa REA 6.7.0 e 207 ferramentas |
| REA estático | Fixture Electron/JavaScript e fixture nativa geram evidência reproduzível sem alterar o original |

CPU, memória, energia, inicialização e custo total entram nas comparações. A bancada separa estudo,
desenvolvimento e prova reservada, mantém condições equivalentes e registra resultados negativos.

Referências e decisões detalhadas: `research/AUDITORIA_VOZ_AUTONOMIA_APRENDIZADO_2026-11-17.md`,
`research/OPEN_SOURCE_CANDIDATES_2026-11-17.json` e
`research/IMPLEMENTATION_BACKLOG_2026-11-17.json`. O roteiro definitivo deste datasheet prevalece
sobre cronogramas históricos; as provas de aceitação determinam a disponibilidade de cada recurso.
