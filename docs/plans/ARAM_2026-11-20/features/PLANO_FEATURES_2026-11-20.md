# ARAM Oracle — Plano de features a partir dos repos de referência (2026-11-20)

Vem **depois** do plano de correção **v3** (`AUDITORIA_E_PLANO_v3_2026-11-20.md`: A1→A2→PG→B1…D2→(S1→C3)→N1). Não altera nenhuma fase A–D, PG, S1, P1, C3 nem N1. Onde uma feature toca no mesmo código, entra **depois da N1** e diz qual contrato v2 estende.

Blueprints para o GPT: `audit/blueprints_features/M-F_features.md` (+ `fixtures/`). Zip: `audit/ARAM_features_GPT_2026-11-20.zip`.

**Marcas:** [Certo] = medido, lido no código ou reproduzido · [Provável] = inferência forte · [Suposição] = a preencher lacuna. **Decidido** = disseste tu · **Proposta** = desenho meu por aprovar.

---

## 1. O que a pesquisa do GPT errou (ler primeiro)

1. **O `league-aram-builder` (fabs133) é o nosso próprio repo de origem** [Certo]. O ARAM Oracle é um fork dele: mesmo README, `OVERLAY_ASSESSMENT.md`, `PLAN-scaling-specs.md`, `build2/`, `overwolf/`, e o nosso `LICENSE` é o MIT "Copyright (c) 2025 fabs133". O código dele está parado em 2026-03-06, com 104 testes. O nosso tem 557 + 53. O "P2: avaliar league-aram-builder" do GPT não tem nada para aproveitar. **A obrigação que fica:** manter o aviso MIT do fabs133 em qualquer distribuição.
2. **"MIT" não é verdade para 3 dos 9** [Certo, li os repos]. O Paradox e o minseop8787 não têm licença: só podemos usar ideias. O zp96 Mayhem Overlay não tem ficheiro LICENSE. Só o `package.json` diz `"license": "MIT"`, sem texto nem copyright. Trato-o como só ideias [Provável que seja o uso juridicamente seguro].
3. **"Substituir botas não está implementado em lado nenhum"** é falso para nós: já temos `_boot_replacement` e `test_boot_replacement.py`, e a B3 fecha-o com o pool. O que falta é dizer **o que vender** com o inventário cheio (K3).
4. **Vários dos "reutilizáveis" violam a política da Riot no que mostram** [Certo]. A política diz: *"Products cannot display win rates for Augments or Arena Mode items… This applies to all websites, applications and overlays."*
   - Sygnano mostra a diferença de win rate por augment.
   - Hex Companion e zp96 mostram estatísticas de augments.
   - Counterbuild mostra tiers de augments do OP.GG e o WR das builds.

   Podemos usar o código de visão e de compras. **Nunca** os dados nem o que mostram.

## 2. Verificação repo a repo

| Repo | Licença (verificada) | Stack | Código existe? Testes? | Veredito |
|---|---|---|---|---|
| **Sygnano/aram-mayhem-tracker** | MIT ✓ (`LICENSE`, Cargo `license = "MIT"`) | Rust + Tauri + TS | Sim: `crates/mayhem-vision` (3.653 linhas, 8 ficheiros de teste, 23 screenshots de 9 resoluções). **Não consegui correr o `cargo test`: o ambiente bloqueou a execução de código de terceiros.** Medi o modelo diretamente (§3) | **Aproveitar:** motor OCR, separação de linhas, gate do botão de reroll e do "hide augments", re-OCR por carta. **Rejeitar:** win rates, auto-accept, estado do chat, item sets que apagam as páginas do jogador |
| **michadasis/Counterbuild** | MIT ✓ | Go | Sim: `engine/` com 3.327 linhas. **`go test ./engine ./meta` passou** [Certo, corri] | **Aproveitar** (portar para Python com o aviso MIT): plano de compra com o ouro atual, ganho real de penetração contra a armadura/MR estimada, contra urgente barato. **Rejeitar:** dados do OP.GG (endpoint MCP deles), tiers de augments |
| fabs133/league-aram-builder | MIT ✓ | Python | É a nossa base | Nada a fazer além de manter o aviso |
| Clarinet-koiyun/hex-companion | MIT ✓ | Electron/JS | Sim, 8 ficheiros de teste (não corri) | Pouco valor: OCR Tesseract multilingue e estatísticas de augments (proibidas) |
| ishtartec/query-lol-desktop | MIT ✓ | Tauri/React | Sim, 0 testes | Pouco valor: focado em SR e OP.GG, com runas e item sets automáticos. Só o padrão LCU gameflow-phase, que já temos em `collectors/lcu.py` |
| ItzStorDz/mayhem-advisor | All rights reserved ✓ | C# | Já analisado no plano v2 | Só ideias (já usadas em A6, C2, C3, E1) |
| zp96-cmd/mayhem-overlay | Sem LICENSE; `package.json` diz MIT | Electron | Sim, 2 testes | Só ideias: editor visual da posição dos painéis |
| Danielxpj/Paradox-LoL-Companion | **Nenhuma** | C# .NET 10 | Sim, ~60 ficheiros de teste (não corri) | Só ideias: inimigos ponderados por "fed", motivos legíveis, arquétipo por voto do ouro do inventário |
| minseop8787/lol-overlay | **Nenhuma** | Python + Electron | Sim, 2 testes | Só ideias: deteção da loja por template. **Captura o monitor inteiro**, o que a nossa regra proíbe |

## 3. Medição real: OCR do Sygnano contra os nossos crops

O motor é o modelo de reconhecimento **PaddleOCR PP-OCRv4** em ONNX, Apache-2.0. O Sygnano corre-o em Rust (`tract`). Eu corri o **mesmo ficheiro** em Python (`onnxruntime` 1.29), com um script meu que reproduz o pré-processamento deles (altura 48, largura 448, normalização [-1, 1], CTC greedy). A comparação com o nosso catálogo usa o critério do A1: ≥ 90 e margem ≥ 8.

**Proveniência** [Certo]: o SHA-256 `48fc40f2…683b` é igual ao `ch_PP-OCRv4_rec_infer.onnx` do wheel PyPI `rapidocr-onnxruntime==1.4.4`. Vamos buscá-lo ao PyPI, não ao repo do Sygnano.

| Teste (26 crops: 21 títulos + 2 diálogos + 5 sem oferta) | Resultado |
|---|---|
| Crop inteiro, sem separar linhas | **11/26**: falha nos títulos de 342×96 (o modelo quer 1 linha) |
| **Com separação de linhas** (como o `title_line_crops` deles) | **26/26** [Certo]. Todos os nomes a 100, margem 29–52. Diálogos e mundo dão `None` |
| Reduzido a 0,75× / 0,5× / 0,4× (≈1080p, 720p, 576p) | 21/21, 21/21, 21/21 |
| Igual, mais JPEG q60 | 21/21, 21/21, **20/21**, com **0 nomes errados** (falha fechada) |
| Tempo | **~16 ms por crop** em CPU, ou seja < 50 ms para 3 cartas |

**Conclusão** [Certo nos dados que temos; Provável em Silver, que não tem crop]: lê tão bem como o Tesseract (21/21 no plano v2), com mais margem e mais robustez à escala. **Não precisa de instalação**: o modelo tem 10,9 MB e vai dentro da app. Isto resolve o maior obstáculo de distribuição melhor do que o E2 (`Windows.Media.Ocr` exige pacote de idioma).

**Decidido (Francisco, 20/11, condicionado):** a V1 substitui o E2 do backlog, desde que seja melhor e sem problema de política.
- *Melhor* [Certo nos crops; Provável em Silver]: 26/26 contra 21/21 do Tesseract; o E2 nunca foi medido. A promoção a motor por omissão só acontece com os critérios da N2. Se falharem, o Tesseract continua a decidir e o E2 volta ao backlog.
- *Política*: a V1 e o E2 são o mesmo tópico P1 #1 (OCR do que já está visível, [Por validar], risco baixo). Trocar de motor não muda o risco. O modelo é Apache-2.0, com aviso no `THIRD_PARTY_NOTICES.md`.

## 4. Política da Riot aplicada às features [Certo, citações em developer.riotgames.com/docs/lol e /policies/general; matriz completa em `blueprints/P1_politica_riot.md` v3]

Cada fase está mapeada a um tópico da matriz P1 v3 (tabela no topo do M-F). Tudo o que é dinâmico fica em **modo pessoal** e bloqueia a distribuição até ao registo. A L1 usa a LCU e nasce **desligada**.

- *"Products cannot display win rates for Augments or Arena Mode items."* Nenhuma fase mostra WR de augments. O `allow_empirical` do `augment_rating.py` fica desligado.
- *"Products should not remove game decisions, but may highlight decisions that are important"* e *"Apps that dictate player decisions"* (não aprovado). Os textos dizem **"Sugerido"** e dão o motivo, nunca "Escolhe/Compra" como ordem. Não automatizamos nada.
- *"Products may not provide any game-session-specific information that would be previously unknown to the player."* Só usamos o que o jogador vê: as cartas, o Tab (itens e KDA dos inimigos) e a loja. A armadura/MR **estimada** dos inimigos (K2) deriva de dados visíveis (nível + itens + base pública). [Provável que seja aceitável; vai no P1.]
- *"All products must be registered in, and audited by Riot Games through the Developer Portal"*, mesmo sem API oficial. A L1 (LCU) e a I1 (distribuição) ficam atrás do P1 e do registo.

## 5. As fases (todas depois da N1)

| # | Fase | Fonte da ideia/código | Precisa de jogo? | Depende de |
|---|---|---|---|---|
| 1 | **V1** Motor OCR PP-OCRv4 + separação de linhas, em modo comparação com o Tesseract | Sygnano (ideia + modelo Apache-2.0) | Não | N1 |
| 2 | **K1** "Comprar agora": a melhor peça com o ouro atual | Counterbuild `planBuy` (MIT, portado) | Não | B3 |
| 3 | **K2** Inimigos ponderados por "fed", resistências estimadas, ganho real de penetração | Counterbuild `penGain` (MIT) + ideia do Paradox | Não | B5 |
| 4 | **K3** Contra urgente barato + o que vender com o inventário cheio | Counterbuild `urgentCounter` (MIT) | Não | K1, K2 |
| 5 | **X1** Motivos curtos e verificáveis em cada sugestão | Paradox / Counterbuild (ideia) | Não | K3 |
| 6 | **X2** Estabilidade: a sugestão só muda com um evento relevante | Nossa | Não | X1 |
| 7 | **V2** Recolha local de frames de referência (ferramenta dev, nunca commitada) | Nossa | **Sim, jogos normais** | V1 |
| 8 | **V3** Presença da oferta pelo botão de reroll e pelo "hide augments" + re-OCR só da carta que mudou (sombra) | Sygnano (MIT, portado; templates nossos) | Não (usa a V2) | V2, C1 |
| 9 | **V4** Loja aberta por template, na janela do League (sombra) | minseop (só ideia) | Não (usa a V2) | V2 |
| 10 | **N2** Teste nativo 2: promoções das sombras (V1, V3, V4) | — | **Sim, um** | 1–9 |
| 11 | **H1** Sugestão junto a cada carta, ancorada à geometria | Sygnano (ideia) | Não | N2, D1 |
| 12 | **L1** Champion select pela LCU, só leitura: fit da equipa e troca do banco sugerida | Sygnano / Advisor (ideia) | Não (fixtures LCU) | P1, S1 |
| 13 | **I1** Instalador + atualização com assinatura verificada | Sygnano (ideia) | Não | P1 + registo na Riot |

**Alinhamento com o v3:** só augments confirmados/reconciliados (C2 v3) alimentam K/X; sem `availability="verified_two_source"` (B1 v3) não há sugestões de compra; a troca de botas por item final é da B3 v3, a K3 nunca a duplica; frames só via `WgcFrameSource` (A3 v3); o H1 destaca as 3 cartas com motivo e trade-off (P1 2b).

**Proposta de ordem**, pela tua preferência "funcionalidade primeiro": V1 → K1 → K2 → K3 → X1 → X2 → V2 → V3 → V4 → N2 → H1 → L1 → I1. As 6 primeiras são offline e não precisam de jogos. O design (posição e aspeto do H1) fica para o fim, de propósito.

**Fora do plano, com o motivo:**
- WR, tiers ou estatísticas de augments, incluindo o teu histórico pessoal: proibido pela política.
- Auto-accept, estado do chat, aplicar runas: automatização fora do âmbito.
- Item sets que apagam páginas: o E1 v2 já cobre isto sem apagar.
- Dados do OP.GG, AramHex ou aramkit: termos de terceiros, e o AramHex é CC BY-NC.
- Gravação de jogos (QueryLoL).
- Editor de layout por arrastar (zp96): é design, por isso fica para depois do H1.

## 6. Mudanças ao plano v2 (só backlog, nenhuma fase A–N1 muda)

| Item v2 | Proposta |
|---|---|
| E2 `Windows.Media.Ocr` (backlog v3) | **Substituído pela V1** (Decidido 20/11, condicionado à N2; ver §3). |
| F-08 ofertas de 4 cartas | Fica no backlog. A V3 dá-lhe a base: os botões de reroll dizem quantas cartas existem. |
| E1 item set, B6 itens exigidos por augments | Sem mudança. |

## 7. Riscos concretos

1. **A V1 depende de uma separação de linhas correta.** Sem ela, cai para 11/26 [Certo]. A separação está na blueprint, com fixtures e testes próprios.
2. **Silver sem crops** [Por validar]. A V1 corre em comparação com o Tesseract até à N2. O Tesseract continua a decidir.
3. **Os templates de reroll, "hide augments" e loja são imagem do jogo.** Recortamo-los das tuas capturas (V2), não do repo do Sygnano. A geometria deles coincide com a tua captura de 18/11 (reroll ≈ 0,69 × H e "hide augments" ≈ 0,76 × H do cliente) [Provável, medido à mão numa captura].
4. **O K2 muda as entradas do B5** (contagens passam a ser ponderadas). As constantes do B5 não mudam. Se a N1 mostrar que o B5 sozinho chega, o K2 fica só com a penetração.