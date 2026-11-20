# Fixtures: manifesto (v3, 2026-11-20)

## Contagens reconciliadas

**Catálogo de augments**
- `cdragon_cherry_augments_2026-11-20.json` tem **600** linhas.
- As linhas Mayhem (id ≥ 1000 ou `/Kiwi/`) são **331**: 132 Gold, 104 Prismatic, 95 Silver.
- A deduplicação remove 3: `1424 ???`, `3176 (espaços)` e `393 Icathia's Fall` (gémeo de 1361). Ficam **328** em `expected_mayhem_catalog_2026-11-20.json`.

**Imagens: 26 no total**
- `title_crops_1440p/`: **13** PNG, dos quais 11 com nome (Gold) e 2 diálogos do League (`expected_name: null`).
  - Os 2 crops `ocr_1795024938_*` foram removidos: tinham UI externa e janela pequena.
- `title_crops_prismatic_snips/`: **8** PNG, 4 Prismatic e 4 Gold, dos quais 2 com título em 2 linhas.
  - São recortes aproximados de snips do Windows. Servem para OCR e C1, **não** para geometria.
- `no_offer_2544x1353/`: **5** PNG do mundo do jogo sem oferta.

**Itens**
- `ddragon_items_16.23.1_compact.json`: 480 itens (mapas 11/12).
- `cdragon_items_2026-11-20.json`: 863 itens. v3: o campo `source` regista que `latest` == 16.23 (content-metadata), equivalente ao caminho fixado `/16.23/`. Dados iguais à v2.
- `ddragon_items_16.23.1_details.json`: 181 itens do pool, com passivas, ativas, stats, from e into.
- `expected_item_pool_16.23.1.json`:
  - classes dos 480;
  - `pool_ids` **181**;
  - `final_ids` **111** (104 final + 7 boots_tier2).
- `expected_item_properties_16.23.1.json`: 11 propriedades com regra explícita e 6 grupos exclusivos.

**Validações feitas [Certo]**
- OCR com Tesseract 5.3.4 e o catálogo A1: **21/21** títulos corretos. Os 2 diálogos dão `None`.
- Com o catálogo atual (sem A1): 18/21.
- Teal fraction:
  - 19 cartas entre 0,789 e 0,958;
  - 2 diálogos sobre uma carta entre 0,865 e 0,871;
  - 5 sem oferta: 0,000.
- O DD e o CDragon concordam em preço, `from` e `into` nos 181 itens do pool.

## Revisão manual das imagens (2026-11-20)

Vi as 26 imagens numa folha de contacto.

**O que contêm:**
- títulos de cartas, incluindo chips de tags do próprio League por baixo do título;
- 2 diálogos do League ("will be marked as idle", "game will now exit");
- terreno do mapa, 1 campeão e 1 número de dano ("-171").

**O que não contêm:**
- OP.GG ou outras apps;
- desktop;
- nomes de jogador, chat ou HUD (KDA, tempo, minimapa).

**Conclusão:** aptas para o repo público, só nas pastas indicadas nas blueprints. Mais nenhuma imagem é permitida.

## Ficheiros

| Ficheiro | Bytes | sha256 (16) |
|---|---|---|
| `cdragon_cherry_augments_2026-11-20.json` | 34322 | `580e74ba3a16d18d` |
| `cdragon_items_2026-11-20.json` | 112231 | `f5f837fa3763619b` |
| `ddragon_items_16.23.1_compact.json` | 80196 | `28f18e20b3c558a6` |
| `ddragon_items_16.23.1_details.json` | 36588 | `257bfb79b20141ff` |
| `expected_item_pool_16.23.1.json` | 14313 | `5011090b5cf2e55d` |
| `expected_item_properties_16.23.1.json` | 3276 | `e73622a98ef025b5` |
| `expected_mayhem_catalog_2026-11-20.json` | 9131 | `458d2b7f81d680f5` |
| `no_offer_2544x1353/card_centre_1795134399156658000_1.png` | 34112 | `5ff58b0e19c6cb7d` |
| `no_offer_2544x1353/card_left_1795134399156658000_0.png` | 41224 | `3ce0daf3992ffd7a` |
| `no_offer_2544x1353/card_left_1795134416913524800_0.png` | 24918 | `ed9d083d1fd753ab` |
| `no_offer_2544x1353/card_right_1795134399156658000_2.png` | 45015 | `9dec9e402dce42a3` |
| `no_offer_2544x1353/card_right_1795134416913524800_2.png` | 19997 | `3ffc4b3921976267` |
| `title_crops_1440p/ground_truth.json` | 1547 | `d5f9f88707f5a36d` |
| `title_crops_1440p/ocr_1795024923_centre.png` | 15268 | `1815316477bf6480` |
| `title_crops_1440p/ocr_1795024923_right.png` | 12681 | `8a3f62bd4b45a7b2` |
| `title_crops_1440p/ocr_1795025002_centre.png` | 35955 | `c770eacd8573360d` |
| `title_crops_1440p/ocr_1795025015_centre.png` | 15275 | `ed622cccf35a5e20` |
| `title_crops_1440p/ocr_1795025015_left.png` | 12644 | `61b2a1cf57fd04c3` |
| `title_crops_1440p/ocr_1795025015_right.png` | 12286 | `66a0b22eb986461a` |
| `title_crops_1440p/ocr_1795025241_centre.png` | 12713 | `66f277cf31a842f3` |
| `title_crops_1440p/ocr_1795025241_left.png` | 12584 | `1fb2da5c11ca8af4` |
| `title_crops_1440p/ocr_1795025241_right.png` | 12773 | `77a05feeddd0f85c` |
| `title_crops_1440p/ocr_1795025367_centre.png` | 36361 | `2f8cb80492ce6bbf` |
| `title_crops_1440p/region_1795025142_centre.png` | 12713 | `dfbb0a1c966f5430` |
| `title_crops_1440p/region_1795025142_left.png` | 12644 | `ad7373f0ec0c2f90` |
| `title_crops_1440p/region_1795025142_right.png` | 12269 | `d6fd8840f87a4b5a` |
| `title_crops_prismatic_snips/ground_truth.json` | 1378 | `b241845a0c449255` |
| `title_crops_prismatic_snips/snip_015021_takeemdowndowndown.png` | 23539 | `37f1fdbd9c902762` |
| `title_crops_prismatic_snips/snip_015907_takeemdowndowndown.png` | 23167 | `b004fa933c2620b3` |
| `title_crops_prismatic_snips/snip_023747_enpassant.png` | 15581 | `bcf5a97d06d5ff90` |
| `title_crops_prismatic_snips/snip_023747_itskillingtime.png` | 17748 | `0bc9386e7b3a7cbf` |
| `title_crops_prismatic_snips/snip_023747_ravenousbind.png` | 18056 | `e3a31f2f7029e71d` |
| `title_crops_prismatic_snips/snip_121107_backtobasics.png` | 17601 | `5709d7a4ca68b83c` |
| `title_crops_prismatic_snips/snip_121107_biggestsnowballever.png` | 20045 | `f5188d14ebb8763c` |
| `title_crops_prismatic_snips/snip_121107_goliath.png` | 13758 | `66a51aaad9b7fc56` |