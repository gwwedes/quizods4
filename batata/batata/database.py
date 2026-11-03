from sqlalchemy import (
    inspect, text, create_engine, Column, Integer, String, Text,
    Boolean, ForeignKey, DateTime
)
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from dotenv import load_dotenv
from datetime import datetime
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise Exception("DATABASE_URL não encontrada. Verifique o arquivo .env")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    pontuacao = Column(Integer, default=0)
    tempo_recorde = Column(Integer, nullable=True)  # segundos da partida do recorde (desempate)
    criado_em = Column(DateTime, default=datetime.now)

    tentativas = relationship("Tentativa", back_populates="usuario")


class Materia(Base):
    __tablename__ = "materias"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(50), unique=True, nullable=False)

    perguntas = relationship("Pergunta", back_populates="materia")


class Dificuldade(Base):
    __tablename__ = "dificuldades"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(20), unique=True, nullable=False)

    perguntas = relationship("Pergunta", back_populates="dificuldade")


class Pergunta(Base):
    __tablename__ = "perguntas"

    id = Column(Integer, primary_key=True, index=True)
    id_materia = Column(Integer, ForeignKey("materias.id"), nullable=False)
    id_dificuldade = Column(Integer, ForeignKey("dificuldades.id"), nullable=False)
    enunciado = Column(Text, nullable=False)
    pontos = Column(Integer, nullable=False)

    materia = relationship("Materia", back_populates="perguntas")
    dificuldade = relationship("Dificuldade", back_populates="perguntas")
    alternativas = relationship("Alternativa", back_populates="pergunta")


class Alternativa(Base):
    __tablename__ = "alternativas"

    id = Column(Integer, primary_key=True, index=True)
    id_pergunta = Column(Integer, ForeignKey("perguntas.id"), nullable=False)
    texto = Column(Text, nullable=False)
    correta = Column(Boolean, default=False)

    pergunta = relationship("Pergunta", back_populates="alternativas")


class Tentativa(Base):
    __tablename__ = "tentativas"

    id = Column(Integer, primary_key=True, index=True)
    id_usuario = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    pontuacao_total = Column(Integer, default=0)
    tempo_total = Column(Integer, nullable=True)
    iniciado_em = Column(DateTime, default=datetime.now)
    finalizado_em = Column(DateTime, nullable=True)

    usuario = relationship("Usuario", back_populates="tentativas")
    respostas = relationship("Resposta", back_populates="tentativa")


class Resposta(Base):
    __tablename__ = "respostas"

    id = Column(Integer, primary_key=True, index=True)
    id_tentativa = Column(Integer, ForeignKey("tentativas.id"), nullable=False)
    id_pergunta = Column(Integer, ForeignKey("perguntas.id"), nullable=False)
    id_alternativa = Column(Integer, ForeignKey("alternativas.id"), nullable=False)
    acertos = Column(Boolean, nullable=False)
    tempo_gasto = Column(Integer, nullable=True)
    respondido_em = Column(DateTime, default=datetime.now)

    tentativa = relationship("Tentativa", back_populates="respostas")


def garantir_colunas():
    """Adiciona colunas novas em tabelas já existentes (migração simples)."""
    insp = inspect(engine)
    if "usuarios" in insp.get_table_names():
        colunas = [c["name"] for c in insp.get_columns("usuarios")]
        if "tempo_recorde" not in colunas:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE usuarios ADD COLUMN tempo_recorde INTEGER"))


garantir_colunas()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()