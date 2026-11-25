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

## Distribuição e limites do snapshot inicial

Os arquivos desse snapshot `d61f0b1` foram substituídos nos mesmos caminhos pelo build atual
`3c02ec2`; os hashes antigos abaixo são preservados apenas como histórico.

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
- A [PR #6](https://github.com/engsathiago/nara-agent/pull/6) foi integrada no commit `7f98a734daf356f05ec69f8a5783b9d3c8ffb15e`. Ela troca os links operacionais do domínio legado pelo endereço próprio planejado. Enquanto Pages não está ativo, os comandos de instalação usam os scripts em `raw.githubusercontent.com/engsathiago/nara-agent/main/scripts/`, ambos observados com HTTP 200. O seletor de skills do Desktop recorre à busca local quando a página externa não responde.
- O serviço legado de criação gerenciada de bot Telegram não resolve DNS. Sem `TELEGRAM_ONBOARDING_URL` configurada, CLI e dashboard informam que se deve usar BotFather manualmente; não tentam acessar esse serviço.
- Na preparação da PR #6 passaram 312 testes Python dirigidos de catálogo/OAuth/plugin guard/modelo, 11 de Telegram, 45 testes do Desktop, typecheck do Desktop e do site, `scripts/check --staged` (16 checks), `docs-check-links` e o build local em inglês do site. O [CI da PR](https://github.com/engsathiago/nara-agent/actions/runs/45656860540) e o [CI do merge](https://github.com/engsathiago/nara-agent/actions/runs/45657153748) passaram. O build local avisou sobre dois anchors herdados sem destino. A suíte integral e a publicação real no Pages seguem pendentes.
- Uma suíte ampliada do Desktop reproduziu no macOS uma falha preexistente na identificação de processo SSH quando o caminho tinha espaços. A leitura de `ps` foi substituída nesse host pela lista de argumentos via `KERN_PROCARGS2`; a repetição passou com 133 testes e 1 ignorado. O teste específico com caminho contendo espaços também passou isoladamente.
- A [PR #7](https://github.com/engsathiago/nara-agent/pull/7), limitada ao guia `plugin-catalog/README.md` pelo contrato do gate de admissão, foi integrada no commit `81ab80ac377344e344d0353c422296f7e85ed134`. Os jobs estrutural, pin de origem e CI de identidade passaram. O job de pin não validou um novo plugin, pois nenhuma entrada YAML mudou.
- O [run 45657154007](https://github.com/engsathiago/nara-agent/actions/runs/45657154007) de Pages após a PR #6 continuou falhando na etapa `configure-pages`, antes do build/deploy. É necessário habilitar Pages com origem `GitHub Actions` em `engsathiago/nara-agent` → Settings → Pages e repetir o workflow. O site, a busca e os catálogos públicos só poderão ser considerados publicados após uma verificação HTTP dos endpoints.

## Atualização: catálogo público e identidade própria

- O GitHub Pages foi habilitado por API em 2026-11-25 com `build_type=workflow`; a resposta foi HTTP 201. A [PR #9](https://github.com/engsathiago/nara-agent/pull/9) ativou o índice de skills no repositório próprio e fez o site consumir apenas seu artefato validado. O [run 45660310390](https://github.com/engsathiago/nara-agent/actions/runs/45660310390) gerou 106.709 skills: 84.378 ClawHub, 20.000 skills.sh, 1.206 GitHub, 505 LobeHub, 479 Browse.sh e 141 oficiais. A resolução dos caminhos GitHub das entradas skills.sh é adiada até a instalação para respeitar a quota do token do repositório.
- O primeiro build do site com o índice passou, mas o deploy consultou a API antes de o artefato `github-pages` ficar visível. A [PR #10](https://github.com/engsathiago/nara-agent/pull/10) adicionou essa espera. O [run 45665630200](https://github.com/engsathiago/nara-agent/actions/runs/45665630200) passou por build, upload e deploy. `https://engsathiago.github.io/nara-agent/docs/`, `/docs/api/skills-index.json` e `/docs/api/plugin-catalog.json` responderam HTTP 200. O índice servido tinha 106.709 linhas e SHA-256 `ca7ae41aee5bf101d90e834179fb2b8f8172baf729aa250e0351217e04eaddde`, idêntico ao artefato do run. O catálogo público tinha 1.378 plugins; a prova CORS do Desktop retornou `ok` com `Origin: null`.
- A [PR #11](https://github.com/engsathiago/nara-agent/pull/11), integrada no commit `6a691f469f`, substituiu os identificadores ativos de Desktop, plugin, launchd, Linux e MSIX pelo namespace do projeto próprio. O teste de identidade falhou na base com `com.nousresearch.nara` e passou após a mudança. Passaram 191 testes Python dirigidos, mais 18 testes de bundle, 15 testes de identidade/canais do Desktop, 6 testes MSIX, typecheck do Desktop, `scripts/check --staged` (16 checks) e o CI da PR. A assinatura Windows/Store ainda requer certificado e identidade cadastrada pelo proprietário; `CN=Nara Agent` é a identidade local, não uma prova de publicação assinada.
- No `main` atual, `nara --version` apontou para `/Users/fate/Desktop/Nara` no commit `6a691f469f`; `scripts/check_product_identity.py` passou e o scorecard estrito de continuidade retornou `ready` sem bloqueios. A tentativa de repetir a suíte Python integral no snapshot publicado encontrou timeouts de arquivos sob carga e foi interrompida; portanto ela **não** conta como aprovação da suíte integral atual.

## Atualização: pacote macOS do commit publicado

- A [PR #13](https://github.com/engsathiago/nara-agent/pull/13) atualizou autor, publisher, copyright visível e mantenedor dos pacotes para a Nara, preservando as licenças e atribuições do código upstream. O CI da PR passou. O `main` limpo `3c02ec2a3765587701c8c89122e432ee534c40f8` foi empacotado com `bash scripts/build-bundle.sh`; o processo terminou com código zero e `build/install-stamp.json` registrou esse commit com `dirty: false`.
- Manifesto do código nesse commit: `/Users/fate/Desktop/Nara-release-manifest-3c02ec2a37.json`, SHA-256 `6a0d8a8e47a7fac89c6a61792469d2ba71020571d6b92bcbd80138f5be843797`, 304 arquivos, `content_set_sha256` `9a8a0afb2a7a0b5fd9bf8996cba4045bd193b66dddfe6c1c22051369c56999cc`.
- DMG local `apps/desktop/release/NaraBundled-0.0.0-mac-arm64.dmg`: SHA-256 `8848770acaad252793749ea7dff6bd0e21eda2b477d9f8899ba56a7cc2ccf670`; `hdiutil verify` confirmou checksum válido. ZIP local `apps/desktop/release/NaraBundled-0.0.0-mac-arm64.zip`: SHA-256 `7a6636dbdcfde21feeb4d32682882cef10b3fe8a8f3a9b3a70f03e8b5caafe52`; `zipinfo -t` confirmou 126.956 arquivos. Ambos contêm o `CFBundleIdentifier` `io.github.engsathiago.nara-bundled-3c02ec2`, lido diretamente de seus `Info.plist`.
- O aplicativo desempacotado `apps/desktop/release/mac-arm64/Nara Agent 3c02ec2.app` foi reassinado ad hoc após gerar DMG/ZIP e passou em `codesign --verify --deep --strict`; CDHash `6e09ad8cdc7e23a7701d59595566ae4a39bd6eb2`. Essa assinatura manual **não está dentro** dos arquivos DMG/ZIP. Nenhum deles foi notarizado ou assinado com Developer ID, e nenhum binário foi anexado a um GitHub Release.
