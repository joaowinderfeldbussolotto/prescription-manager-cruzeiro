# Relojoaria e Ótica Cruzeiro — Cadastro de Clientes e Receitas Ópticas

Réplica moderna de um sistema originalmente feito em Oracle APEX para a
**Relojoaria e Ótica Cruzeiro**: cadastro de **clientes** e das **receitas
ópticas** associadas a cada um. Escopo atual: apenas o módulo óptico (cliente +
receita) + autenticação.

> **Sem IA nesta fase.** O sistema é CRUD puro. A visão de copilot (busca em
> linguagem natural, identificação de cliente por imagem) está registrada
> apenas como intenção na [`SPEC.md`](./SPEC.md), sem código nem tela.

---

## ⚠️ Estado Atual do Deploy

A instância EC2 (t2.micro) está **rodando, mas sem HTTPS nem Google OAuth**:

- **URL pública**: via DNS da AWS (ex: `http://ec2-XX-XX-XX-XX.compute-1.amazonaws.com:8080`)
- **Protocolo**: HTTP-only (sem certificado TLS — aviso no navegador)
- **Autenticação**: dev auth (allowlist simples, sem validação de senha)
  - Login: qualquer e-mail na allowlist (default: `admin@example.com`)
  - Sem suporte a Google OAuth neste momento (requer HTTPS)
- **Banco/Storage**: MongoDB e MinIO rodando containerizados na instância
- **Custo**: ~US$10/mês (ou perto de zero no Free Tier)

**Pra usar em produção real**, você vai precisar:
1. **HTTPS + certificado real**: Let's Encrypt via `deploy/user-data.sh` (scripts prontos, requer rodá-los na instância via SSH)
2. **Google OAuth**: configurar Client ID no Google Cloud Console após ter HTTPS
3. Desabilitar dev auth: `DEV_AUTH_ENABLED=false` no `.env`

Esse estado atual serve pra validação e testes; a infra tá pronta pra escalar.

---

## Como este projeto foi construído

Projeto construído majoritariamente com IA generativa, usando **Claude Code
Web** e **Claude Code CLI** (Anthropic).

Considerei aplicar Spec Driven Development formal, mas pareceu
desproporcional pro escopo deste projeto — optei por um fluxo mais direto:

### Ciclos de planejamento antes de código

Para cada funcionalidade, usei o modo de planejamento do Claude Code,
explorando o raciocínio do Opus 4.8 pra gerar planos de implementação
detalhados (arquivos afetados, contratos de API, decisões de design) antes
de qualquer código ser escrito. Só depois de revisar o plano e concordar
com o que estava proposto é que pedia pra implementar.

**Exemplo concreto**: upload eager de receita + extração IA mock. O
planejamento explorou: "qual é o UX ideal (preview instant)?", "como
validar imagem antes de submeter receita?", "se a IA for real depois, qual
é o contrato de API que faria sentido?" — só depois disso foi escrito código.

### ~98% do código escrito pela IA

A intervenção manual direta no código foi mínima — praticamente restrita a
debug (ex: diagnosticar erros do deploy na instância EC2 em produção).
Isso demonstra que o planejamento antecipado permitiu implementações diretas,
sem iterate-and-fix loops caros.

### Validação em camadas

Em vez de esperar a integração de serviços reais, cada feature foi validada
em camadas:

1. **Backend mockado**: endpoints mock com o mesmo contrato de API que a
   versão real (ex: `/api/receitas/extracao-ia` retorna sugestões em JSON).
   Permitiu exercitar UI de ponta a ponta sem Mongo/MinIO reais.

2. **Testes unitários do backend**: a suíte (`backend/tests/`) foi gerada
   junto com cada funcionalidade:
   - Testes da camada feliz (happy path)
   - Testes de erro (404, 422, 500)
   - Isolamento de dependências via `monkeypatch` e `dependency_overrides`
   - Validação de serialização (BSON ↔ JSON, date ↔ datetime)

3. **Testes de integração via Playwright**: fluxo completo de UI (login →
   cadastro de cliente → receita com upload eager → extração IA → visualização).
   Rodou contra dev server Vite + backend-fake sem depender de BD real.

4. **Validação sem dependências externas**: dev auth simples (sem Google),
   mock de IA, timestamps previsíveis — tudo testável localmente.

### Documentação de decisões

Cada design choice foi capturada — não é só "como funciona", mas "por que
funciona assim":
- Por que imagem é obrigatória? Força documentação, reduz campos.
- Por que soft delete? Preserva histórico se houver receitas.
- Por que upload direto ao S3? Mais rápido, menos carga no backend,
  padrão AWS nativo.
- Por que feature toggles via env? Permite dev local vs prod sem alterar
  código.

**Resultado**: código estruturado em camadas (auth → routers → models →
db/storage), com abstrações pensadas pra permitir migrations futuras
(S3 real em vez de MinIO, DynamoDB em vez de MongoDB) sem impactar o
frontend.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | FastAPI (Python 3.12), async |
| Frontend | React + Vite |
| Banco | MongoDB (local via Docker) |
| Storage de imagem | MinIO (local via Docker, API compatível com S3) |
| Orquestração | Docker Compose |

---

## Subindo o projeto (Docker Compose)

Pré-requisitos: Docker + Docker Compose.

```bash
# opcional: customizar variáveis
cp .env.example .env

docker compose up --build
```

Sobe quatro serviços (+ um init de bucket):

| Serviço | URL |
|---|---|
| **Frontend** (nginx) | http://localhost:8080 |
| **Backend** (FastAPI) | http://localhost:8000 — docs em `/docs` |
| **MongoDB** | `mongodb://localhost:27017` |
| **MinIO** API / Console | http://localhost:9000 / http://localhost:9001 |

Abra **http://localhost:8080** e faça login (veja abaixo).

### Primeiro login

O cadastro de usuários é **manual** (não há autoregistro) — é a _allowlist_.
Na primeira subida, o backend semeia um admin a partir de `SEED_ADMIN_EMAIL`
(default `admin@example.com`).

Como não é necessário configurar o OAuth do Google para desenvolver, há um
**login de desenvolvimento** habilitado por padrão (`DEV_AUTH_ENABLED=true`):
na tela de login, informe o e-mail semeado (`admin@example.com`) e entre.

> ⚠️ O login de dev **não valida senha nem token** — só confere a allowlist.
> **Desabilite em produção** (`DEV_AUTH_ENABLED=false`) e configure o Google.

Para adicionar mais usuários à allowlist, insira direto no Mongo:

```js
// mongosh mongodb://localhost:27017/aureye
db.usuarios.insertOne({
  email: "atendente@example.com",
  nome: null,
  ativo: true,
  role: "atendente",           // "admin" | "atendente"
  data_criacao: new Date(),
  ultimo_login: null
})
```

Setar `ativo: false` **revoga o acesso na hora** (o backend recheca o usuário
a cada requisição), sem apagar o registro.

### Login com Google (produção / opcional em dev)

1. Crie um OAuth Client (tipo _Web_) no Google Cloud Console.
2. Defina `GOOGLE_CLIENT_ID` no `.env` (backend valida) — o mesmo valor é
   passado ao build do frontend como `VITE_GOOGLE_CLIENT_ID`.
3. O frontend passa a exibir o botão “Entrar com Google”. O backend valida a
   assinatura do `id_token`, exige `email_verified` e confere a allowlist.

---

## Desenvolvimento fora do Docker

**Backend:**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env    # ajuste MONGO_URI / S3_ENDPOINT_* p/ localhost
uvicorn app.main:app --reload
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev             # http://localhost:5173, proxy /api -> :8000
```

O Vite faz proxy de `/api` para o backend, então o cookie de sessão funciona
em mesma origem (`VITE_API_PROXY_TARGET` controla o alvo).

**Testes do backend:**

```bash
cd backend && pytest
```

---

## Arquitetura

```
Navegador ──▶ nginx (frontend) ──/api──▶ FastAPI ──▶ MongoDB
    │                                        │
    │  PUT presigned (upload direto)         └──▶ MinIO (presign)
    └────────────────────────────────────────────▶ MinIO :9000
```

- **Sessão própria via cookie httpOnly.** O frontend nunca guarda o `id_token`
  do Google; após o login, recebe um cookie de sessão (JWT `httpOnly`,
  `secure`, `sameSite=lax`).
- **Upload direto pro storage.** O backend só emite uma _presigned URL_; o
  browser faz `PUT` direto no MinIO. Depois envia a `key` no create/update da
  receita, e a leitura da imagem usa uma presigned URL de `GET`.
- **Dois endpoints de storage.** O backend fala com o MinIO pela rede interna
  (`minio:9000`), mas assina as presigned URLs com o host que o navegador
  acessa (`localhost:9000`). Ver `backend/app/storage.py`.

### Regras de negócio (backend)

- **Cadastro de receita**: o **único campo obrigatório é a imagem**. A **data de
  emissão** assume _hoje_ por padrão e a **validade**, _emissão + 12 meses_ —
  ambas editáveis. Todos os demais dados (graus OD/OE, médico, DP, observações)
  são opcionais. No frontend, só a imagem aparece por padrão; o resto fica atrás
  de um "Adicionar detalhes da receita".
- **Soft delete de cliente**: se houver receitas vinculadas, o cliente é
  arquivado (`deletado=true`) em vez de apagado, preservando o histórico.
- **CPF**: validação de _formato_ apenas (não valida dígito verificador).

---

## As duas migrações futuras (decisão consciente)

A `SPEC.md` é honesta sobre isso, e vale repetir: **as duas migrações previstas
não têm o mesmo custo.**

### MinIO → S3 real: quase transparente ✅

MinIO implementa a API do S3, então o mesmo client `boto3` funciona nos dois.
Para migrar, muda-se apenas `S3_ENDPOINT_*` e as credenciais via variável de
ambiente. **O código de presigned URL não muda.**

### MongoDB → DynamoDB: **não é drop-in** ⚠️

MongoDB é um banco de documentos com queries flexíveis; o sistema usa isso:

- busca de cliente por nome/telefone parcial (`$regex`);
- contagem de receitas por cliente (agregação);
- filtro de receitas por intervalo de validade (dashboard).

DynamoDB é key-value/single-table, otimizado para acesso por chave conhecida.
Essas queries livres exigiriam **redesenho de modelagem** (GSIs, chaves
compostas), não só troca de driver. É uma reescrita da camada de acesso a
dados, não uma configuração — por isso está isolada em
`backend/app/models/*.py` e `backend/app/db/`, para concentrar o impacto.

---

## Estrutura do projeto

```
backend/
  app/
    main.py            # app FastAPI + lifespan (connect, bucket, seed)
    config.py          # settings via env (pydantic-settings)
    auth/              # google (id_token), session (JWT cookie), deps (roles)
    db/                # conexão Mongo async + serialização BSON<->API
    models/            # camada de persistência (usuario, cliente, receita)
    schemas/           # Pydantic (request/response)
    routers/           # auth, clientes, receitas, uploads, dashboard, agente
    storage.py         # MinIO/S3 (boto3) + presigned URLs
  tests/               # testes de schema/regra e de presign
frontend/
  src/
    api/               # client axios + endpoints
    context/           # AuthContext (sessão)
    components/        # Logo, Layout, ValidadeBadge, ProtectedRoute
    pages/             # login, dashboard, clientes, receitas, agente
    utils/             # formatação e status de validade
  nginx.conf           # serve o build + proxy /api
docker-compose.yml
```

---

## Endpoints da API

Todas as rotas de negócio ficam sob o prefixo `/api` e exigem sessão válida
(exceto `/api/auth/*` de login).

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/auth/google` | Login com `id_token` do Google |
| POST | `/api/auth/dev-login` | Login de dev (allowlist, sem OAuth) |
| GET | `/api/auth/me` | Usuário da sessão |
| POST | `/api/auth/logout` | Encerra a sessão |
| POST | `/api/clientes` | Cria cliente |
| GET | `/api/clientes?busca=&page=&limit=` | Lista com busca/paginação |
| GET | `/api/clientes/{id}` | Detalhe + histórico de receitas |
| PUT | `/api/clientes/{id}` | Edita |
| DELETE | `/api/clientes/{id}` | Remove (soft se houver receitas) |
| POST | `/api/clientes/{cliente_id}/receitas` | Cria receita |
| GET | `/api/clientes/{cliente_id}/receitas` | Timeline de receitas |
| GET | `/api/receitas/{id}` | Detalhe + URL da imagem |
| PUT | `/api/receitas/{id}` | Edita |
| DELETE | `/api/receitas/{id}` | Remove |
| POST | `/api/uploads/presigned-url` | Presigned URL de upload |
| GET | `/api/dashboard` | 3 métricas do dashboard |
| POST | `/api/agente/mensagem` | Chat com o agente (mock) — ver "Agente" no Manual de Uso |

Documentação interativa (Swagger) em **http://localhost:8000/docs**.

---

## Manual de Uso

### Autenticação e Permissões

A aplicação suporta **dois modos de login**:

| Modo | Descrição | Quando usar | Config |
|------|-----------|-----------|--------|
| **Login de Desenvolvimento** | Email + allowlist simples, sem OAuth | Dev local | `DEV_AUTH_ENABLED=true` |
| **Login com Google** | Google OAuth, `id_token` validado no backend | Produção | `GOOGLE_CLIENT_ID=<ID>` |

- **Allowlist**: usuários devem estar na collection `usuarios` do MongoDB (role: `admin` ou `atendente`).
- Setar `ativo: false` bloqueia acesso imediatamente.
- Dados do usuário (nome, email, role) vêm do token/allowlist; edição manual só no Mongo.

### Fluxo 1: Cadastrar um Cliente

**Campos obrigatórios**: nome e telefone  
**Campos opcionais**: CPF (validação de formato apenas), email, data de nascimento, endereço

**Fluxo na UI**: Dashboard → "Novo cliente" → preenche dados → "Salvar" → sucesso (toast + redireciona pra detalhe)

### Fluxo 2: Buscar e Listar Clientes

- Campo de busca com debounce 300ms
- Busca por **nome ou telefone** (regex case-insensitive)
- Paginação: 20 itens/página (máximo 100)
- Exibe total de receitas por cliente
- Click em cliente: abre `ClienteDetail`

### Fluxo 3: Editar ou Remover Cliente

**Editar**: click em cliente → detail → "Editar" → form pré-preenchido → "Salvar"

**Remover**:
- Sem receitas? Apaga completamente (hard delete)
- Com receitas? Marca `deletado=true`, fica oculto mas histórico preservado

### Fluxo 4: Cadastrar uma Receita (o fluxo mais importante)

**Decisão crucial: imagem é obrigatória.** Tudo começa com upload da imagem; demais dados são opcionais.

#### Passo 1: Selecionar imagem
- Drag-and-drop ou clique
- Tipos: JPEG, PNG, WebP, PDF
- Upload **imediato** (PUT presigned URL direto pro MinIO/S3)
- Ao terminar: habilita "Preencher com IA"

#### Passo 2: Detalhes (opcional)
- Toggle "Adicionar detalhes da receita"
- **Datas**: emissão (default=hoje), validade (default=emissão+12m, recalcula se emissão mudar)
- **Olho Direito (OD) + Esquerdo (OE)**: esférico, cilindrico, eixo, adição
- **DP**: única, longe, perto
- **Geral**: nome médico, CRM, observações

**Validações**: validade ≥ emissão; ranges dos graus (validação "grosseira" apenas)

#### Passo 3: Preencher com IA (opcional)
- Requer: imagem uploaded + `EXTRACAO_IA_ENABLED=true`
- Backend lê bytes da imagem, retorna sugestões
- Frontend preenche **apenas campos vazios** (nunca sobrescreve)
- Aviso laranja: "Sugestão gerada por mock — revise todos os campos"

#### Passo 4: Salvar
- Click "Salvar receita"
- Redireciona pra `ReceitaView` + toast "Receita cadastrada com sucesso"

### Fluxo 5: Visualizar Receita

**Layout**: imagem grande (esquerda) + dados stacked (direita)
- Datas & médico
- Tabela OD/OE com graus
- DP
- Observações

**Formatação**: datas `DD/MM/YYYY`, graus 2 decimais (ex: `-2.50`), eixo `0-180°`

**Botões**: "Editar", "Remover"

### Fluxo 6: Dashboard

Ao fazer login, 3 métricas:
1. **Total de clientes** (exclui deletados)
2. **Receitas neste mês** (contagem por `data_cadastro`)
3. **Receitas vencendo em 30 dias** (validade entre hoje e hoje+30d)

### Fluxo 7: Agente (chat em linguagem natural — mock)

Aba **Agente**: um chat onde o usuário cadastra, edita e busca clientes
conversando, ao invés de preencher formulários. Ex: "Cadastra a cliente Maria
Souza, CPF 111.222.333-44…" ou "Busca as receitas da Maria Souza".

**Decisão de design importante: a interpretação da frase é mock, mas as
ações no banco são reais.** Não há LLM nesta fase — e, como o frontend **só
oferece frases fixas** (chips de sugestão, sem texto livre), o backend não
precisa de NLU nem de regex pra extrair intenção e dados: ele faz uma
**correspondência exata** entre a mensagem recebida e uma tabela de cenários
conhecidos (`CENARIOS_MOCK` em `backend/app/schemas/agente.py`), cada um já
com o *intent* e os argumentos que a tool precisa. **A partir daí, a
execução é 100% real** — reusa os mesmos repositórios de `routers/clientes.py`
(`cliente_repo.create/update/list_paginated`): cadastra clientes de verdade,
atualiza telefone de verdade, e os links retornados abrem clientes reais com
os dados carregados. Se a busca por nome for ambígua (mais de um cliente
encontrado), o agente devolve **um link para cada um**, ao invés de adivinhar.

Por que exact match em vez de regex/heurística de linguagem: eliminar de vez
os edge cases de parsing (acentuação, ordem das palavras, nomes compostos)
sem esconder a mecânica real do fluxo — a tabela de cenários **é** o
contrato de intent + argumentos que um LLM real produziria a partir de texto
livre; hoje ela é preenchida à mão porque as frases de entrada já são
conhecidas de antemão (são os próprios chips do frontend).

**O que muda quando um LLM real entrar** (fora de escopo agora): só a
função `interpretar_mensagem` — troca o lookup na tabela por uma chamada ao
modelo com tool-calling, produzindo o mesmo formato de saída (`intent` +
`argumentos`). O contrato de request/response da API, a execução das tools
no banco e a UI do chat **não mudam**. O campo de texto do chat já existe na
tela, mas fica desabilitado — sinalizando que o texto livre é o próximo
passo, não uma reescrita de tela.

**Toggle:** `AGENTE_ENABLED=false` no `.env` esconde a aba e desliga o
endpoint (404).

### Features Principais

#### Upload Direto ao S3/MinIO
Imagens **não passam pelo backend HTTP**:
1. Frontend pede presigned URL ao backend
2. Frontend faz PUT direto no S3/MinIO
3. Backend gera presigned URL de leitura (expiração curta)

**Por quê?** Mais rápido, menos carga no backend, padrão AWS nativo.

**Configuração**: `S3_ENDPOINT_PUBLIC` (navegador), `S3_ENDPOINT_INTERNAL` (backend)

#### Extração de IA (Hoje é Mock)
- Botão "Preencher com IA" sugestiona dados da receita a partir da imagem
- **Hoje**: mock (dados fictícios)  
- **Amanhã**: integração real com OCR/IA  
- **Contrato é idêntico** → nenhuma mudança na UI

Feature toggle: `EXTRACAO_IA_ENABLED` (env)

### Decisões de Design que Afetam UX

| Decisão | Efeito |
|---------|--------|
| **Imagem obrigatória** | Receita sem imagem não existe. Força documentação. |
| **Upload eager** | Validação de tipo antes de salvar receita completa. |
| **Detalhes colapsáveis** | Reduz visual clutter. Toggle "Adicionar detalhes". |
| **Validade auto-calculada** | Default +12m, editável, recalcula se emissão mudar. |
| **Graus opcionais** | Flexível; receita pode ter só um olho. |
| **Soft delete** | Cliente com receitas fica oculto, histórico seguro. |
| **CPF formato apenas** | Validação mínima; dígito verificador fica pra depois. |
| **Presigned URLs curtas** | Segurança; URL compartilhada após expiração não funciona. |
| **Feature toggles via `.env`** | Ativa/desativa IA, dev auth, Google, Agente sem redeploy. |
| **Agente por sugestões fixas** | Sem texto livre ainda; catálogo de frases exercitando cada caso de uso. |
| **Interpretação do Agente por exact match** | Sem regex/NLU nesta fase; tools que ele aciona são reais no banco. |

### Configuração por Feature

Edite `.env` e restarte (`docker compose up -d`):

| Variável | Default | Efeito |
|----------|---------|--------|
| `DEV_AUTH_ENABLED` | `true` | Botão de login simples |
| `GOOGLE_CLIENT_ID` | vazio | Botão "Entrar com Google" |
| `EXTRACAO_IA_ENABLED` | `true` | Botão "Preencher com IA" |
| `AGENTE_ENABLED` | `true` | Aba "Agente" (chat mock) |
| `COOKIE_SECURE` | `false` | Cookie só funciona com HTTPS se `true` |
| `CORS_ORIGINS` | `http://localhost:*` | Origins autorizadas pra CORS |

### Próximos Passos (Road Map)

- **IA real (extração de receita)**: substitua o mock em `backend/app/schemas/extracao.py`. UI não muda.
- **LLM real (Agente)**: substitua o lookup por exact match em
  `interpretar_mensagem` (`backend/app/schemas/agente.py`) por tool-calling
  de um modelo de verdade, e destrave o campo de texto livre em
  `frontend/src/pages/Agente.jsx`. Contrato de API e execução das tools não mudam.
- **S3 real**: mude `S3_ENDPOINT_*` pra bucket AWS. Código não muda.
- **Google OAuth**: registre Client ID no Google Cloud Console.
- **Módulo de relojoaria**: estrutura pronta, fora de escopo.
- **DynamoDB**: requer reescrita de `backend/app/models/*` + `backend/app/db/*`.

---

## Fora de escopo por ora

- Módulo de relojoaria / ordem de serviço
- Autoregistro de usuário e tela de gestão da allowlist
- Qualquer componente de IA (real ou mockado) — ver "Fase Futura" na `SPEC.md`
- Deploy em Lambda/API Gateway/DynamoDB/S3
