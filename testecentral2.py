import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, date, timedelta

# ==============================
# CONFIGURAÇÃO INICIAL
# ==============================
st.set_page_config(
    page_title="Central do Barça - Dados e Estatísticas",
    page_icon="⚽",
    layout="wide"
)

# ==============================
# LOGO DO CLUBE
# ==============================
LOGO_PATH = "barca_logo.png"

col1, col2 = st.columns([1, 6])
with col1:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, use_column_width=True)
    else:
        st.warning("Logo não encontrada.")
with col2:
    st.markdown(
        "<h1 style='color:orange; font-weight:700;'>Central do Barça - Dados e Estatísticas</h1>",
        unsafe_allow_html=True
    )
st.markdown("---")

# ==============================
# BANCO DE DADOS LOCAL
# ==============================
DB_PATH = "database.json"

if not os.path.exists(DB_PATH):
    st.warning("Nenhum banco encontrado. Criando novo database.json...")
    db = {"jogadores": [], "rodadas": [], "ranking": {}, "puskas": [], "quinteto": []}
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
else:
    with open(DB_PATH, "r", encoding="utf-8") as f:
        db = json.load(f)

def salvar_db():
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

# ==============================
# FUNÇÕES AUXILIARES
# ==============================
def pontuacao_total(j):
    """Calcula pontuação do ranking de craque"""
    pts = (j.get("craques", 0) * 100 +
           j.get("artilheiro", 0) * 90 +
           j.get("assistencias", 0) * 80 +
           j.get("defensor", 0) * 60 +
           j.get("goleiro", 0) * 50 +
           j.get("coringa", 0) * 40 +
           j.get("capitao", 0) * 30)
    return pts

def atualizar_pontuacoes():
    for j in db["jogadores"]:
        j["total"] = pontuacao_total(j)
    salvar_db()

# ==============================
# PÁGINAS
# ==============================

def page_dashboard():
    st.subheader("🏆 Dashboard — Visão Geral")
    atualizar_pontuacoes()

    df = pd.DataFrame(db["jogadores"])
    if df.empty:
        st.info("Nenhum jogador cadastrado ainda.")
        return

    df = df.sort_values(by="total", ascending=False)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### ⚽ Artilharia")
        st.dataframe(df[["nome", "gols"]].sort_values(by="gols", ascending=False).head(10), hide_index=True)

    with col2:
        st.markdown("### 🎯 Assistências")
        st.dataframe(df[["nome", "assistencias"]].sort_values(by="assistencias", ascending=False).head(10), hide_index=True)

    with col3:
        st.markdown("### ⭐ Craque do Barça (ranking geral)")
        st.dataframe(df[["nome", "total"]].head(10), hide_index=True)

def page_jogadores():
    st.subheader("👥 Gerenciar Jogadores")

    if st.button("➕ Adicionar linha"):
        db["jogadores"].append({
            "nome": "",
            "posicao": "",
            "gols": 0,
            "assistencias": 0,
            "craques": 0,
            "artilheiro": 0,
            "defensor": 0,
            "goleiro": 0,
            "coringa": 0,
            "capitao": 0,
            "total": 0
        })
        salvar_db()
        st.rerun()

    if db["jogadores"]:
        df = pd.DataFrame(db["jogadores"])
        edit = st.data_editor(df, num_rows="dynamic", key="edit_jogadores")
        if st.button("💾 Salvar alterações"):
            db["jogadores"] = edit.to_dict(orient="records")
            salvar_db()
            st.success("Jogadores atualizados com sucesso!")
    else:
        st.info("Nenhum jogador cadastrado ainda.")

def page_rodadas():
    st.subheader("📅 Registrar Nova Rodada")

    data_rodada = st.date_input("Data da Rodada", value=date.today())

    st.write("### Jogadores da Rodada")
    if not db["jogadores"]:
        st.warning("Cadastre jogadores antes de registrar rodadas.")
        return

    nomes = [j["nome"] for j in db["jogadores"]]
    jogadores_sel = st.multiselect("Selecione os jogadores que participaram", nomes)

    rodada_data = []
    for nome in jogadores_sel:
        col1, col2, col3 = st.columns(3)
        with col1:
            gols = st.number_input(f"Gols ({nome})", min_value=0, step=1)
        with col2:
            assist = st.number_input(f"Assistências ({nome})", min_value=0, step=1)
        with col3:
            craque = st.checkbox(f"Craque ({nome})")

        rodada_data.append({"nome": nome, "gols": gols, "assist": assist, "craque": int(craque)})

    if st.button("Salvar Rodada"):
        nova = {"data": str(data_rodada), "dados": rodada_data}
        db["rodadas"].append(nova)
        salvar_db()
        st.success("Rodada registrada com sucesso!")

def page_admin():
    st.subheader("🛠️ Administração")

    if st.button("Zerar banco de dados ⚠️"):
        st.warning("Isso apagará tudo permanentemente.")
        db.clear()
        db.update({"jogadores": [], "rodadas": [], "ranking": {}, "puskas": [], "quinteto": []})
        salvar_db()
        st.success("Banco de dados zerado.")

    if st.button("📤 Exportar banco JSON"):
        st.download_button("Baixar database.json", json.dumps(db, indent=2), "database.json")

# ==============================
# NAVEGAÇÃO
# ==============================
paginas = {
    "Dashboard": page_dashboard,
    "Jogadores": page_jogadores,
    "Rodadas": page_rodadas,
    "Admin": page_admin
}

with st.sidebar:
    st.header("Central do Barça ⚽")
    escolha = st.radio("Navegar", list(paginas.keys()))

paginas[escolha]()
