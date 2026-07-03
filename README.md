# Aureye — Cadastro de Clientes e Receitas Ópticas

Réplica moderna de um sistema originalmente feito em Oracle APEX para uma
óptica: cadastro de **clientes** e das **receitas ópticas** associadas a cada
um. Escopo atual: apenas o módulo óptico (cliente + receita) + autenticação.

> **Sem IA nesta fase.** O sistema é CRUD puro. A visão de copilot (busca em
> linguagem natural, identificação de cliente por imagem) está registrada
> apenas como intenção na [`SPEC.md`](./SPEC.md), sem código nem tela.

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
    routers/           # auth, clientes, receitas, uploads, dashboard
    storage.py         # MinIO/S3 (boto3) + presigned URLs
  tests/               # testes de schema/regra e de presign
frontend/
  src/
    api/               # client axios + endpoints
    context/           # AuthContext (sessão)
    components/        # Logo, Layout, ValidadeBadge, ProtectedRoute
    pages/             # login, dashboard, clientes, receitas
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

Documentação interativa (Swagger) em **http://localhost:8000/docs**.

---

## Fora de escopo por ora

- Módulo de relojoaria / ordem de serviço
- Autoregistro de usuário e tela de gestão da allowlist
- Qualquer componente de IA (real ou mockado) — ver "Fase Futura" na `SPEC.md`
- Deploy em Lambda/API Gateway/DynamoDB/S3
