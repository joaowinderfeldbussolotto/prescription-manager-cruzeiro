"""Tools do Agente — cada uma é uma capability real sobre o banco.

O LLM decide QUANDO chamar cada tool; a INSTRUÇÃO de uso (quando usar, quais
campos são obrigatórios, protocolo de desambiguação, formato de link) vive na
docstring de cada função — é ela que vira a `description` da tool exposta ao
modelo (decisão deliberada: ver app/agent/prompts/system_prompt.md, que fica
propositalmente magro).

Nenhuma tool deixa exceção subir: todo erro de validação/banco vira uma
string de retorno explicando o problema, pra não derrubar o turno inteiro do
agente por causa de um dado mal formatado.
"""
from __future__ import annotations

from langchain_core.tools import tool
from pydantic import ValidationError

from app.db.mongo import get_db
from app.models import cliente as cliente_repo
from app.models import receita as receita_repo
from app.schemas.cliente import ClienteCreate, ClienteUpdate


async def _buscar_clientes(termo: str, limit: int = 10) -> list[dict]:
    db = get_db()
    items, _total = await cliente_repo.list_paginated(db, busca=termo, page=1, limit=limit)
    return items


def _formatar_clientes(items: list[dict]) -> str:
    return "\n".join(
        f"- {c['nome']} (id: {c['id']}, telefone: {c.get('telefone') or '—'})" for c in items
    )


@tool
async def cadastrar_cliente(
    nome: str,
    telefone: str,
    cpf: str | None = None,
    email: str | None = None,
    data_nascimento: str | None = None,
    endereco: str | None = None,
) -> str:
    """Cadastra um cliente NOVO na base de dados da ótica.

    Use somente para cliente que ainda não existe. Se o cliente já existir e
    o usuário quiser mudar um dado dele, use `editar_cliente` em vez desta.

    Argumentos:
    - nome, telefone: OBRIGATÓRIOS. Se o usuário não informar um dos dois,
      pergunte antes de chamar esta ferramenta.
    - cpf: opcional, formato "000.000.000-00" (com ou sem pontuação).
    - email, endereco: texto livre, opcionais.
    - data_nascimento: opcional, formato "AAAA-MM-DD".

    IMPORTANTE: preencha cada campo opcional SOMENTE se o usuário informou
    esse dado explicitamente na conversa — nunca invente CPF, e-mail,
    endereço ou data de nascimento.

    Ao ter sucesso, inclua na sua resposta final ao usuário um link markdown
    no formato [NOME_DO_CLIENTE](/clientes/ID_RETORNADO), além de mencionar
    os dados em texto simples (o link é um bônus, não o único jeito de
    confirmar a informação).
    """
    try:
        dados = ClienteCreate(
            nome=nome,
            telefone=telefone,
            cpf=cpf,
            email=email,
            data_nascimento=data_nascimento or None,
            endereco=endereco,
        ).model_dump()
    except ValidationError as exc:
        return f"Não consegui cadastrar: dados inválidos ({exc}). Peça pro usuário corrigir e tente de novo."

    try:
        db = get_db()
        criado = await cliente_repo.create(db, dados)
    except Exception as exc:  # noqa: BLE001 - nunca deixa a tool derrubar o turno do agente
        return f"Erro ao cadastrar o cliente: {exc}"

    return (
        f"Cliente cadastrado com sucesso: {criado['nome']} "
        f"(id: {criado['id']}, telefone: {criado['telefone']})."
    )


@tool
async def editar_cliente(
    busca: str,
    novo_telefone: str | None = None,
    novo_email: str | None = None,
    novo_cpf: str | None = None,
    novo_endereco: str | None = None,
    nova_data_nascimento: str | None = None,
) -> str:
    """Edita dados de um cliente JÁ CADASTRADO.

    Use quando o usuário quiser atualizar, corrigir ou mudar algum dado de
    um cliente existente. Para cliente novo, use `cadastrar_cliente`.

    Argumentos:
    - busca: nome (completo ou parcial) ou telefone do cliente. OBRIGATÓRIO.
    - novo_telefone, novo_email, novo_cpf, novo_endereco: informe SÓ os
      campos que o usuário efetivamente quer mudar; omita os demais.
    - nova_data_nascimento: formato "AAAA-MM-DD".

    Protocolo obrigatório de desambiguação: se `busca` encontrar MAIS DE UM
    cliente, NÃO edite nada — responda listando os candidatos encontrados
    (nome, telefone e um link markdown [Nome](/clientes/ID) pra cada um) e
    peça pro usuário confirmar qual deles antes de chamar esta ferramenta de
    novo. Se não encontrar nenhum, diga isso claramente ao usuário.
    """
    try:
        encontrados = await _buscar_clientes(busca, limit=5)
    except Exception as exc:  # noqa: BLE001
        return f"Erro ao buscar cliente: {exc}"

    if not encontrados:
        return f'Não encontrei nenhum cliente correspondente a "{busca}".'
    if len(encontrados) > 1:
        return (
            f'Encontrei {len(encontrados)} clientes para "{busca}" — preciso que '
            f"o usuário diga qual deles antes de editar:\n{_formatar_clientes(encontrados)}"
        )

    raw = {
        "telefone": novo_telefone,
        "email": novo_email,
        "cpf": novo_cpf,
        "endereco": novo_endereco,
        "data_nascimento": nova_data_nascimento,
    }
    raw = {k: v for k, v in raw.items() if v is not None}
    if not raw:
        return "Nenhum campo novo foi informado pra atualizar — pergunte ao usuário o que ele quer mudar."

    try:
        mudancas = ClienteUpdate(**raw).model_dump(exclude_unset=True)
    except ValidationError as exc:
        return f"Não consegui atualizar: dados inválidos ({exc})."

    try:
        alvo = encontrados[0]
        db = get_db()
        atualizado = await cliente_repo.update(db, alvo["id"], mudancas)
    except Exception as exc:  # noqa: BLE001
        return f"Erro ao atualizar o cliente: {exc}"

    return (
        f"Cliente atualizado com sucesso: {atualizado['nome']} "
        f"(id: {atualizado['id']}, telefone: {atualizado.get('telefone') or '—'})."
    )


@tool
async def buscar_cliente(termo: str) -> str:
    """Busca clientes cadastrados por nome ou telefone (busca parcial, sem
    diferenciar maiúsculas/minúsculas).

    Use quando o usuário quiser encontrar, ver ou consultar um cliente, sem
    pedir explicitamente pra editar (`editar_cliente`) ou ver as receitas
    dele (`buscar_receitas_cliente`).

    Pode retornar mais de um cliente se o termo for comum. Sempre cite nome,
    telefone e um link markdown [Nome](/clientes/ID) de CADA cliente
    retornado na sua resposta; nunca escolha um sozinho quando houver mais
    de um resultado — deixe o usuário decidir qual é.
    """
    try:
        encontrados = await _buscar_clientes(termo, limit=10)
    except Exception as exc:  # noqa: BLE001
        return f"Erro ao buscar cliente: {exc}"

    if not encontrados:
        return f'Não encontrei nenhum cliente correspondente a "{termo}".'
    return f'Encontrei {len(encontrados)} cliente(s) para "{termo}":\n{_formatar_clientes(encontrados)}'


@tool
async def buscar_receitas_cliente(termo: str) -> str:
    """Busca o histórico de receitas ópticas de um cliente (localiza o
    cliente por nome/telefone e lista as receitas dele).

    Use quando o usuário perguntar sobre receitas, graus, validade ou
    histórico óptico de um cliente específico.

    Protocolo de desambiguação: se a busca encontrar mais de um cliente,
    NÃO escolha um sozinho — liste os candidatos (nome, telefone, link
    markdown [Nome](/clientes/ID)) e peça pro usuário especificar qual deles
    antes de listar receitas.
    """
    try:
        encontrados = await _buscar_clientes(termo, limit=5)
    except Exception as exc:  # noqa: BLE001
        return f"Erro ao buscar cliente: {exc}"

    if not encontrados:
        return f'Não encontrei nenhum cliente correspondente a "{termo}".'
    if len(encontrados) > 1:
        return (
            f'Encontrei {len(encontrados)} clientes para "{termo}" — preciso que '
            f"o usuário diga qual deles:\n{_formatar_clientes(encontrados)}"
        )

    cliente = encontrados[0]
    try:
        db = get_db()
        receitas = await receita_repo.list_by_cliente(db, cliente["id"])
    except Exception as exc:  # noqa: BLE001
        return f"Erro ao buscar receitas: {exc}"

    if not receitas:
        return (
            f"{cliente['nome']} ([{cliente['nome']}](/clientes/{cliente['id']})) "
            "não tem nenhuma receita cadastrada ainda."
        )

    linhas = [
        f"- receita {r['id']}: emitida em {r['data_emissao']}, validade {r['validade']}, "
        f"médico: {r.get('medico_nome') or '—'}"
        for r in receitas
    ]
    return (
        f"{cliente['nome']} ([{cliente['nome']}](/clientes/{cliente['id']})) "
        f"tem {len(receitas)} receita(s):\n" + "\n".join(linhas)
    )


@tool
async def preparar_receita(termo: str) -> str:
    """Prepara o cadastro de uma receita NOVA para um cliente já existente.

    Use quando o usuário pedir para cadastrar, criar ou registrar uma
    receita para um cliente.

    Esta ferramenta NÃO cria a receita — apenas localiza o cliente e devolve
    o link do formulário. Toda receita exige uma IMAGEM anexada manualmente
    pelo atendente; não é possível criar uma receita só por texto/conversa.
    Sempre explique isso ao usuário e inclua o link markdown
    [Nova receita para NOME](/clientes/ID/receitas/nova) pra ele abrir o
    formulário certo.

    Protocolo de desambiguação: se houver mais de um cliente com esse nome,
    liste os candidatos e peça pro usuário confirmar antes de dar o link.
    """
    try:
        encontrados = await _buscar_clientes(termo, limit=5)
    except Exception as exc:  # noqa: BLE001
        return f"Erro ao buscar cliente: {exc}"

    if not encontrados:
        return f'Não encontrei nenhum cliente correspondente a "{termo}".'
    if len(encontrados) > 1:
        return (
            f'Encontrei {len(encontrados)} clientes para "{termo}" — preciso que '
            f"o usuário diga qual deles:\n{_formatar_clientes(encontrados)}"
        )

    cliente = encontrados[0]
    return (
        f"Cliente encontrado: {cliente['nome']} (id: {cliente['id']}). Toda receita "
        "exige uma imagem anexada manualmente — não é possível criar por aqui. "
        f"Link do formulário: [Nova receita para {cliente['nome']}]"
        f"(/clientes/{cliente['id']}/receitas/nova)"
    )


TOOLS = [
    cadastrar_cliente,
    editar_cliente,
    buscar_cliente,
    buscar_receitas_cliente,
    preparar_receita,
]
