# SPEC.md — Sistema de Cadastro de Clientes e Receitas Ópticas

## Contexto

Réplica moderna de um sistema construído originalmente em Oracle APEX para uma
óptica/relojoaria: cadastro de clientes e das receitas ópticas associadas a
cada um. Escopo atual: **apenas o módulo óptico** (cliente + receita).
Relojoaria fica fora por ora.

**Escopo atual:** CRUD de clientes e receitas + autenticação, mais dois
componentes de "IA":

- **Extração de dados da receita a partir da imagem** — 100% mock (ver
  "Extração (mock) de dados da receita" nos Endpoints); todo ponto onde IA
  real atuaria aqui usa lógica determinística, claramente comentada no
  código (`# MOCK: substituir por chamada de IA real`).
- **Agente** — chat em linguagem natural que cadastra/edita/busca clientes
  (ver "Agente" nos Endpoints). Este é um **agente LLM real** (LangChain +
  Groq, tools sobre o banco) — não é mock.

Ambos ficam atrás de feature toggle. A identificação de cliente por imagem
segue registrada só como decisão anotada na seção "Fase Futura" no final
deste arquivo, sem tela nem endpoint ainda.

---

## Identidade Visual

**Logo:** olho estilizado, traço fino, gradiente dourado (tons de amarelo
ouro pra âmbar), fundo transparente/branco. Estética minimalista, mais
próxima de joalheria/produto premium do que de clínica genérica.

**Implicações pro design da UI:**
- Paleta primária em tons de dourado/âmbar (aprox. `#D4AF37` → `#B8860B` como
  faixa de gradiente), não azul genérico de SaaS
- Traço fino, bastante espaço em branco, sem elementos pesados ou sombras
  fortes — o logo pede um visual clean, não corporativo denso
- Tipografia deve acompanhar esse tom mais refinado (evitar fontes muito
  "técnicas"/monoespaçadas na UI principal, reservar isso pra área de dados
  brutos se houver)
- Nome do repositório/produto ainda em aberto — candidatos discutidos:
  `aureye`, `clarion`, `optic-records` (mais neutro/técnico)

Isso vale como referência quando a implementação do frontend chegar na parte
de tema/design tokens — não é escopo de backend, só contexto pra não sair um
visual genérico de dashboard.

---

- **Backend:** FastAPI (Python)
- **Frontend:** React + Vite
- **Banco:** MongoDB (local, via Docker) — futuro: migração para DynamoDB
- **Storage de imagem:** MinIO (local, via Docker, API compatível com S3) —
  futuro: migração para S3 real
- **Orquestração local:** Docker Compose

**Nota honesta sobre as duas migrações futuras — elas não são equivalentes:**

- **MinIO → S3** é quase transparente. MinIO implementa a API do S3, então o
  mesmo client `boto3` funciona nos dois; muda só `endpoint_url` e credenciais
  via variável de ambiente. O código de presigned URL não muda.
- **MongoDB → DynamoDB não é drop-in.** MongoDB é um banco de documentos com
  queries flexíveis (filtro por qualquer campo, `$regex`, agregação). DynamoDB
  é key-value/single-table, otimizado pra acesso por chave conhecida — queries
  livres (ex: buscar cliente por nome parcial, ou filtrar receitas por
  intervalo de validade sem índice dedicado) exigem redesenho de modelagem
  (GSIs, chaves compostas) quando essa migração acontecer. Não é só troca de
  driver; é repensar os padrões de acesso. Vale documentar isso no README
  como decisão consciente, não como detalhe menor.

### Docker Compose (desenvolvimento local)

Serviços:
- `mongodb` — imagem oficial `mongo`, porta `27017`, volume nomeado pra
  persistência entre restarts
- `minio` — imagem `minio/minio`, portas `9000` (API) e `9001` (console web),
  volume nomeado, credenciais via env (`MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD`)
- `backend` — build do FastAPI, depende de `mongodb` e `minio` (`depends_on`),
  variáveis de ambiente com connection string do Mongo e endpoint/credenciais
  do MinIO
- `frontend` — build do Vite (dev server ou build servido por nginx),
  depende de `backend`

Um script/comando de inicialização (rodado pelo próprio backend no startup,
ou um serviço `init` no compose) precisa garantir que o bucket do MinIO exista
antes do primeiro upload — MinIO não cria bucket automaticamente.

---

## Modelos de Dados

> Coleções MongoDB. `id` é o `_id` nativo do Mongo (ObjectId), serializado
> como string na API — evita expor ou depender do formato interno do Mongo
> no frontend.

### Usuario

| Campo | Tipo | Obrigatório | Observação |
|---|---|---|---|
| id | string (ObjectId) | auto | |
| email | string | sim | índice único; é a chave da allowlist |
| nome | string | não | preenchido a partir do perfil Google no primeiro login |
| ativo | bool | sim | default `true`; setar `false` revoga acesso sem apagar o registro |
| role | string | sim | enum: `admin`, `atendente` — default `atendente` |
| data_criacao | datetime | auto | |
| ultimo_login | datetime | não | atualizado a cada login bem-sucedido |

> Cadastro de usuário nesta fase é manual (inserido direto no banco ou por
> uma tela simples de admin) — não há autoregistro. Alguém com acesso ao
> banco decide quem entra na allowlist antes da pessoa tentar logar.

### Cliente

| Campo | Tipo | Obrigatório | Observação |
|---|---|---|---|
| id | string (ObjectId) | auto | |
| nome | string | sim | |
| cpf | string | não | validação de formato, não de dígito verificador |
| telefone | string | sim | |
| email | string | não | |
| data_nascimento | date | não | |
| endereco | string | não | campo único de texto livre, sem CEP estruturado |
| data_cadastro | datetime | auto | |

### Receita

| Campo | Tipo | Obrigatório | Observação |
|---|---|---|---|
| id | string (ObjectId) | auto | |
| cliente_id | string (ref) | sim | índice pra listar receitas por cliente |
| data_emissao | date | sim | |
| validade | date | sim | default = data_emissao + 12 meses, editável |
| medico_nome | string | não | |
| medico_crm | string | não | |
| od_esferico | decimal | não | ex: -2.50 |
| od_cilindrico | decimal | não | |
| od_eixo | int (0-180) | não | |
| od_adicao | decimal | não | presbiopia |
| oe_esferico | decimal | não | |
| oe_cilindrico | decimal | não | |
| oe_eixo | int (0-180) | não | |
| oe_adicao | decimal | não | |
| dp | decimal | não | distância pupilar única |
| dp_longe | decimal | não | opcional, se a receita especificar por perto/longe |
| dp_perto | decimal | não | |
| observacoes | text | não | |
| imagem_key | string | não | chave do objeto no MinIO/S3 |
| data_cadastro | datetime | auto | |

> Nenhum campo de grau é obrigatório porque uma receita pode registrar só um
> olho, ou vir sem adição (paciente sem presbiopia). Validação de negócio
> (ex: "pelo menos um esférico deve estar preenchido") fica no backend.

---

## Endpoints

### Autenticação
- `POST /auth/google` — recebe `{ id_token }` (token do Google Identity
  Services no frontend). Backend valida a assinatura contra as chaves
  públicas do Google, extrai `email` + `email_verified`. Se `email_verified`
  for `false` → 401. Busca o email na coleção `usuarios`:
  - Não existe ou `ativo = false` → 403 (`"Email não autorizado"`)
  - Existe e `ativo = true` → atualiza `ultimo_login`, emite sessão própria
    (JWT em cookie `httpOnly`, `secure`, `sameSite=lax`) e retorna dados
    básicos do usuário (`nome`, `email`, `role`)
- `GET /auth/me` — retorna o usuário da sessão atual (a partir do cookie),
  401 se não autenticado
- `POST /auth/logout` — limpa o cookie de sessão

**Middleware de autorização:** toda rota de `/clientes` e `/receitas` exige
sessão válida (dependency do FastAPI que decodifica o cookie e injeta o
usuário atual). Rotas administrativas futuras (gerenciar allowlist) exigiriam
`role = admin` — fora do escopo desta entrega, mas a dependency já nasce
parametrizável por role pra não precisar refatorar depois.

### Clientes
- `POST /clientes` — cria cliente
- `GET /clientes?busca=&page=&limit=` — lista com busca por nome/telefone
- `GET /clientes/{id}` — detalhe do cliente, incluindo lista resumida de receitas (histórico)
- `PUT /clientes/{id}` — edita
- `DELETE /clientes/{id}` — remove (soft delete, se receitas vinculadas existirem)

### Receitas
- `POST /clientes/{cliente_id}/receitas` — cria receita para o cliente
- `GET /clientes/{cliente_id}/receitas` — lista receitas do cliente (timeline)
- `GET /receitas/{id}` — detalhe (dados + URL da imagem)
- `PUT /receitas/{id}` — edita
- `DELETE /receitas/{id}` — remove

### Upload
- `POST /uploads/presigned-url` — recebe `{ content_type }`, retorna
  `{ upload_url, key }`. Gerado via `boto3` apontando pro endpoint do MinIO
  (`endpoint_url` configurável por env — trocar pra S3 real no futuro é só
  mudar essa variável e as credenciais). Frontend faz PUT direto usando
  `upload_url`, depois envia `key` no create/update da receita.

### Extração (mock) de dados da receita
- `POST /receitas/extracao-ia` — recebe `{ imagem_key }` (de uma imagem já
  enviada via presigned URL), retorna `{ campos, mock, aviso }` com uma
  sugestão de preenchimento (OD/OE, DP, data de emissão, médico) pro
  frontend pré-preencher o formulário de receita. **100% mock nesta fase**
  (`# MOCK: substituir por chamada de IA real` em
  `app/schemas/extracao.py`) — nunca persiste nada, o atendente sempre
  revisa antes de salvar. Controlado por um feature toggle
  (`EXTRACAO_IA_ENABLED`, default ligado) que derruba o endpoint (404) e
  esconde o botão no frontend quando desligado.

### Agente (LLM real)
- `POST /agente/mensagem` — recebe `{ mensagem }`, retorna `{ resposta }`.
  **Agente real** via LangChain `create_agent`, modelo primário Groq
  `openai/gpt-oss-120b` (`init_chat_model`), com `ModelFallbackMiddleware`
  pra `openai/gpt-oss-20b` em caso de erro. Frontend aceita texto livre;
  chips de sugestão continuam existindo como atalhos.
  - **Tools bem definidas** (`app/agent/tools.py`), não uma query genérica:
    `cadastrar_cliente`, `editar_cliente`, `buscar_cliente`,
    `buscar_receitas_cliente`, `preparar_receita` — todas reusam
    `cliente_repo`/`receita_repo` (os mesmos repositórios de
    `routers/clientes.py`), batendo no banco de verdade. Busca ambígua por
    nome faz o agente listar todos os candidatos e perguntar, em vez de
    adivinhar.
  - **Instrução de uso na description de cada tool**, não no prompt — o
    prompt do sistema (`app/agent/prompts/system_prompt.md`, arquivo
    externo) carrega só identidade ("Assistente Virtual da Cruzeiro") e
    regras gerais (idioma, nunca inventar dado).
  - **Memória multi-turn** via checkpointer do LangGraph
    (`langgraph-checkpoint-mongodb`, `MongoDBSaver`), thread por usuário, com
    TTL pra expirar histórico antigo.
  - **Links**: cada tool instrui o modelo a incluir `[Nome](/clientes/ID)`
    na resposta quando relevante; o frontend faz o parse desse padrão
    markdown. A informação sempre aparece em texto simples também (o link é
    um bônus, não o único jeito de saber o resultado).
  - Controlado por feature toggle (`AGENTE_ENABLED`, default ligado) que
    derruba o endpoint (404) e esconde a aba no frontend quando desligado.
    Sem `GROQ_API_KEY` configurada, o endpoint também fica indisponível
    (404) mesmo com o toggle ligado.
  - **Limitações assumidas**: fallback só entre modelos Groq (não cobre
    queda do provedor inteiro); rate limit do tier grátis é baixo e
    tool-calling multi-step consome tokens rápido — erros viram resposta
    amigável no chat, não 500; sem botão de "nova conversa" ainda.

---

## Telas (Frontend)

0. **Login** — botão "Entrar com Google" (Google Identity Services), trata
   erro de "email não autorizado" com mensagem clara (não um erro genérico
   de servidor)
1. **Lista de clientes** — busca por nome/telefone, paginação, botão "novo cliente"
2. **Cadastro/edição de cliente** — formulário simples
3. **Detalhe do cliente** — dados do cliente + timeline de receitas (cards com
   data de emissão/validade, badge de "vencida"/"válida"/"vencendo em breve")
   + botão "nova receita"
4. **Cadastro/edição de receita** — formulário estruturado (OD/OE lado a
   lado), upload de imagem com preview, cálculo automático de validade
5. **Visualização de receita** — imagem ao lado dos dados (layout tipo
   "documento + metadados")
6. **Dashboard leve** (opcional, 3 cards) — total de clientes, receitas
   cadastradas no mês, receitas vencendo nos próximos 30 dias
7. **Agente** — chat em linguagem natural (texto livre + chips de sugestão),
   agente LLM real (LangChain + Groq); cadastra/edita/busca clientes de
   verdade, com links clicáveis embutidos na resposta

---

## Fora de escopo por ora

- Módulo de relojoaria / ordem de serviço
- Autoregistro de usuário e tela de gerenciamento da allowlist (cadastro de
  usuário é manual, direto no banco, por ora)
- Extração de dados de receita por imagem continua mock (ver "Extração
  (mock) de dados da receita" acima) — o Agente de chat já é real; ver
  "Fase Futura" pro que ainda não tem nem mock
- Deploy em Lambda/API Gateway/DynamoDB/S3 (Docker Compose local é suficiente
  por ora; migração AWS é próxima fase)

---

## Fase Futura (não implementada — apenas registro de intenção)

Fica registrado aqui pra não se perder a decisão, sem gerar código ou tela
nesta fase:

1. **Identificação de cliente por imagem** — upload de receita sem cliente
   pré-selecionado; modelo multimodal lê a imagem e chama uma tool de busca
   pra encontrar o cliente correspondente. Ainda sem contrato de API nem
   mock — fica pra quando essa fase entrar em planejamento de verdade.
2. **Botão de "nova conversa" no Agente** — hoje a memória do chat é um
   thread contínuo por usuário (com TTL), sem opção de reset manual.
