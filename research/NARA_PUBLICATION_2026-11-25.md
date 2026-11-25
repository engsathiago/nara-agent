# Nara — publicação pública e validação local

Data: 2026-11-25 (America/Sao_Paulo)

## Repositório

- Código público: https://github.com/engsathiago/nara-agent; branch padrão `main`.
- Commit de código empacotado: `d61f0b15c0d6795267a5ba88a4b19c06607e08bb`.
- `LICENSE` MIT e `UPSTREAM_PROVENANCE.md` preservam licença e atribuição da base.
- A raiz do histórico publicado é nova: o histórico local anterior continha um objeto Git ausente. A branch `codex/nara-identity` conserva a referência histórica local.
- `scripts/install.sh --stage repository` clonou o repositório público em diretório temporário limpo e conferiu `origin` e `HEAD`.

## Gates observados

- CI próprio do GitHub no commit acima: [run 45638457697](https://github.com/engsathiago/nara-agent/actions/runs/45638457697), 29 arquivos, 126 testes aprovados, 0 falhas, 24 ignorados no Linux.
- Última suíte integral de código de produção: commit `a72116f032e40719336711e8ff10723461cbb338`, 7.466 arquivos, 74.220 testes aprovados, 0 falhas finais e 2.097 ignorados. A suíte integral não foi repetida com sucesso no snapshot publicado; consulte `research/NARA_COMPLETION_AUDIT_2026-11-23.md` para a distinção entre gates.
- `nara --version` no checkout publicado: `git.d61f0b1`, Python 3.14.9; gateway supervisionado pelo launchd, definição compatível com este checkout.
- Manifesto limpo do commit empacotado: `/Users/fate/Desktop/Nara-release-manifest-d61f0b15c0.json`, SHA-256 `e3a86816814f6dd5b172e92694e54d5ba7a82b904288dc098f8f011a58bad39d`, SHA-256 do conjunto de conteúdo `67c1a3c568151d362e6c3ae41bd292a04c63c9685cdcdb4db35bc73e30068c43`.

## Distribuição e limites

- O instalador de fonte segue `main` por padrão. Não há ainda tag de release estável neste repositório.
- O build macOS arm64 terminou com código zero e checkout limpo. O `build/install-stamp.json` fixa o commit acima e `dirty: false`.
- DMG local: `apps/desktop/release/NaraBundled-0.0.0-mac-arm64.dmg`, SHA-256 `863b1b194b633b3c9481666adce79b2d6b2f032a8c3c5eed3a2d518cdd263e04`; `hdiutil verify` retornou checksum válido.
- ZIP local: `apps/desktop/release/NaraBundled-0.0.0-mac-arm64.zip`, SHA-256 `cf68079ebfcd65c0a9585a331a8bb44bca29e7ce7779c70af62b7874b9399a83`; `zipinfo -t` confirmou 126.967 arquivos.
- Aplicativo local desempacotado: `apps/desktop/release/mac-arm64/Nara Agent d61f0b1.app`; assinatura ad hoc aplicada após gerar os arquivos ZIP/DMG, verificada por `codesign --verify --deep --strict`, CDHash `cf0dbcd059fb3e7dda0a81d8a8fed5396aaaf92c`. Portanto, os arquivos ZIP/DMG não contêm esta assinatura manual.
- O identificador macOS ainda é `com.nousresearch.nara-bundled-d61f0b1`; deverá ser substituído por um identificador próprio antes de uma distribuição oficial assinada.
- O domínio `nara-agent.nousresearch.com` e o host `nara-assets.nousresearch.com` não resolviam DNS nesta validação. Alguns links de documentação, catálogos, instalação remota e feeds ainda apontam para esses hosts. O repositório GitHub e o instalador por checkout foram validados separadamente; um site/feed oficial da Nara ainda precisa de hospedagem própria.
- Os workflows herdados que dependem de runners ou credenciais do upstream estão desativados; o CI portátil próprio acima é o gate publicado. Os PRs automáticos de Dependabot não foram incorporados.
- O pacote macOS não foi notarizado nem assinado com Developer ID. Nenhum binário foi anexado a GitHub Release.

## Gates externos pendentes

VPS/SSH e failover remoto; hardware e amostras PT-BR reservadas para `Ei, Nara`; contas/provedores/modelos escolhidos; clientes externos autenticados do Memory Gateway; benchmark variado e prolongado de competência/evolução; feed futuro e período de paper trading; credenciais Apple para assinatura e notarização. O módulo live de trading não foi promovido.

A ordem combinada é código local, documentação, GitHub público e depois instalação e validação na VPS. Este documento registra a etapa GitHub sem converter os gates externos em aprovados.

## Atualização: site e URLs próprias

- O `main` público chegou ao commit `caf74b0f063844aae07360c8f2208e80935ac204` com configuração Docusaurus para `engsathiago.github.io/nara-agent/docs`, busca local e workflow `Nara Pages`. O CI de identidade no [run 45651788466](https://github.com/engsathiago/nara-agent/actions/runs/45651788466) passou.
- O [run 45651788819](https://github.com/engsathiago/nara-agent/actions/runs/45651788819) de Pages falhou em `actions/configure-pages`: a API GET do site respondeu 404, pois Pages ainda não está habilitado. As tentativas de criar o site pela API REST responderam HTTP 500 sem corpo. **O site público e seus catálogos ainda não estão comprovadamente online.**
- A branch `codex/nara-owned-urls` troca os links operacionais do domínio legado pelo endereço próprio planejado. Enquanto Pages não está ativo, os comandos de instalação passam a usar os scripts em `raw.githubusercontent.com/engsathiago/nara-agent/main/scripts/`, ambos observados com HTTP 200. O seletor de skills do Desktop recorre à busca local quando a página externa não responde.
- O serviço legado de criação gerenciada de bot Telegram não resolve DNS. Sem `TELEGRAM_ONBOARDING_URL` configurada, CLI e dashboard informam que se deve usar BotFather manualmente; não tentam acessar esse serviço.
- Nesta branch passaram 312 testes Python dirigidos de catálogo/OAuth/plugin guard/modelo, 11 de Telegram, 45 testes do Desktop, typecheck do Desktop e do site, `scripts/check --staged` (16 checks), `docs-check-links` e o build local em inglês do site. O build avisou sobre dois anchors herdados sem destino. A suíte integral e a publicação real no Pages seguem pendentes.
- Uma suíte ampliada do Desktop reproduziu no macOS uma falha preexistente na identificação de processo SSH quando o caminho tinha espaços. A leitura de `ps` foi substituída nesse host pela lista de argumentos via `KERN_PROCARGS2`; a repetição passou com 133 testes e 1 ignorado. O teste específico com caminho contendo espaços também passou isoladamente.
