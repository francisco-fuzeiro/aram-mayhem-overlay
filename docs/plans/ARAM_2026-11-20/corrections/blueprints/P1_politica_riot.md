# P1 · Política da Riot: mapa por funcionalidade (v3, 2026-11-20)

**Fontes oficiais lidas hoje:**
- `developer.riotgames.com/docs/lol` (Game Policy, Developer API Policy, Live Client Data);
- `developer.riotgames.com/policies/general` (atualizada a 2025-05-29);
- `developer.riotgames.com/policies/game-specific` (2026-08-21);
- `developer.riotgames.com/league-client-apis.html`;
- `riotgames.com/en/DevRel/vanguard-faq`;
- `support.riotgames.com/…/third-party-applications`.

Citações literais também em `audit/blueprints_features/fixtures/riot_policy_quotes_2026-11-20.md`.

**O que NÃO serve de prova:** o OP.GG ou o Mayhem Advisor existirem não prova autorização. Não declaramos conformidade sem texto da Riot ou sem resposta ao registo.

## 1. Regras relevantes (fragmentos literais, < 15 palavras cada)

- "Products cannot display win rates for Augments or Arena Mode items." Vale para "all websites, applications and overlays".
- "Products may not provide any game-session-specific information that would be previously unknown to the player."
- "Apps that dictate player decisions" está na lista de casos não aprovados.
- "Products should not remove game decisions, but may highlight decisions that are important".
- "Products must not use or incorporate information not present in the game client…"
- Lista de aprovados (chaves pessoais): "Game overlays that provide static data that is available prior to the game."
- "All products must be registered in, and audited by Riot Games through the Developer Portal". Também: "If your product serves players, you must register it with us".
- A LCU "is not officially supported for use with third party applications" (paráfrase da página LCU).
- Vanguard FAQ: as apps que usam a LCU e as APIs em jogo "are still expected to work". E não há allow list.
- Partidas custom: "Products may not publicly display a player's match history from the custom match queue" sem opt-in.

**Não mencionados em nenhuma página:** OCR ou captura de ecrã, monitorização de rato e teclado, ARAM Mayhem pelo nome, adaptação a itens inimigos.

## 2. Matriz

| # | Funcionalidade | O que a política diz | Classificação | Comportamento no plano |
|---|---|---|---|---|
| 1 | OCR dos títulos das cartas já visíveis no ecrã | Não abordado. A informação está no cliente e é conhecida do jogador | **[Por validar]**, risco baixo [Provável] | Ligado. Só lê píxeis da janela do League (A3) |
| 2a | Mostrar win rates de augments ou itens Arena | **Proibido** [Certo] | Proibido | Nunca. Já é assim (`composite_score.py`). Teste novo: nenhum payload tem chaves `win_rate`/`wins`/`wr` para augments |
| 2b | Destacar augments com pontuação própria | "dictate" não aprovado, "highlight" permitido | **[Por validar]** | Ligado só como **destaque**: as 3 cartas têm sempre razões e trade-offs visíveis, sem "PICK THIS" nem seleção automática. Um texto do tipo "you must pick" está proibido no frontend |
| 2c | Build dinâmica de itens em jogo | Aprovados: overlays de dados **estáticos pré-jogo**. Dinâmico não listado | **[Por validar]** | Ligado em **modo pessoal**. Bloqueia a distribuição até ao registo e à auditoria |
| 3 | Adaptar a build a itens inimigos visíveis | Não abordado. Os itens são visíveis no Tab e o LCDA expõe-nos | **[Por validar]**, risco baixo [Provável] | Ligado em modo pessoal, como 2c. Nunca usa informação escondida (só o que o LCDA devolve, que já é o que o Tab mostra) |
| 4a | Hotkeys locais do próprio overlay (Alt+O/H/S/B/1/2/3) | Não abordado. O proibido é "taking actions on your behalf" | **[Por validar]**, risco baixo | Ligado. Só lê as combinações listadas e nunca envia input ao League |
| 4b | Ler a posição dos cliques do rato (pista de escolha) | Não abordado | **[Por validar]**, risco médio | **Desligado** (`PICK_CLICK_HINTS_ENABLED=False`). Alternativa: confirmação por Alt+1/2/3 |
| 5 | LCU: histórico local para reconciliar augments (S1/C3) | LCU não suportada oficialmente. O uso exige registo | **[Por validar]** | **Desligado** (`lcu_history_enabled=False`). A S1 só corre com o teu sim explícito, só leitura e só os teus dados. Os outros 9 jogadores são descartados antes de gravar. Nada é publicado |

**Modo pessoal vs. distribuição:**
- **Modo pessoal:** só o Francisco, no PC dele. As funcionalidades **[Por validar]** de risco baixo ficam ligadas. As de risco médio e a LCU ficam desligadas até decisão dele.
- **Distribuição:** qualquer cópia para outra pessoa. Só depois de:
  - **(a)** registo no Developer Portal com a lista desta matriz;
  - **(b)** estado "Approved" ou "Acknowledged";
  - **(c)** o texto "isn't endorsed by Riot Games…" visível;
  - **(d)** o aviso MIT do projeto de origem (`fabs133/league-aram-builder`) mantido.

## 3. Critérios de aceitação (testes)

- `tests/test_policy_p1.py`:
  - nenhum payload WS ou HTTP contém chaves `win_rate`, `winrate`, `wins`, `wr` ligadas a augments;
  - o frontend não contém as strings `Pick this`/`You must`;
  - `PICK_CLICK_HINTS_ENABLED is False`;
  - `lcu_history_enabled` vale False por defeito;
  - o `window.py` não lê `VK_LBUTTON` enquanto a flag estiver desligada.
- O README mantém o aviso "isn't endorsed by Riot Games" e o aviso MIT de origem.