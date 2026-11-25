# STATE Seguranca - Tendencia IA (F7) - Auditoria Etapa 4

Escopo: `git diff origin/main...HEAD`. Revisao estatica (nao foram escritos testes ofensivos novos; a suite existente em `tests/trend_insights/` cobre rota OIDC, contrato sem campos de custo, rate limit e validacao).

## Veredito
APROVADO COM RESSALVAS. Nenhum achado Critico/Alto na F7. A esteira NAO e bloqueada pela F7. O achado pre-existente F-01 (fora do escopo) deve ser tratado antes do proximo deploy em producao.

## Achados

### Alto (fora do escopo da F7, pre-existente)
- F-01 `.github/workflows/deploy-cloud-run.yml:110`: `AUTH_PASSWORD: ${{ secrets.AUTH_PASSWORD || 'Fito1997@' }}` - senha Basic padrao literal no repositorio, injetada em producao (linha 124 via `--set-env-vars`, tambem visivel em descricao do servico). Correcao: remover o default, falhar o job se o secret faltar, rotacionar a senha (considerar comprometida) e passar segredos via Secret Manager (`--set-secrets`).

### Baixo
- F-02 `src/modules/trend_insights/auth/oidc_verifier.py:15`: `verify_oauth2_token` com `google_requests.Request()` novo a cada chamada busca os certificados do Google por requisicao, sem cache; requisicoes anonimas com bearer lixo geram trafego de saida (DoS leve, rota publica pelo bypass do Basic). Correcao: reutilizar um `Request` com `CacheControl` de sessao e/ou um pre-filtro barato (rejeitar tokens que nao tenham 3 segmentos/tamanho maximo) antes de verificar.
- F-03 `src/modules/trend_insights/llm/validation.py:114-119`: `_is_safe_url` bloqueia so IPv4 literal; aceita `localhost`, hosts internos, IPv6 literal e `user@host`. Mitigado porque a URL precisa estar em `cited_urls` (grounding) e o front so renderiza http(s) com `rel="noopener noreferrer"`, sem fetch server-side. Correcao: rejeitar `parsed.username`, `localhost`, sufixos `.local/.internal` e IPv6 (usar `ipaddress`).
- F-04 `validation.py:140`: `titulo` da fonte vem da saida do modelo, nao da citacao do grounding; texto de link pode enganar (phishing leve) apontando para URL citada. Correcao: usar o titulo de `GroundingCitation` quando existir.
- F-05 `src/modules/trend_insights/api/router.py:51-59`: identificador do limitador vem do usuario do cabecalho Basic nao verificado nesse ponto. Em producao o middleware ja valida o Basic (credencial unica), entao nao ha bypass; em ambiente sem auth (`AUTH_REQUIRED=false`) rotacionar o usuario burla o limite por minuto. Contador e por instancia (`generation_guard.py:28`): o teto real e o livro de orcamento no GCS (falha fechada, `budget_ledger.py:104`, US$0,20/dia), o que limita o custo. Correcao: documentar e manter `max-instances` baixo; opcionalmente chavear apenas por IP/`X-Forwarded-For` confiavel.
- F-06 Persistencia de `sugestoesBuscaHtml` (HTML do Google) no GCS (`llm_orchestrator.py:214`) embora `_public_diagnosis` o anule (`insights_service.py:239`). Seguro hoje; ao liberar no CP-10 manter `sandbox` sem `allow-scripts`/`allow-same-origin` (ja assim em `ai-diagnosis-block.component.ts:178`) e adicionar CSP `frame-src`/`frame-ancestors`. `allow-popups-to-escape-sandbox` e aceitavel so com `referrerpolicy=no-referrer` (presente).

### Informativo
- F-07 Nao ha CSP nem `X-Frame-Options`/`frame-ancestors` na aplicacao (pre-existente): clickjacking geral. Recomendado middleware de cabecalhos de seguranca.
- F-08 `AFFINITY_SYNC_AUDIENCE` e `AFFINITY_SYNC_INVOKER_SA` nao constam no `.env.example` (sem segredo; so documentacao). Sem eles a rota fica fechada (fail-closed, correto).

## Verificacoes sem achado
1. Rota OIDC: isencao do Basic por igualdade exata de metodo `POST` e caminho (`src/core/auth.py:37`); variacoes (`/x/`, `//`, maiusculas, `..`) nao casam e caem no Basic/404. Dependencia valida assinatura/exp/issuer Google (biblioteca), `aud`, `email_verified is True` e e-mail da SA (case-insensitive); sem configuracao = 401; toda falha devolve a mesma resposta `TIA-006` sem causa.
2. Prompt injection: dados em blocos com nonce, regras so no `system`; descricao da galeria sanitizada (HTML/URL/e-mail/delimitadores/`<>{}` removidos); lista branca de campos; saida validada por schema estrito, zero digitos, SKU do pacote, fator externo exige fonte citada e data no periodo, confianca ALTA rebaixada; textos renderizados por interpolacao Angular (sem `innerHTML`); nenhuma ferramenta alem de busca.
3. SQL: novas consultas usam `?` para todas as datas/SKU; f-strings so interpolam constantes do modulo (`SALE_OPERATION`, `RETURN_OPERATION_PATTERN`); `sku` coagido a `int`.
4. Segredos: sem chave de API (Vertex via ADC); `.env.example` sem segredos reais; logs so com tipo de excecao, contagens, custo e codigos de violacao (sem prompt, payload, PII ou usuario).
5. Kill-switch `TREND_AI_ENABLED`, modelos em lista permitida, orcamento falha fechada, `force` com teto diario proprio.
6. Contrato: `_build_data` exclui `descricao_galeria`; custo/tokens/hash/precos ficam so em `StoredInsight` (nao publico); teste `FORBIDDEN_COST_KEYS` cobre.
7. Novos endpoints GET/POST ficam sob Basic global; entrada validada (Pydantic `Literal`, regex de mes, `sku` limitado, `force` estrito).
8. Frontend da F7 nao usa localStorage/sessionStorage (store documenta e nao persiste). Usos existentes em inventory/pricing sao pre-existentes e guardam cache de dados, nao credenciais.
9. Dependencias: `google-genai==3.6.1` e `google-cloud-storage==3.17.2` fixas e resolvem no PyPI (versoes atuais); sem CVE conhecida identificada nesta revisao (rodar `pip-audit` no CI).
