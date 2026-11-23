# BD de tiers, extensão: itens, builds por campeão e Stat Anvils — desenho para aprovação

Data: 23/11 · Base: BD de tiers do draft #106 · Só desenho, sem código · Dados verificados em `czgreat/aramhex-data` 16.22/16.23 `normal`

## 0. Verdade desconfortável primeiro

1. **Stat Anvils: zero dados reais, em qualquer fonte legal.** [Certo] A AramHex não tem Anvils (nem os vouchers 220008/220009 nas 197 IDs de itens). A arammayhem.com só tem pick rate de augments. A Riot API dá 403 no Mayhem. O catálogo do CommunityDragon tem 0 linhas `kBronze` (P0-01). **Decidido (Francisco, 23/11):** a tier list de Anvils é heurística, marcada "estimativa", nunca OP/S.
2. **A adaptação aos augments, aliados e inimigos também é quase toda heurística.** [Certo] O único dado medido de item × augment é o "Weapon of Fate" (augment 3081, 3 itens por campeão, números de 16.22). Item × composição inimiga ou aliada não existe em nenhuma fonte legal com volume. Só o histórico LCU do próprio jogador, com n pequeno, e a telemetria opt-in (D5, futura).
3. **O WR de um item é enviesado pela duração da partida.** [Provável] A AramHex conta os itens que o jogador tem no fim da partida. O 5.º e o 6.º item só aparecem em partidas longas, e uma equipa que está a ganhar acaba itens mais cedo. Por isso o ΔWR de um item mede "aparecer em jogos ganhos", não "comprar faz ganhar". Mitigação: a build de referência vem dos **três primeiros itens lendários, por ordem** (dado medido, `core_builds.json`); o ΔWR dos itens só ordena, com teto, e é validado em holdout.
4. **Os itens dependem do fix do GPT.** No PC dele há 0 itens finais elegíveis. Sem esse fix não há pool onde aplicar a tier list. Esta extensão **lê** o pool elegível e o `canonical_item_id` dele, sem tocar nesses ficheiros.

## 1. O que existe de dados reais (medido em 23/11)

| Necessidade | Fonte | Cobertura | Estado |
| --- | --- | --- | --- |
| Itens finais por campeão (WR) | AramHex `hero_items.json` (sem upgrades, recompensas de augments nem itens oferecidos) + denominador `equipment_recommendation_heroes.json` | 173 campeões; 108 itens finais; mediana de 29 itens com ≥ 1000 jogos por campeão (mínimo 12) | **Medido** [Certo] |
| Build de referência (ordem) | AramHex `core_builds.json`: até 3 conjuntos de 3 lendários por ordem, com jogos, vitórias e pick | 172 campeões; cobre ~17 % dos jogos de cada campeão (mediana); **reutilizado de 16.22** | **Medido**, só nos slots 1–3 [Certo] |
| Botas | AramHex `hero_item_holdings.json` (8 botas) | 173 campeões | **Medido** [Certo] |
| Slots 4–6, ordem | — | nenhuma | **Heurístico** (tier do item + motor atual) |
| Item × augment | AramHex `hero_augment_items.json` | só o augment 3081 (Weapon of Fate), números de 16.22 | Medido só nesse caso |
| Item × aliados/inimigos | — (LCU próprio: n pequeno; D5: futuro) | nenhuma com volume | **Heurístico** (`_enemy_reaction_bonus` atual) |
| Stat Anvils | nenhuma | nenhuma | **Heurístico** (Decidido) |
| Rácios das habilidades (para as Anvils) | CommunityDragon `characters/<c>/<c>.bin.json` (partes de cálculo por stat) | todos os campeões | [Provável]: não consegui abrir daqui (proxy), verificar na fase I0 |

**Para o GPT (elegibilidade de itens), dado útil:** [Provável] a AramHex regista os itens finais do Mayhem quase todos com a **ID base** (3118, 4645…), não com as variantes 22xxxx/32xxxx. Das 197 IDs, só 7 têm 6 dígitos, e são recompensas ou itens especiais (228002, 226668, 223069, 994403, 12xxxx). Isto aponta para as 152 `mode_variant` como suspeitas de bloquear as IDs que os jogadores compram de facto. Fonte: servidor CN (Tencent); confirmar no EUW.

## 2. Esquema (Proposta: acrescenta à BD existente, sem mudar o que está)

```
observation.scope += champ_item, champ_boots, champ_core, champ_aug_item
   champ_core: metric="core", value=NULL, items_json=["3118","4645","3089"] (ordem), wins, n
item_tier(run_id, champion_id, item_id, kind{final,boots}, score, score_p20, score_p80,
          rank, tie_group, tier, level{champion,role,global,heuristic}, confidence)
reference_build(run_id, champion_id, slot 1..6, item_id, source{core,tier,heuristic}, confidence)
champion_stat_demand(run_id, champion_id, stat, weight, source{abilities,builds})
```

Export para o overlay: tier, rank e nível por item e por campeão; a build de referência (IDs); os pesos de stats. **Nunca WR, jogos nem n** (o teste do F6 estende-se a estas tabelas).

## 3. Fórmulas (Proposta)

**Tier de item por campeão** (só itens finais elegíveis; botas numa lista à parte)
- `p_c` = WR do campeão no denominador de equipamento. ΔWR do item: Beta encolhido para `p_c`, `k = 300`; `Δ = logit(p_ci) − logit(p_c)`.
- Presença no núcleo `P_ci` = Σ, sobre os conjuntos de 3 do campeão que contêm o item, de pick × WR encolhido. Dá peso a "os jogadores que ganham constroem isto cedo".
- Encaixe `F_ci` = `score_item` atual (vetor de stats do campeão), percentil.
- `S = 10·(0,50·pct(Δ) + 0,30·pct(P) + 0,20·pct(F))`. WR a 50 %, como nas outras listas.
- Mínimo de 2 % dos jogos do campeão para entrar como medido. Abaixo disso, o item desce para o nível `role → global → heuristic`, com os mesmos tetos (OP/S/S/A).
- Rank, empates (P < 0,75) e percentis de tier: iguais aos dos augments.

**Build de referência (slots 1–6)**
- Slots 1–3: o conjunto do `core_builds` com maior WR encolhido entre os de pick ≥ 5 %, com a ordem medida. Se o campeão não tiver nenhum, os três itens de maior `S`.
- Slots 4–6: maior `S` entre os elegíveis, respeitando os grupos exclusivos e as receitas (`_fill_slots` atual).
- Botas: a de maior `S` na lista de botas.

**Otimização por cima (adaptação à partida)**
- `A_i = S_ci + C_aug + C_ini + C_ali`. Cada termo de contexto tem um limite. `C_aug` vem do `score_item` com os augments confirmados (medido só para o 3081 via `hero_augment_items`). `C_ini` e `C_ali` vêm do `_enemy_reaction_bonus` e do `AllyTeamProfile` atuais.
- Regras para o resultado ficar estável e explicável:
  1. A adaptação troca **no máximo 2 dos 6 slots**.
  2. Só troca se `A_novo − A_ref ≥ 1,0` (escala 0–10).
  3. O slot 1 da referência nunca é trocado.
  4. Cada troca mostra o motivo (ex.: "inimigos com cura → anti-cura").
- O overlay mostra "Referência" e "Adaptada a esta partida" lado a lado.

**Stat Anvils (heurístico, Decidido)**
- Procura de stats do campeão `D_c(s)`:
  - 50 % rácios das habilidades (CommunityDragon, soma dos coeficientes por stat, ponderada pela utilização típica: ultimate < básicas).
  - 50 % stats que as builds medidas do campeão acumulam (vetor de stats dos itens ponderado pelos `S` da tier list).
  - A segunda metade é a âncora em dados reais.
- Valor de uma opção de Anvil `o` (stat `s`, magnitude `v`): `V = D_c(s) · v/v_ref(s) · 1/(1 + tem(s)/cap(s)) · M_aug(s) · M_ctx(s)`.
  - `tem(s)`: o que o jogador já tem, pelo LCDA `championStats`.
  - `M_aug`: multiplicadores dos augments confirmados (ex.: um augment de escudos sobe "heal & shield power"; um de ataques básicos sobe AS).
  - `M_ctx`: inimigos (armadura/MR se o dano inimigo é físico/mágico; tenacidade se há muito CC) e aliados (falta de frontline → vida).
- Ordena apenas as opções visíveis. Tier visível no máximo A, sempre com a etiqueta "estimativa".

## 4. Reaproveitar o `anvil_priorities.py` do #103 e o modelo de 12 dimensões

- Reaproveita-se a estrutura: pesos por stat a partir do campeão, ajuste pelo inimigo, saturação, e só opções verificadas no ecrã. O `rank_anvil_stats` passa a receber `D_c` em vez do vetor curado.
- **O modelo de 12 dimensões não cobre os stats das Anvils.** [Certo] O `StatVector` tem ap, ad, attack_speed, hp, lethality, pen, crit, cdr, heal_power, hard_cc, soft_cc e shield. Faltam armadura, resistência mágica, velocidade de movimento, tenacidade, omnivamp/roubo de vida e mana, que são stats típicos das Anvils [Suposição: o catálogo real das Anvils não existe em nenhuma fonte, P0-01]. O `anvil_priorities` só modela 7 (P1-13). Hard/soft CC e escudo são mecânicas, não stats que se compram.
- Proposta: um vetor `AnvilStats` separado, com 13 stats: ad, ap, as, hp, armor, mr, ah, crit, ms, lethality, mpen, omnivamp, tenacity. Fica só para Anvils e itens, sem mexer no `StatVector` que o motor de augments usa, para não colidir com o fix do parser do GPT.

## 5. Onde a cobertura com dados reais é impossível (hoje)

1. **Anvils:** a escolha, o valor e a ordem não têm dado real. Validação offline impossível; só se confirma o funcionamento na partida de teste (diagnóstico por funcionalidade).
2. **Itens × inimigos/aliados:** sem fonte legal com volume. Fica heurístico até haver D5 com consentimento.
3. **Itens × augments:** só o Weapon of Fate é medido.
4. **Ordem dos slots 4–6:** não é medida.
5. **Viés da região CN e da duração da partida** nos WR dos itens: o lift face ao campeão e a validação em holdout reduzem-no, mas não o eliminam.

## 6. Fases (RED → GREEN; só depois do fix de elegibilidade do GPT para I2+)

| Fase | Entrega | Depende de |
| --- | --- | --- |
| I0 | Ler um bin do CommunityDragon e fixar o formato dos rácios; confirmar se o LCU regista as Anvils escolhidas | — |
| I1 | Importador AramHex: itens, botas, núcleos, Weapon of Fate → observações | — |
| I2 | Tier de itens por campeão, build de referência; interseção com o pool elegível | fix do GPT |
| I3 | `AnvilStats`, `D_c` (rácios + builds), score das opções de Anvil | catálogo/gatilho de Anvil do GPT para mostrar no jogo |
| I4 | Otimização por cima (máx. 2 trocas, motivos) no motor de build | I2 |
| I5 | Overlay: referência vs adaptada, tier dos itens, Anvils "estimativa"; diagnóstico `items.*`/`anvil.*` | I2–I4 |
| I6 | Holdout 16.22→16.23: τ dos ranks dos itens; WR do núcleo previsto vs observado | I2 |

Pedido de validação ao Francisco: pesos 50/30/20 dos itens, máximo de 2 trocas com limiar de 1,0, e o slot 1 fixo.
