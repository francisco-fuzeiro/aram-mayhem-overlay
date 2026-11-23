# Fontes de dados ARAM Mayhem (queue 2400): investigação legal, 2026-11-23

Investigação só de leitura. Sem scraping, sem contactos. Complementa a §19 de `AUDITORIA_INDEPENDENTE_2026-11-23.md`.

## 0. Verdade desconfortável
1. **Não existe nenhum dataset aberto de Mayhem com licença reutilizável** além do que já tínhamos (AramHex CC BY-NC, arammayhem.com CC BY). Kaggle e HuggingFace: zero resultados para Mayhem. [Provável: pesquisa web, sem hits; não abri as APIs de pesquisa dos dois sites]
2. **A Riot API pública bloqueia Mayhem de propósito.** Os jogos não aparecem na lista de match IDs e `match-v5/matches/{id}` devolve **403**. [Provável: relato de utilizador com reprodução em RiotGames/developer-relations#1204, 28/10/2026; #1154 cita #1109 a dizer que é "intended behavior"; nenhum funcionário Riot identificado nas páginas lidas] O projeto Lanternko/arammeta confirma: "Mayhem 不存在於 Riot 公開 API". **A fase D2 (coletor match-v5) fica BLOCKED.** Não vale a pena gastar um pedido para confirmar; se quiseres, é 1 pedido com a nossa chave a um match ID Mayhem.
3. **A razão provável do bloqueio é a Riot não querer win rates de Mayhem** ("they don't want people generating win rates etc for their fun mode", comentário de utilizador em #1204). [Suposição sobre a intenção da Riot] Isto reforça a regra que já temos: o overlay nunca mostra WR/n, só tiers.
4. **A única fonte legal com as métricas ricas que queres (dano/min, KP, mortes, duração, comp inimiga, build, augments) é o histórico local do cliente (LCU)**: os teus jogos e, com consentimento, os de outros utilizadores. É exatamente o que o arammeta faz em escala. [Certo: o README/AGENTS.md do arammeta descreve recolha por LCU com jogadores-semente]

## 1. Tabela de fontes

| Fonte | URL | Licença / termos | Métricas | Cobertura / atualização | Veredicto |
| --- | --- | --- | --- | --- | --- |
| Riot API match-v5 | developer.riotgames.com/apis#match-v5 | Termos Riot API | Seria tudo, mas **403 para queue 2400** | Nenhuma para Mayhem | **Bloqueada** [Provável] |
| Riot API via RSO (jogos consentidos) | developer-relations#1204 | Pedido de feature aberto, sem endpoint | — | Não existe | **Não existe** [Provável] |
| **LCU: histórico do próprio jogador** | cliente local (`/lol-match-history/...`) | Dados do próprio utilizador; uso local | Por jogo: campeão, resultado, augments, itens finais, dano, KDA, KP derivável, duração, as 10 composições | ~20 jogos por jogador segundo o arammeta (outro relato diz até 200) [Provável]; o repo já tem `storage/history_import.py` | **Legal para uso pessoal** [Provável]; é a fonte certa para as métricas ricas |
| **Telemetria opt-in (LCU de vários utilizadores)** | modelo do arammeta / D5 da §19.5 | Consentimento explícito + política de privacidade; publicar só agregados sem PUUID/Riot ID | As mesmas do LCU, agregadas | Cresce com os utilizadores; arranque lento | **Legal com consentimento** [Provável]; requer registo do produto na Riot antes de distribuir (já está no P1) |
| AramHex (czgreat/aramhex-data) | github.com/czgreat/aramhex-data | **CC BY-NC 4.0** | Jogos, vitórias por campeão e campeão+augment | Servidor CN, 7 regiões, por patch | **Legal (não comercial, com atribuição)** [Certo, §19] |
| arammayhem.com/data | arammayhem.com | **CC BY 4.0** | Pick rate | Por patch | **Legal (até comercial)** [Certo, §19] |
| arammeta.com (Lanternko/ARAM-Mayhem-Database) | arammeta.com · github.com/Lanternko/ARAM-Mayhem-Database | **Código MIT** (linha "License: MIT." no README; não vi ficheiro LICENSE). **Dados: nenhuma licença**, nem termos, nem API, nem download | WR ajustado e bruto, jogos, tier, frequência de augment, WR de itens, pares campeão+augment | LCU por jogadores-semente, por patch | **Dados: não reutilizáveis sem autorização** (sem licença = todos os direitos reservados) [Provável]. **Código MIT: reutilizável** (coletor LCU, pipeline com encolhimento bayesiano), com aviso MIT [Provável; confirmar o LICENSE antes de copiar] |
| U.GG, Blitz, Mobalytics, METAsrc, OP.GG | u.gg/lol/aram-mayhem-tier-list, blitz.gg, metasrc.com | ToS comerciais; não consegui ler a cláusula de reutilização do U.GG | Tiers, WR, builds | Global, frequente | **Não usar** [Provável]; têm acesso privado à Riot (#1154 refere acesso "acordado com a equipa de Game Modes", não verificado) |
| MayhemMeta, ARAMKit, ARAMGG | — | Termos desconhecidos / "uso pessoal e não comercial" (ARAMKit) | WR, pick rate | — | **Só com autorização escrita** [Certo, §19] |
| Wiki LoL (Module:MayhemAugmentData) | wiki.leagueoflegends.com | Não consegui ler o rodapé; wikis Fandom/LoL costumam ser CC BY-SA [Suposição] | **Dados estáticos** dos augments, não estatísticas [Provável] | Por patch | Útil só para metadados; CDragon já cobre |
| Kaggle / HuggingFace | kaggle.com, huggingface.co | — | — | Nenhum dataset Mayhem encontrado | **Não existe** [Provável] |
| Yhprum/mayhem-tracker | github.com/Yhprum/mayhem-tracker | Não consegui ler | Tracker baseado no cliente (segundo #1154) | — | Por verificar; só ideias até ver a licença |

## 2. Recomendação (Proposta)
1. **Agora:** a BD de tiers usa AramHex (jogos/vitórias campeão e campeão+augment) + arammayhem.com (pick rate), como já decidido. Nada muda.
2. **Métricas ricas (dano/min, KP, mortes, duração, comp inimiga, build):** vêm do **LCU**. Passo 1: alargar `history_import.py` para guardar por jogo todas as estatísticas de participante e as 10 composições (só os teus jogos, local). Isto dá-te sinal real para o teu campeão-pool, mas **n pequeno**: não serve para tiers globais sozinho.
3. **Escala:** D5 (telemetria opt-in) é a única via legal para ter estas métricas em volume. Antes de distribuir: registo do produto no Developer Portal, consentimento explícito, só agregados, sem identificadores.
4. **Pedido de autorização** ao Lanternko (arammeta) para usar os agregados é o atalho com melhor relação custo/benefício: mesmo modo, recolha LCU, pares campeão+augment, código já MIT. Não contactei ninguém; fica para decidires.
5. **Risco de política Riot:** mesmo com dados legais, mostrar WR de augments é proibido pela política (ver P1). Os tiers continuam a esconder WR/n.

## 3. O que não consegui verificar
- Ficheiro LICENSE e ficheiros de dados em `docs/` do repo arammeta (robots bloqueado).
- Cláusula de reutilização dos ToS do U.GG; rodapé de licença da wiki; repo Yhprum/mayhem-tracker.
- Se o LCU devolve `playerAugment1..6` em todos os jogos Mayhem (o código atual já os lê; confirmar com um jogo real).
- Nenhum comentário identificado como sendo de funcionário Riot nos issues lidos.

## Fontes
- https://github.com/RiotGames/developer-relations/issues/1154
- https://github.com/RiotGames/developer-relations/issues/1204
- https://github.com/AFlyingP/ARAMPig/issues/3
- https://github.com/Lanternko/ARAM-Mayhem-Database e AGENTS.md
- https://arammeta.com/ e https://arammeta.com/about/
- §19 de AUDITORIA_INDEPENDENTE_2026-11-23.md (AramHex, arammayhem.com, ARAMKit, MayhemMeta)
