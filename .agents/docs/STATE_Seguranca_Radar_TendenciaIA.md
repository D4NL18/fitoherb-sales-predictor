# Auditoria de Seguranca - Radar externo v3.1 (Tendencia IA)

Veredito: NAO BLOQUEIA o radar. BLOQUEIA o deploy pelo achado S-1 (credencial no workflow, fora do escopo do radar, mas critica).

## Critico / Alto
- S-1 (ALTO) `.github/workflows/deploy-cloud-run.yml:110`: fallback `AUTH_PASSWORD || 'Fito1997@'` (e usuario `fitoherb` na L109) com senha em texto no repositorio. Correcao: remover o default, falhar o deploy se o secret estiver ausente, rotacionar a senha.

## Medio
- S-2 `store/radar_store.py:57-59` (`_check_source`): na leitura so verifica que url/dominio/titulo sao `str`. Um objeto plantado no bucket com `javascript:` ou URL interna passa na leitura estrita (a escrita valida com `is_safe_url`, a leitura nao). Correcao: revalidar `is_safe_url(url)`, `dominio == hostname`, tamanho do titulo (<=200), `dataPublicacao` ISO e `origemData` em lista fechada.
- S-3 `store/radar_store.py:78-98`: `geradoEm`, `mesBase` e `slug` nao sao validados na leitura (`mesBase` sem regex; `slug` sem regex; `radarHash` nao e recalculado). Correcao: validar `mesBase` com `^\d{4}-(0[1-9]|1[0-2])$`, `slug` com `^[a-z0-9-]{1,60}$`, exigir `slug`/`mesBase` iguais aos da chave e recalcular `radarHash`.

## Baixo
- S-4 `radar_store.py:26,105` / `radar_runner.py:125`: `searchSuggestionsHtml` (HTML vindo da web) e persistido no objeto compartilhado sem sanitizacao. Hoje NAO e exposto por `public_radar_view`; se for exposto, risco de XSS persistente. Correcao: nao persistir, ou persistir so com marcador de "nunca renderizar".
- S-5 `radar_store.py:139-142` `current_generation`: le o objeto mesmo invalido e sobrescreve com a geracao correta; OK. Mas o `ObjectConflict` descarta o radar recem-pago. Aceitavel.
- S-6 frontend `source-link.component.ts:2,41`: `safeHref` aceita http(s); a regra de negocio pede https. Correcao: so `https:`.
- S-7 `radar_schema.py:25`: o filtro de marcadores nao tem efeito pratico (campos sao enums). Defesa extra, sem custo. Nenhuma acao.

## Verificado sem falha
- Injecao indireta persistente: saida do modelo = so enums, tema de lista fechada por dimensao, `fonteIdx` inteiro, data ISO. `additionalProperties:false` + validacao estrita; qualquer violacao rejeita tudo e nada e gravado (`radar_schema.py:83-121`). Frases exibidas vem do backend (`radar_themes.py`). Um atacante que controle uma pagina pesquisada so consegue escolher um tema legitimo ou uma URL citada. Titulo e texto livre da web (so exibicao, interpolado, 200 chars).
- Cache/concorrencia: `if_generation_match` em `put`; lease de 90 s mais lock em processo; `ObjectConflict` tratado. Leitura estrita por conjunto exato de chaves; JSON puro, sem desserializacao insegura.
- Chave do objeto: `slug` = `[a-z0-9-]` (`slugify`), `mesBase` validado por regex na borda, sem `../` possivel. Assunto vem de lista fechada ou categoria sanitizada. Descricao da galeria nunca vai ao prompt.
- Custo: `hard_cap_queries` (1500) em `radar_policy` e `reserve`; fatia do radar, limite diario, `RADAR_RESERVED_MONTHLY_USD`; `force` do diagnostico nao renova o radar (`peek` + politica). `GET` e custo zero.
- Logs: `tia.radar.injectionSuspect` so com codigos de violacao, sem payload.
- Frontend: sem `innerHTML` no radar, `rel="noopener noreferrer"`, `target=_blank`.
- Env/deploy: variaveis novas sao nao secretas (`env.sh`, workflow L126-154).
