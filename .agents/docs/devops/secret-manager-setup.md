# Guia — Login do app no Google Secret Manager

> **Objetivo:** tirar `AUTH_USERNAME` e `AUTH_PASSWORD` do GitHub e do código. O Cloud Run lê os dois direto do Secret Manager. O `src/core/auth.py` não muda: continua lendo as variáveis de ambiente.
> **Contexto:** o valor padrão que estava em `.github/workflows/deploy-cloud-run.yml` foi removido, mas **continua no histórico do Git de um repositório público**. Por isso a senha precisa ser **nova**. Não reutilize a antiga.

Substitua `SEU_PROJETO` pelo ID do projeto GCP e `SERVICO` pelo nome do serviço no Cloud Run (padrão do workflow: `fitoherb-sales-predictor`). Região padrão: `southamerica-east1`.

---

## 1. Ativar a API

```powershell
gcloud services enable secretmanager.googleapis.com --project=SEU_PROJETO
```

## 2. Criar o secret do usuário

```powershell
$f = New-TemporaryFile; [IO.File]::WriteAllText($f.FullName, "NOVO_USUARIO"); gcloud secrets create fitoherb-auth-username --data-file=$($f.FullName) --replication-policy=automatic --project=SEU_PROJETO; Remove-Item $f.FullName
```

## 3. Criar o secret da senha

O comando pede a senha sem mostrá-la na tela e a grava **sem quebra de linha no final** (uma quebra faria o login falhar). Use uma senha longa e única, de um gerenciador de senhas.

```powershell
$s = Read-Host "Nova senha" -AsSecureString; $p = [System.Net.NetworkCredential]::new("", $s).Password; $f = New-TemporaryFile; [IO.File]::WriteAllText($f.FullName, $p); gcloud secrets create fitoherb-auth-password --data-file=$($f.FullName) --replication-policy=automatic --project=SEU_PROJETO; Remove-Item $f.FullName; $p = $null
```

## 4. Dar permissão de leitura à conta que roda o serviço

Descubra a conta de serviço do Cloud Run:

```powershell
gcloud run services describe SERVICO --region=southamerica-east1 --project=SEU_PROJETO --format="value(spec.template.spec.serviceAccountName)"
```

Se vier vazio, é a conta padrão do Compute (`NUMERO_DO_PROJETO-compute@developer.gserviceaccount.com`). Conceda o acesso aos dois secrets:

```powershell
gcloud secrets add-iam-policy-binding fitoherb-auth-username --member="serviceAccount:CONTA_DO_SERVICO" --role="roles/secretmanager.secretAccessor" --project=SEU_PROJETO
```

```powershell
gcloud secrets add-iam-policy-binding fitoherb-auth-password --member="serviceAccount:CONTA_DO_SERVICO" --role="roles/secretmanager.secretAccessor" --project=SEU_PROJETO
```

## 5. Primeiro deploy

Rode o workflow (push na `main` ou "Run workflow"). Se falhar com erro do tipo *"Cannot update environment variable [AUTH_PASSWORD] to the given type because it has already been set with a different type"*, o serviço ainda tem as variáveis antigas em texto puro. Remova-as uma vez e repita o deploy:

```powershell
gcloud run services update SERVICO --region=southamerica-east1 --project=SEU_PROJETO --remove-env-vars=AUTH_USERNAME,AUTH_PASSWORD
```

Enquanto isso o app fica fechado para todos (login obrigatório sem credencial válida). Isso é intencional.

## 6. Limpar o que sobrou

- No GitHub, em *Settings → Secrets and variables → Actions*, **apague** `AUTH_USERNAME` e `AUTH_PASSWORD`. O workflow não usa mais.
- Teste o login com a senha nova e confirme que a antiga **não** entra mais.

## Trocar a senha depois

```powershell
$s = Read-Host "Nova senha" -AsSecureString; $p = [System.Net.NetworkCredential]::new("", $s).Password; $f = New-TemporaryFile; [IO.File]::WriteAllText($f.FullName, $p); gcloud secrets versions add fitoherb-auth-password --data-file=$($f.FullName) --project=SEU_PROJETO; Remove-Item $f.FullName; $p = $null
```

Depois force uma nova revisão (novo deploy, ou `gcloud run services update SERVICO --region=southamerica-east1 --project=SEU_PROJETO --update-env-vars=ROTACAO=$(Get-Date -Format yyyyMMddHHmm)`). Com `:latest`, a nova versão é lida na próxima revisão.

---

## Pendências relacionadas
- **`DB_PASSWORD`** ainda vem dos secrets do GitHub. Não está exposta no código, mas o mesmo padrão (Secret Manager + `--set-secrets`) vale para `DB_USER` e `DB_PASSWORD`. Recomendado, e vale a revisão da senha do banco.
- **Aba Financeiro:** decisão de acesso (credencial separada ou perfis) segue em aberto em `.agents/docs/tasks/financeiro.md` §8.
