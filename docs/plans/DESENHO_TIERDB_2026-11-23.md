# BD de tier lists (augments por campeão + campeões) — desenho para aprovação

Data: 2026-11-23 · Base: `feat/f3-post-full-build-anvil-priorities-20261123` @ e0772f44 (PR #103) · Branch proposta: `feat/tierdb-augment-champion-tiers`

## 0. Verdade desconfortável primeiro

1. **Com as fontes legais de hoje, os 50 % "não-WR" dos pesos ficam quase todos vazios.** A AramHex dá jogos/vitórias por campeão×augment [Provável: ainda não abri os ficheiros, é a fase F0]. Dano/min, KP, mortes/min e curva por duração exigem dados por partida: Riot API (queue 2400 provavelmente bloqueada) ou o teu histórico local (amostra minúscula). Pela regra de fallback decidida, o peso redistribui-se, e na v1 a tier list de augments é **≈100 % ΔWR com shrinkage** + contexto heurístico. O desenho suporta as outras métricas desde o dia 1, mas não as inventa.
2. **Decidido (Francisco, 23/11, contra a recomendação): a tier list empírica aparece no overlay já**, sem esperar pela Riot. Risco registado: a política proíbe exibir win rates de augments e um tier derivado deles pode ser lido como transformação; no pior caso, a Riot recusa ou revoga a chave/registo da app. Mitigação: nunca mostrar WR/n/lift, só tier/rank/nível; camada empírica atrás da flag `empirical_tiers_enabled` (ligada por omissão) que, desligada, volta ao nível 4 sem reiniciar.
   Confirmado em `audit/FONTES_DADOS_MAYHEM_2026-11-23.md`: a Riot API devolve 403 para Mayhem; métricas ricas só via histórico LCU (próprio) e telemetria opt-in (D5).
3. **A AramHex é servidor CN.** O meta CN pode divergir do EUW. O lift face à base do campeão (não o WR bruto) reduz esse viés, mas não o elimina. Fica marcado como "região: CN" na proveniência.

## 1. Decidido vs Proposta

| Tema | Estado |
| --- | --- |
| Tier list por campeão, todos os augments do patch, separada por raridade, ranking 1..N, empate se P < 0,75, tiers OP/S/A/B/C/D/E com limiares fixos por patch | Decidido |
| Pesos 50/15/12/8/8/7 (ΔWR ≥ 40–50 %, Decidido 23/11; resto proporcional aos pesos antigos 20/15/10/10/10), tudo em delta face à base do campeão, pick rate só como prior | Decidido |
| Fallback: métrica em falta → redistribui; hierarquia campeão→classe→global→curada; tetos OP/S/S/A | Decidido |
| Fontes: AramHex (app não comercial, com atribuição), arammayhem.com (CC BY, pick rate), histórico local; Riot API em paralelo | Decidido |
| Esquema da BD, pipeline, fórmulas exatas, limiares, ponderação da tier list de campeões, testes | **Proposta** (este documento) |

## 2. Esquema da BD (Proposta)

SQLite local, ficheiro separado `%LOCALAPPDATA%\ARAMOracle\data\tierdb.sqlite` (nunca no repo). Formato "longo": **cada valor tem fonte, snapshot e n**.

```
source(id, name, url, license, attribution, commercial_ok)
snapshot(id, source_id, patch, region, queue, window_start, window_end,
         fetched_at, sha256, row_count, metric_definitions_json)       -- idempotente por sha256
observation(snapshot_id, scope, champion_id NULL, role NULL, augment_id NULL,
            metric, value NULL, wins NULL, n NOT NULL, low_sample)
            -- scope ∈ {champion, champ_aug, role_aug, global_aug}
            -- metric ∈ {win, pick, dmg_min, heal_shield_min, cc_min, kp, deaths_min, duration_bin_*}
quarantine(snapshot_id, raw_name, reason)                              -- nomes não mapeados: nunca descartados em silêncio
tier_run(id, patch, created_at, code_sha, weights_json, thresholds_json, snapshot_ids_json, seed)
augment_tier(run_id, champion_id, rarity, augment_id, score, score_p20, score_p80,
             rank, tie_group, tier, level, confidence, n_eff, sources_json)
champion_tier(run_id, champion_id, score, components_json, rank, tie_group, tier, confidence, n)
```

`observation.n` é obrigatório: um valor sem n é rejeitado (teste).

## 3. Pipeline por patch (Proposta)

```
python -m backend.tierdb ingest --source aramhex|arammayhem|local --patch 26.23
python -m backend.tierdb build  --patch 26.23
python -m backend.tierdb export --patch 26.23   → tierlist_26.23.json (só tiers/rank/nível/confiança)
```

1. **Ingest:** descarregar → SHA-256 → validar o esquema → mapear nomes para IDs do catálogo CDragon do patch (falhas → `quarantine`) → gravar o snapshot. Repetir o mesmo SHA não duplica.
2. **Build:** calcular as duas tier lists (secções 4 e 5) → `tier_run`. Determinístico (semente fixa).
3. **Export:** JSON para o overlay **sem** `wins`, `n`, WR ou lift (teste). Flag `empirical_tiers_enabled=True` por omissão (Decidido 23/11); interruptor nas Definições; desligada → o overlay usa só o nível 4 (teste).
4. Gatilho: deteção de patch novo que já existe na app; sem dados do patch novo → mantém-se o anterior marcado "patch anterior".
5. Atribuição AramHex e arammayhem.com em `THIRD_PARTY_NOTICES.md` e no ecrã "Sobre". Se `app_mode=commercial`, as fontes NC são excluídas no ingest (teste).

## 4. Tier list de augments por campeão (Proposta das fórmulas)

Para o campeão `c`, augment `a`, raridade `r`; `p_c` = WR base do campeão no snapshot.

**ΔWR (50 %):** posterior Beta encolhido para a base do campeão, `k = 300` (recomendação AramHex; calibrar):
`p_ca ~ Beta(wins_ca + k·p_c, losses_ca + k·(1−p_c))`, `ΔWR = logit(p_ca) − logit(p_c)`.

**Outras métricas (combate 15 / KP-mortes 12 / duração 8 / contexto 8 / consistência 7):** `Δm = (média_ca − média_c)/dp_papel`, encolhido por `n/(n+k_m)`; combate comparado **dentro do papel**; mortes com sinal negativo; consistência só com ≥ 2 snapshots.

**Normalização:** cada componente → percentil empírico dentro de `raridade × patch`; `S = 10·Σ wᵢ'·zᵢ`, com `wᵢ' = wᵢ/Σ_disponíveis w`. Sem ΔWR nesse nível → desce de nível.

**Hierarquia (transição suave):** `S = w₁S₁ + (1−w₁)[w₂S₂ + (1−w₂)(w₃S₃ + (1−w₃)S₄)]`, `wⱼ = nⱼ/(nⱼ+kⱼ)`, `k₁=200, k₂=500, k₃=1000` [Suposição, calibrar]. Classe = papel do `_classify_role` existente. Nível mostrado = termo de maior peso. `S₄` = score heurístico atual (`rate_augment`); augment sem modelo → "sem dados", nunca 0.

**Rank, empates, tiers:**
- 1000 amostras do posterior (semente fixa) → rank 1..N pela mediana; vizinhos com `P(S_a > S_b) < 0,75` ficam no mesmo grupo ("#3–#7 ≈").
- Limiares congelados por patch sobre a distribuição de referência (pares de nível 1–2): **OP ≥ P97** (só nível 1 e `S_p20` também acima), **S ≥ P85, A ≥ P65, B ≥ P40, C ≥ P20, D ≥ P7, E < P7**. Tier final = `min(tier pelo score, teto do nível)`.
- Cobertura: para cada campeão e raridade, **todos** os augments do catálogo do patch aparecem uma vez (com "sem dados" se for o caso).

## 5. Tier list de campeões (Proposta nova)

| Componente | Peso | Métrica |
| --- | --- | --- |
| Win rate em Mayhem | 50 % | Limite inferior (P20) do WR do campeão, encolhido para a média do modo, `k = 500` |
| Força em combate | 19 % | Δ dano/min, cura+escudo/min, CC/min, KP, mortes/min **face à média do papel** |
| Aproveitamento de augments | 23 % | `L_c = Σ_r f_r · E[max de 3 ofertas de ΔWR_ca]` com ofertas sorteadas do catálogo da raridade; mede quanto as melhores escolhas sobem o campeão acima da sua própria base |
| Consistência | 8 % | Variância do rank entre snapshots/patches |

- **Porque não há dupla contagem óbvia:** o WR do campeão é o resultado médio com os augments que os jogadores escolheram; `L_c` é o ganho *potencial* da escolha ótima face a essa média. São quantidades diferentes; a validação confirma (secção 6).
- `f_r` = frequência de cada raridade nas ofertas do modo [Suposição: 1/3 cada até haver dado].
- Mesma regra: métrica em falta → redistribui. Na v1 só com AramHex: **WR 68 % / aproveitamento 32 %**. WR ≥ 50 % por decisão do Francisco (23/11); resto proporcional.
- Ranking 1..N, empates P < 0,75, tiers com os mesmos percentis; OP exige `n ≥ 500` jogos do campeão.
- Mostrado no champ select e numa vista de tier list; **nunca o WR**.

## 6. Validação (offline, obrigatória antes de ligar)

Treino no patch N, teste no N+1. Augments: Kendall τ entre o score previsto e o ΔWR observado no holdout; o composto tem de bater o "só ΔWR", senão os pesos sobrepostos descem (Decidido). Campeões: τ contra o WR do holdout; o composto não pode ficar abaixo do "só WR" por mais de 0,02. Relatório nos ficheiros do projeto, não no repo público.

## 7. Fases RED→GREEN (um commit de teste a falhar, depois o código)

| Fase | Entrega | Testes |
| --- | --- | --- |
| F0 | Ler 1 patch da AramHex e da arammayhem.com, fixar o formato e o SHA; documentar campos reais | — (relatório) |
| F1 | Esquema + proveniência | rejeita valor sem n/fonte; idempotência por SHA |
| F2 | Importadores AramHex, arammayhem, histórico local; quarentena | fixtures **sintéticas** marcadas como tal; NC excluído em modo comercial |
| F3 | Matemática dos augments | shrinkage (3/3 vitórias não chega ao topo; monótono em n); redistribuição; descida de nível; tetos |
| F4 | Rank, empates, tiers, cobertura | determinismo com semente; grupos P < 0,75; todos os augments por raridade |
| F5 | Tier list de campeões | `L_c` com casos conhecidos; redistribuição |
| F6 | Export + flag (ligada por omissão) + atribuição | JSON sem WR/n; flag desligada → só nível 4, sem reiniciar |
| F7 | Harness de validação holdout | só ΔWR vs composto |

PR draft sobre o #103, sem merge. Sem dados privados no repo.
