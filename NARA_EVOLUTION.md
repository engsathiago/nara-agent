# Nara Evolutiva — arquitetura-alvo

> Identidade definitiva: **Nara**. A especificação consolidada está em
> [NARA_DATASHEET.md](NARA_DATASHEET.md), versão 1.0. Ela prevalece para fases,
> prioridades, seleção de componentes e critérios de entrega. Segurança e políticas
> próprias permanecem na etapa posterior separada. Este documento detalha contratos.

> A seleção exata de componentes, as decisões de reutilizar/adaptar/reescrever e
> os gates que impedem funcionalidades apenas aparentes estão definidos em
> [`NARA_BUILD_CONTRACT.md`](NARA_BUILD_CONTRACT.md).

## Visão

A Nara deve funcionar como uma agente líder persistente. Ela recebe uma missão,
mantém o estado do trabalho por horas ou dias, reúne a informação necessária,
cria uma equipe temporária de agentes especializados, executa ações no computador,
verifica os resultados e transforma experiências úteis em memória, skills e
melhorias mensuráveis.

Autonomia não significa manter um modelo respondendo em um loop. O sistema precisa
possuir estado durável, critérios de conclusão, recuperação após falhas, evidências
das ações e um processo controlado para promover mudanças em si próprio.

O objetivo operacional é:

> Dada uma missão e um contrato de conclusão, a Nara consegue planejar,
> executar, verificar, retomar após interrupção e aprender um procedimento
> reutilizável, preservando o histórico original e a origem de cada decisão.

## Princípios

1. **A missão é a autoridade.** Toda subtarefa, agente e ação aponta para uma
   missão, um resultado esperado e uma evidência de conclusão.
2. **O estado vive fora do contexto do modelo.** Plano, fila, artefatos,
   processos, checkpoints e resultados sobrevivem à conversa e ao processo.
3. **Contexto é uma projeção, não o banco de dados.** O modelo recebe somente o
   contexto necessário para o passo atual; o histórico integral permanece
   pesquisável e recuperável.
4. **Agentes são criados por capacidade.** A líder monta equipes temporárias de
   planejadores, pesquisadores, executores e verificadores conforme a missão.
5. **Toda ação produz um recibo.** O recibo registra intenção, ferramenta,
   alvo, resultado observado, artefatos e forma de verificação.
6. **Aprendizado precisa de evidência.** Uma memória ou skill informa sua
   origem, confiança, validade e o resultado que a justificou.
7. **Evolução passa por experimento.** Mudanças em prompt, skill, roteamento,
   plugin ou código são comparadas com uma linha de base antes da promoção.
8. **O modelo é substituível.** A Nara escolhe modelos por capacidade,
   custo, latência e histórico de sucesso sem entregar o estado do sistema ao
   provedor.
9. **Política fica centralizada.** O módulo de política decide autoridade e
   limites; os mecanismos de execução cuidam de integridade, recuperação e
   verificação.

## Arquitetura

```text
Pessoa / voz / desktop / canais / API
                    │
                    ▼
          ┌───────────────────────┐
          │ Nara Mission Control  │
          │ missão, estado, fila  │
          └───────────┬───────────┘
                      │
       ┌──────────────┼──────────────┐
       ▼              ▼              ▼
  Contexto e      Líder e equipe   Política e
  memória          de agentes      orçamento
       │              │              │
       └──────────────┼──────────────┘
                      ▼
          ┌───────────────────────┐
          │ Capability Router     │
          │ API, terminal, web,   │
          │ browser, desktop, voz │
          └───────────┬───────────┘
                      ▼
          recibos, artefatos e traces
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
   Verificador independente   Evolution Lab
   testes e evidências        memória/skill/código
```

### 1. Nara Mission Control

É o núcleo durável da autonomia. Uma missão contém:

- objetivo e contrato de conclusão;
- restrições, orçamento e prazo;
- grafo de tarefas e dependências;
- estado atual e próximo passo seguro;
- agentes responsáveis e recursos em uso;
- artefatos esperados e evidências obtidas;
- bloqueios, tentativas, falhas e decisões;
- checkpoint de retomada e condição de parada.

Estados mínimos: `draft`, `planned`, `running`, `waiting`, `verifying`,
`completed`, `failed`, `cancelled` e `needs_input`.

Cada transição gera um evento imutável. O estado atual é uma projeção desses
eventos. Isso permite recuperar uma missão após queda do processo, explicar por
que uma decisão foi tomada e evitar repetir uma ação externa já concluída.

### 2. Agente líder e equipes temporárias

A líder não precisa executar tudo. Ela decompõe a missão, seleciona capacidades,
atribui tarefas e integra os resultados. Os papéis são modelos reutilizáveis,
instanciados somente quando necessários:

- **planner:** constrói e atualiza o grafo de trabalho;
- **researcher:** busca fontes e preserva citações;
- **executor:** usa ferramentas e produz artefatos;
- **browser/desktop operator:** atua em páginas e aplicativos;
- **verifier:** testa o resultado sem confiar no relato do executor;
- **critic:** procura lacunas, conflitos e conclusões sem evidência;
- **memory curator:** extrai decisões, preferências e experiências;
- **skill builder:** converte procedimentos repetíveis em skills;
- **watchdog:** acompanha jobs, prazos, travamentos e retomadas;
- **model router:** seleciona modelo e provedor para cada tipo de trabalho.

Cada agente recebe um pacote limitado: tarefa, contexto necessário, ferramentas,
orçamento, critérios de conclusão e formato de entrega. O resultado volta como
um artefato estruturado, não como uma conversa solta.

A líder pode criar uma nova definição de agente quando nenhum papel existente
cobre a tarefa. A definição deve declarar capacidades, ferramentas, contexto,
saída esperada, orçamento e teste de aceitação.

### 3. Memória em cinco camadas

| Camada | Conteúdo | Escopo e retenção |
| --- | --- | --- |
| Trabalho | próximo passo, hipóteses, dados temporários | missão atual |
| Episódica | eventos, tool calls, recibos e conversas originais | histórico permanente pesquisável |
| Semântica | pessoas, projetos, decisões, preferências e fatos temporais | entre sessões, com origem e validade |
| Procedimental | skills, playbooks e automações verificadas | reutilizável e versionada |
| Reflexiva | falhas recorrentes, estratégias e critérios de roteamento | promovida somente após avaliação |

O sistema nunca depende apenas de um sumário. Mensagens e resultados originais
permanecem no arquivo episódico. Sumários e memórias apontam para suas fontes e
podem ser expandidos quando um detalhe for necessário.

Cada registro durável deve guardar:

- identidade e escopo (`user`, `project`, `mission`, `agent`);
- tipo, conteúdo e entidades relacionadas;
- fonte e trecho de evidência;
- data de criação e intervalo de validade;
- confiança e agente responsável;
- relação `supersedes` quando substituir informação anterior;
- uso posterior e impacto observado.

### 4. Contexto contínuo

O contexto de cada chamada é montado a partir de:

1. instruções estáveis e identidade da Nara;
2. missão e contrato de conclusão;
3. estado resumido e próximo passo;
4. memórias recuperadas para a tarefa;
5. artefatos ou trechos originais necessários;
6. mensagens recentes e resultados ainda ativos.

Quando o limite se aproxima, o sistema usa uma escada:

1. remove resultados grandes já salvos como artefatos;
2. compacta segmentos concluídos mantendo referências às fontes;
3. cria checkpoints hierárquicos da missão;
4. recupera sob demanda detalhes arquivados.

A compactação nunca substitui o arquivo original e nunca é usada como prova de
que uma ação ocorreu.

### 5. Capability Router e acesso ao sistema

O roteador escolhe a menor camada capaz de concluir e verificar a ação:

1. API ou conector estruturado;
2. ferramenta de arquivos ou terminal;
3. automação de navegador por DOM/CDP;
4. controle visual e acessibilidade do aplicativo;
5. interação humana quando o sistema não consegue observar o resultado.

Cada capacidade declara disponibilidade, custo, latência, efeitos, suporte a
cancelamento, método de verificação e idempotência. A Nara pode combinar
camadas na mesma tarefa: consultar uma API, preparar um arquivo, abrir um
aplicativo e confirmar visualmente o resultado.

### 6. Verificação independente

O executor não decide sozinho que terminou. O contrato de conclusão define
evidências como:

- teste ou comando com resultado esperado;
- arquivo com conteúdo ou hash verificável;
- consulta de leitura após uma escrita;
- estado observado em página ou aplicativo;
- comparação antes/depois;
- segunda fonte para uma afirmação factual;
- avaliação humana quando o resultado é subjetivo.

O verificador recebe o objetivo, o contrato e os artefatos, mas não a conclusão
do executor como fato. Ele devolve `pass`, `fail` ou `inconclusive`, com as
evidências. Somente `pass` conclui a missão automaticamente.

## Ciclo de evolução contínua

```text
experiência → classificação → hipótese de melhoria → variante
     → execução isolada → avaliação contra baseline
     → promoção, revisão ou descarte → monitoramento de regressão
```

### Níveis de evolução

| Nível | Mudança | Promoção |
| --- | --- | --- |
| E0 | contexto de trabalho | expira com a missão |
| E1 | memória e preferência | evidência + escopo + validade |
| E2 | skill ou playbook | replay bem-sucedido em caso real ou fixture |
| E3 | prompt, roteamento ou configuração | comparação com dataset e rollback |
| E4 | plugin ou código da Nara | branch isolada, testes e verificação independente |
| E5 | ajuste ou treinamento de modelo | dataset versionado, benchmark e análise de regressão |

Uma melhoria não é promovida porque o agente acredita que ficou melhor. O
Evolution Lab compara a variante com a versão ativa usando tarefas reais
anonimizadas ou fixtures reproduzíveis. A promoção registra versão, métricas,
motivo e caminho de rollback.

### Experience Ledger

O ledger armazena, por missão:

- estratégia e modelos usados;
- sequência de ferramentas;
- falhas, correções e intervenções humanas;
- tempo, custo e uso de contexto;
- critérios aprovados e reprovados;
- artefato final e feedback;
- lições candidatas e melhoria promovida.

Esse ledger é a matéria-prima do aprendizado. Ele permite descobrir tarefas
repetidas, ferramentas pouco confiáveis, prompts que custam demais e skills que
realmente aumentam a taxa de conclusão.

## Encaixe na base atual

A Nara já possui grande parte dos mecanismos necessários:

| Capacidade atual | Papel na arquitetura-alvo |
| --- | --- |
| `nara_cli/goals.py` | objetivo persistente e contratos de conclusão |
| `agent/context_engine.py` | seleção e compactação de contexto |
| `agent/memory_provider.py` | interface para memória externa e checkpoints |
| `agent/conversation_compression_checkpoint.py` | handoff durável antes da compactação |
| `tools/delegate_tool*.py` | criação e acompanhamento de subagentes |
| `tools/checkpoint_manager*.py` | checkpoints de execução e recuperação |
| `cron/` e `nara_cli/heartbeat.py` | trabalho agendado e reentrada de sessão |
| `tools/browser_*` | operação de páginas e perfis de navegador |
| `tools/computer_use/` | captura, acessibilidade e ações no desktop |
| `tools/voice_mode.py`, `tools/voice_live.py` | conversa falada |
| `tools/wake_word*.py` | ativação local por voz |
| `agent/learn_prompt.py` e skills | aprendizado de procedimentos |

Os componentes novos devem chegar como módulos ou plugins sobre essas
interfaces, sem criar um segundo loop de agente:

- **Mission Store:** eventos e projeções duráveis da missão;
- **Mission Supervisor:** fila, dependências, retomada e cancelamento;
- **Artifact Store:** saídas grandes e evidências endereçadas por conteúdo;
- **Receipt Store:** registro uniforme de ações e verificações;
- **Experience Ledger:** histórico de desempenho e lições;
- **Evolution Lab:** variantes, datasets, avaliações, promoção e rollback;
- **Capability Registry:** inventário vivo de ferramentas, máquinas e serviços;
- **Operations Console:** visão de missões, agentes, custos, bloqueios e provas.

## Primeira entrega: continuidade comprovada

Antes de memória avançada, voz contínua ou autoedição, a Nara deve provar
que consegue terminar uma missão longa após interrupções.

### Escopo

1. Criar o contrato `Mission`, seu event log e a projeção de estado.
2. Adaptar uma meta persistente para gerar uma missão com tarefas.
3. Registrar cada tool call como recibo com artefatos e status de verificação.
4. Criar checkpoint após toda transição relevante.
5. Retomar automaticamente missões `running` ou `verifying` após reinício.
6. Tornar ações com efeito externo idempotentes ou precedidas por leitura.
7. Exibir missão, próximo passo, agentes, bloqueios e evidências no Desktop.

### Teste de aceitação

Uma fixture cria uma missão de várias etapas que escreve arquivos, inicia um
subagente e produz um relatório. O processo é encerrado em pontos definidos.
Após reiniciar, a Nara deve:

- reconstruir o mesmo estado a partir dos eventos;
- não repetir etapas já confirmadas;
- retomar processos ou marcar corretamente os que foram perdidos;
- concluir as etapas restantes;
- verificar o relatório;
- fornecer a trilha completa de evidências.

## Roadmap

### Fase 1 — Mission Control

Estado durável, tarefas, eventos, recibos, artefatos, retomada e verificador.

### Fase 2 — Memória recuperável

Arquivo episódico integral, memória temporal por projeto, busca híbrida,
proveniência e expansão de contexto antigo. Avaliar adaptadores OpenViking,
LCM, Honcho e o provider existente em tarefas próprias.

### Fase 3 — Equipe dinâmica

Templates de agentes, criação sob demanda, contexto isolado, dependências,
cancelamento, orçamento e síntese estruturada pela líder.

### Fase 4 — Controle integral do computador

Roteamento API/terminal/browser/desktop, inventário de capacidades, verificação
pós-ação e execução em máquinas remotas ou ambientes isolados.

### Fase 5 — Nara por voz

Wake word validada, conversa full-duplex em português, interrupção, correções,
acompanhamento de missões e retorno falado conciso enquanto os workers atuam.

### Fase 6 — Evolution Lab

Ledger de experiência, curadoria automática, criação e melhoria de skills,
datasets de regressão, variantes A/B, promoção e rollback.

### Fase 7 — Aprendizado de modelo

Somente depois de acumular dados avaliados: otimização de prompts, roteamento,
fine-tuning ou RL para capacidades específicas, mantendo o modelo generalista
como planejador quando for a melhor opção.

## Métricas

- taxa de missões concluídas e verificadas;
- taxa de retomada correta após falha;
- ações externas repetidas indevidamente;
- intervenções humanas por missão;
- recuperação correta de decisões e preferências;
- regressões introduzidas por skills ou prompts promovidos;
- tempo, custo e tokens por resultado;
- percentual de conclusões sustentadas por evidência;
- reutilização e impacto das skills aprendidas.

## Decisão inicial

A primeira implementação será o Mission Control e seu teste de retomada. Essa
camada transforma as capacidades já existentes em uma agente contínua. Memória
avançada, voz, novas equipes e autoevolução serão conectadas ao mesmo ciclo de
missão, recibos, verificação e experiência.

## Referências técnicas avaliadas

- [OpenAI Agents](https://developers.openai.com/api/docs/guides/agents) e
  [memória/compactação](https://developers.openai.com/cookbook/examples/agents_sdk/building_reliable_agents_memory_compaction);
- [Anthropic: agentes de longa duração](https://www.anthropic.com/research/effective-harnesses-for-long-running-agents)
  e [engenharia de contexto](https://www.anthropic.com/research/effective-context-engineering-for-ai-agents);
- [Letta Code](https://github.com/letta-ai/letta-code),
  [OpenViking](https://github.com/volcengine/OpenViking) e
  [LCM](https://github.com/martian-engineering/lossless-claw);
- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
  e [Microsoft Agent Framework](https://github.com/microsoft/agent-framework);
- [Cua](https://github.com/trycua/cua) e
  [Browser Use](https://github.com/browser-use/browser-use);
- [LiveKit Agents](https://github.com/livekit/agents),
  [Pipecat](https://github.com/pipecat-ai/pipecat) e
  [openWakeWord](https://github.com/dscripka/openWakeWord);
- [Langfuse](https://github.com/langfuse/langfuse) e
  [Promptfoo](https://github.com/promptfoo/promptfoo).
