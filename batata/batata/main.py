from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from database import (
    get_db, Usuario, Pergunta, Alternativa, Materia,
    Tentativa, Resposta
)
import random
import os
import json
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# SCHEMAS
# =========================
class UsuarioCreate(BaseModel):
    nome: str

class RespostaCreate(BaseModel):
    pergunta_id: int
    resposta: str
    tempo_gasto: Optional[int] = None
    tentativa_id: Optional[int] = None

class PontuacaoCreate(BaseModel):
    usuario_id: int
    pontuacao: int
    tempo_total: Optional[int] = None
    tentativa_id: Optional[int] = None

class TentativaCreate(BaseModel):
    usuario_id: int

class RespostaDetalhe(BaseModel):
    categoria: str
    dificuldade: Optional[str] = None
    enunciado: Optional[str] = None
    acertou: bool
    tempo_gasto: Optional[int] = None

class AnaliseIARequest(BaseModel):
    nome: str
    pontuacao: int
    total_perguntas: int
    acertos: int
    tempo_total: Optional[int] = None
    respostas: List[RespostaDetalhe] = []

# =========================
# ROTAS
# =========================
@app.get("/")
def home():
    return {"mensagem": "API do Quiz ODS 4 funcionando!"}

@app.post("/api/usuarios")
def criar_usuario(dados: UsuarioCreate, db: Session = Depends(get_db)):
    nome = dados.nome.strip()
    if not nome:
        raise HTTPException(status_code=400, detail={"erro": "Nome não pode ser vazio"})

    novo = Usuario(nome=nome, pontuacao=0)
    db.add(novo)
    db.commit()
    db.refresh(novo)

    return {"id": novo.id, "nome": novo.nome}

@app.get("/api/usuarios")
def listar_usuarios(db: Session = Depends(get_db)):
    usuarios = db.query(Usuario).all()
    # Ranking: mais pontos primeiro; em empate, menor tempo primeiro (sem tempo vai para o fim)
    usuarios.sort(key=lambda u: (-(u.pontuacao or 0), u.tempo_recorde if u.tempo_recorde is not None else float("inf")))
    return [
        {"id": u.id, "nome": u.nome, "pontuacao": u.pontuacao, "tempo_recorde": u.tempo_recorde}
        for u in usuarios
    ]

@app.post("/api/tentativas")
def iniciar_tentativa(dados: TentativaCreate, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.id == dados.usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail={"erro": "Usuário não encontrado"})

    tentativa = Tentativa(
        id_usuario=usuario.id,
        pontuacao_total=0,
        iniciado_em=datetime.now()
    )
    db.add(tentativa)
    db.commit()
    db.refresh(tentativa)

    return {"tentativa_id": tentativa.id, "usuario_id": usuario.id}

@app.get("/api/perguntas")
def listar_perguntas(db: Session = Depends(get_db)):
    materias = db.query(Materia).all()
    perguntas_selecionadas = []

    for materia in materias:
        perguntas = db.query(Pergunta).filter(Pergunta.id_materia == materia.id).all()
        if not perguntas:
            continue
        escolhidas = random.sample(perguntas, min(2, len(perguntas)))
        perguntas_selecionadas.extend(escolhidas)

    random.shuffle(perguntas_selecionadas)

    resultado = []
    for p in perguntas_selecionadas:
        alternativas = db.query(Alternativa).filter(Alternativa.id_pergunta == p.id).all()
        opcoes = [a.texto for a in alternativas]

        dificuldade_nome = p.dificuldade.nome if hasattr(p.dificuldade, "nome") else str(p.dificuldade)

        resultado.append({
            "id": p.id,
            "categoria": p.materia.nome if p.materia else "Geral",
            "enunciado": p.enunciado,
            "dificuldade": dificuldade_nome,
            "pontos": p.pontos,
            "opcoes": opcoes
        })

    return resultado

@app.post("/api/responder")
def responder(dados: RespostaCreate, db: Session = Depends(get_db)):
    pergunta = db.query(Pergunta).filter(Pergunta.id == dados.pergunta_id).first()
    if not pergunta:
        raise HTTPException(status_code=404, detail={"erro": "Pergunta não encontrada"})

    alternativa_escolhida = (
        db.query(Alternativa)
        .filter(Alternativa.id_pergunta == dados.pergunta_id, Alternativa.texto == dados.resposta.strip())
        .first()
    )

    alternativa_correta = (
        db.query(Alternativa)
        .filter(Alternativa.id_pergunta == dados.pergunta_id, Alternativa.correta == True)
        .first()
    )

    if not alternativa_correta:
        raise HTTPException(status_code=500, detail={"erro": "Alternativa correta não encontrada"})

    acertou = False
    pontos_ganhos = 0

    if alternativa_escolhida and alternativa_escolhida.correta:
        acertou = True
        pontos_ganhos = pergunta.pontos

    if dados.tentativa_id and alternativa_escolhida:
        tentativa = db.query(Tentativa).filter(Tentativa.id == dados.tentativa_id).first()
        if tentativa:
            nova_resposta = Resposta(
                id_tentativa=tentativa.id,
                id_pergunta=pergunta.id,
                id_alternativa=alternativa_escolhida.id,
                acertos=acertou,
                tempo_gasto=dados.tempo_gasto,
                respondido_em=datetime.now()
            )
            db.add(nova_resposta)

            if acertou:
                tentativa.pontuacao_total += pontos_ganhos

            db.commit()

    dificuldade_nome = pergunta.dificuldade.nome if hasattr(pergunta.dificuldade, "nome") else str(pergunta.dificuldade)

    return {
        "acertou": acertou,
        "correta": alternativa_correta.texto,
        "pontos": pontos_ganhos,
        "dificuldade": dificuldade_nome
    }

@app.post("/api/pontuacao")
def salvar_pontuacao(dados: PontuacaoCreate, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.id == dados.usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail={"erro": "Usuário não encontrado"})

    # Novo recorde: mais pontos, ou os mesmos pontos em menos tempo (desempate)
    if dados.pontuacao > (usuario.pontuacao or 0):
        usuario.pontuacao = dados.pontuacao
        usuario.tempo_recorde = dados.tempo_total
    elif (
        dados.pontuacao == usuario.pontuacao
        and dados.tempo_total is not None
        and (usuario.tempo_recorde is None or dados.tempo_total < usuario.tempo_recorde)
    ):
        usuario.tempo_recorde = dados.tempo_total

    if dados.tentativa_id:
        tentativa = db.query(Tentativa).filter(Tentativa.id == dados.tentativa_id).first()
        if tentativa:
            tentativa.pontuacao_total = dados.pontuacao
            tentativa.tempo_total = dados.tempo_total
            tentativa.finalizado_em = datetime.now()

    db.commit()
    db.refresh(usuario)

    return {"id": usuario.id, "nome": usuario.nome, "pontuacao": usuario.pontuacao, "tempo_recorde": usuario.tempo_recorde}

# =========================
# ANÁLISE COM IA (GROQ)
# =========================
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def montar_prompt_analise(dados: AnaliseIARequest) -> str:
    linhas = []
    for i, r in enumerate(dados.respostas, start=1):
        status = "ACERTOU" if r.acertou else "ERROU"
        tempo = f"{r.tempo_gasto}s" if r.tempo_gasto is not None else "?"
        linhas.append(
            f"{i}. [{r.categoria} | {r.dificuldade or '-'}] {status} em {tempo} — {(r.enunciado or '')[:140]}"
        )
    detalhe = "\n".join(linhas) if linhas else "(sem detalhes por questão)"

    media = ""
    if dados.tempo_total and dados.total_perguntas:
        media = f"- Tempo total: {dados.tempo_total}s (média de {dados.tempo_total // dados.total_perguntas}s por questão)\n"

    return f"""Atue como um tutor acadêmico especialista em preparação para exames de alta performance.

Analise o desempenho REAL do aluno abaixo (use somente os dados informados, não invente questões, acertos ou tempos).
Seu objetivo é estruturar um feedback detalhado combinando três metodologias de Prompt Engineering: Zero-Shot, Few-Shot e Chain-of-Thought (CoT).

DADOS DO ALUNO
- Nome: {dados.nome}
- Acertos: {dados.acertos} de {dados.total_perguntas}
- Pontuação: {dados.pontuacao}
{media}
Resultado questão por questão:
{detalhe}

Meta de velocidade: reduzir o tempo por questão para cerca de 2 minutos (120s) sem perder precisão.

Escreva o campo "relatorio" em texto simples (sem markdown, sem asteriscos), seguindo rigorosamente esta estrutura:

PARTE 1: CHAIN-OF-THOUGHT (CADEIA DE PENSAMENTO)
Para CADA questão ERRADA, mostre o passo a passo lógico:
1. Raciocínio inicial e interpretação do comando.
2. Pegadinhas e distratores.
3. Resolução passo a passo até a alternativa correta.
4. Causa raiz do erro (e, se o tempo gasto foi alto, por que demorou).
Se o aluno acertou tudo, diga isso e explique brevemente o raciocínio das questões de maior dificuldade.

PARTE 2: FEW-SHOT (EXEMPLOS PRÁTICOS)
Para cada questão errada, no formato:
Exemplo A (Diagnóstico e Plano de Estudo):
 - Causa provável do erro: ...
 - O que estudar: ...
 - Como estudar: ...
Exemplo B (Estratégia de Velocidade):
 - Técnica de leitura/atalho: ...
 - Ação prática para resolver em menos de 2 minutos: ...

PARTE 3: ANÁLISE DIRETA E PLANO GERAL DE VELOCIDADE (ZERO-SHOT)
1. Resumo dos tópicos teóricos que o aluno precisa revisar imediatamente.
2. Protocolo de agilidade (leitura, descarte de alternativas e gestão de tempo por bloco) para chegar a 2 minutos por questão.

Regras dos demais campos:
- "nivel" deve ser exatamente: "Iniciante", "Intermediário" ou "Avançado".
- "ponto_forte" e "area_melhorar": curtos (máx. 4 palavras), baseados nas matérias reais, ex.: "Matemática".
- "resumo": 2 a 3 frases motivadoras falando com o aluno pelo nome.
- "plano": exatamente 3 ações práticas e específicas.
- Português do Brasil, linguagem adequada a estudantes.

Responda SOMENTE com um JSON válido, sem texto fora dele:
{{"titulo": "...", "nivel": "...", "ponto_forte": "...", "area_melhorar": "...", "resumo": "...", "plano": ["...", "...", "..."], "relatorio": "..."}}
"""


@app.post("/api/analise-ia")
def gerar_analise_ia(dados: AnaliseIARequest):
    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": "Você é um tutor acadêmico de alta performance. Responda sempre apenas com JSON válido."},
                {"role": "user", "content": montar_prompt_analise(dados)}
            ],
            temperature=0.7,
            max_tokens=6000,
            reasoning_effort="low",
            response_format={"type": "json_object"}
        )

        texto = completion.choices[0].message.content or ""
        analise = json.loads(texto)

        for campo in ("titulo", "nivel", "ponto_forte", "area_melhorar", "resumo", "plano", "relatorio"):
            if campo not in analise:
                raise ValueError(f"IA não retornou o campo '{campo}'")

        return {"analise": analise}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na IA: {str(e)}")