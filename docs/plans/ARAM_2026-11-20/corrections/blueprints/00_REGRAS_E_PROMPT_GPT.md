# 00 · Regras globais + prompt de arranque para o GPT (v3, 2026-11-20)

Lê isto **antes** de qualquer blueprint (`M-A_reconhecimento.md`, `M-B_build.md`, `M-C_escolhas.md`, `M-D_overlay.md`).
A fonte é `AUDITORIA_E_PLANO_v3_2026-11-20.md`. A v1 e a v2 ficam só como histórico. A política está em `P1_politica_riot.md`.

---

## 1. Prompt para colar no GPT (copiar tal e qual)

```
Vais implementar correções no repo francisco-fuzeiro/aram-mayhem-overlay seguindo blueprints fechadas (v3).
Regras não negociáveis:
1. Base: o 1.º ramo sai de origin/fix/p0-ocr-prerequisite-recovery (HEAD e4abf24 ou mais recente).
   Uma fase = um ramo = um PR draft, empilhado sobre o PR da fase anterior, por esta ordem:
   A1→A2→PG→B1→B2→B3→B4→B5→A3→A4→A5→A6→C1→C2→D1→D2→C3 (C3 só depois da S1, do P1 tópico 5 e do sim do Francisco).
   Nome do ramo: fix/<fase-minúsculas>-<slug>, ex. fix/a1-mayhem-catalog-dedup.
2. Implementa EXATAMENTE os nomes, constantes, assinaturas e valores da blueprint. Se achares que um valor está errado,
   NÃO o alteres: escreve "DESVIO PROPOSTO" na descrição do PR, com a evidência, e implementa o valor da blueprint.
3. Primeiro o teste vermelho (commit "test(<fase>): ... (RED)"), depois o código (commit "fix(<fase>): ...").
   Corre `python -m pytest -q` e `node --test tests/js/*.cjs` e cola o resumo no PR. O CI tem de estar verde no HEAD final do ramo.
4. Proibido:
   - commits só de docs/ledger/TODO/PROJECT_STATE/DEVELOPMENT_LOG;
   - repetir o mesmo commit;
   - criar "gates" novos desativados (exceção única: o modo sombra do C1, que é especificado);
   - mexer em ficheiros fora da lista "Ficheiros" da fase;
   - baixar MATCH_THRESHOLD (90) ou MIN_MARGIN (8);
   - capturar píxeis que não sejam da janela do League;
   - enviar teclas, cliques ou compras ao League;
   - escolher augments automaticamente, ou deixar uma escolha não confirmada alterar a build;
   - mostrar win rates de augments (proibido pela Riot);
   - ligar PICK_CLICK_HINTS_ENABLED ou lcu_history_enabled;
   - commitar imagens que não estejam no MANIFEST.md das fixtures;
   - usar pytest.skip/skipif para esconder dependências em CI.
5. Não pedes ao Francisco para jogar até ao fim da D2. Não fazes merge para main.
6. No fim de cada fase responde só: ramo, SHA, testes (n passed), ficheiros tocados, desvios propostos (se houver).
```

**Como entregar ao GPT:**
1. Anexa `audit/ARAM_blueprints_GPT_2026-11-20_v3.zip`.
2. Cola o prompt acima.
3. Diz "Implementa a fase A1 de M-A_reconhecimento.md". A fase PG está definida em `P1_politica_riot.md` (secção 3).
4. Só passas à fase seguinte com a resposta no formato da regra 6 e o CI verde.

## 2. Estado de partida verificado (2026-11-20)

- O código que correu no jogo falhado é `a796e7f`. Suite: **557 Python + 53 JS verdes** [Certo].
- Python ≥ 3.11. Dev: `pip install -e ".[dev]"`. Tesseract 5.x é obrigatório para A2 e C1 (imagens).
- CI: `.github/workflows/python-tests.yml` em `windows-latest`.

## 3. Fixtures reais

Estão em `audit/blueprints/fixtures/`. Lista completa, contagens e revisão: **`fixtures/MANIFEST.md`**. Resumo:

| Ficheiro | Conteúdo | Usado em |
|---|---|---|
| `cdragon_cherry_augments_2026-11-20.json` | 600 linhas `[id, augmentNameId, nameTRA, rarity, kiwiIcon]` | A1 |
| `expected_mayhem_catalog_2026-11-20.json` | **328** `{id: name}` | A1, A2 |
| `title_crops_1440p/` | **13** PNG: 11 com nome, 2 diálogos (`null`) | A2, C1 |
| `title_crops_prismatic_snips/` | **8** PNG Gold/Prismatic (2 em 2 linhas) | A2, C1 |
| `no_offer_2544x1353/` | **5** PNG do mundo do jogo, sem oferta | C1 |
| `ddragon_items_16.23.1_compact.json` | 480 itens (mapas 11/12), compacto | B1 |
| `ddragon_items_16.23.1_details.json` | 181 itens do pool: passivas, ativas, stats, from, into | B2–B5 |
| `cdragon_items_2026-11-20.json` | 863 itens CDragon (inStore, displayInItemSets, specialRecipe…) | B1 |
| `expected_item_pool_16.23.1.json` | classes dos 480, `pool_ids` (**181**), `final_ids` (**111**) | B1, B2 |
| `expected_item_properties_16.23.1.json` | propriedades verificadas e grupos exclusivos | B3, B5 |

## 4. Armadilhas transversais

1. **IDs são strings** em todo o backend (`"1041"`). Compara IDs numéricos só com `int(id)` explícito.
2. **Normalização de nomes:** usa sempre `slot_title_ocr._normalize`.
3. **Caches em disco:** qualquer mudança de formato ou de filtro exige bump do schema (`_AUGMENT_CACHE_SCHEMA`, `_ITEM_CACHE_SCHEMA`).
4. **Thread-safety:** `ScreenWatcher.check` corre em `to_thread` sob `self._lock`. Não acedas a `game_state` lá dentro. Passa os valores como argumentos.
5. **Coordenadas:** `LeagueWindow.rect` está em píxeis físicos (processo DPI-aware). As faixas de título são relativas ao cliente. O layout do overlay (D1) está em coordenadas lógicas do Qt.
6. **Testes existentes:** se uma fase muda um contrato, atualiza **só** os asserts listados na fase. Não apagues testes.
7. **Frontend:** `app.js` é JS puro. Os testes JS usam um DOM stub. Se usares uma API nova, acrescenta-a ao stub.
8. **Diagnósticos:** cada `stage`/`outcome`/evento novo tem de entrar no `SCHEMA` de `backend/diagnostic_events.py`. Senão é descartado em silêncio. Nunca registes nomes de jogador, caminhos de utilizador nem imagens.
9. **Dependências novas:** só `windows-capture==2.0.1` (A3), no extra `capture` (puxa `numpy` e `opencv-python`). Só o `WgcFrameSource` a importa, e de forma preguiçosa. Sem ela, a captura dá `backend_unavailable`, nunca uma exceção.
10. **Tesseract no CI:** `ARAM_REQUIRE_TESSERACT=1` no workflow. Com essa variável, a ausência do Tesseract é **falha**, não skip.

## 5. Gates fora de código

- **N1 (único jogo):** checklist no fim de `M-D_overlay.md`. Só depois da D2 verde.
- **S1 (spike, sem jogos novos):** ver se o histórico local do cliente traz os augments dos jogos de 18–20/11. Só leitura e só depois do P1.
- **P1 (política):** antes de distribuir a qualquer pessoa além do Francisco, confirmar nas políticas de developer da Riot:
  - (a) overlays em jogo com recomendações de augments e itens;
  - (b) leitura de ecrã por OCR;
  - (c) uso do LCDA e, se a S1 avançar, da LCU.

  Até lá, uso pessoal apenas. O OP.GG faz (a) [Provável que seja permitido]; isto não substitui a confirmação.