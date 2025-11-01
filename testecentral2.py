import streamlit as st
import pandas as pd
import json, os
from datetime import date
from PIL import Image

# ==============================
# CONFIGURAÇÃO
# ==============================
st.set_page_config(
    page_title="Central do Barça - Dados e Estatísticas",
    page_icon="⚽",
    layout="wide"
)

# ==============================
# LOGO (CORRIGIDA)
# ==============================
LOGO_PATH = "barca_logo.png"

col1, col2 = st.columns([1, 6])
with col1:
    if os.path.exists(LOGO_PATH):
        logo = Image.open(LOGO_PATH).convert("RGBA")
        # força fundo transparente (remove artefato verde)
        datas = logo.getdata()
        nova = []
        for item in datas:
            if item[1] > 200 and item[0] < 60:  # se for verde, remove
                nova.append((255, 255, 255, 0))
            else:
                nova.append(item)
        logo.putdata(nova)
        st.image(logo, use_container_width=True)
    else:
        st.warning("Logo não encontrada.")
with col2:
    st.markdown(
        "<h1 style='color:orange; font-weight:700;'>Central do Barça - Dados e Estatísticas</h1>",
        unsafe_allow_html=True
    )
st.markdown("---")

# ==============================
# BANCO DE DADOS
# ==============================
DB_PATH = "database.json"
if not os.path.exists(DB_PATH):
    db = {"jogadores": [], "rodadas": []}
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
else:
    with open(DB_PATH, "r", encoding="utf-8") as f:
        db = json.load(f)

def salvar_db():
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

# ==============================
# FUNÇÕES
# ==============================
def pontuacao_total(j):
    return (j.get("craques", 0) * 100 +
            j.get("artilheiro", 0) * 90 +
            j.get("assistencias", 0) * 80 +
            j.get("defensor", 0) * 60 +
            j.get("goleiro", 0) * 50 +
            j.get("coringa", 0) * 40 +
            j.get("capitao", 0) * 30)

def atualizar_totais():
    for j in db["jogadores"]:
        j["total"] = pontuacao_total(j)
    salvar_db()

# ==============================
# PÁGINAS
# ==============================
def page_dashboard():
    st.subheader("🏆 Dashboard — Visão Geral")
    if not db["jogadores"]:
        st.info("Nenhum jogador cadastrado ainda.")
        return

    df = pd.DataFrame(db["jogadores"])
    if "nome" not in df.columns:
        st.warning("Banco de dados inválido — recarregue ou cadastre novamente.")
        return

    df.fillna(0, inplace=True)
    atualizar_totais()

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("### ⚽ Artilharia")
        st.dataframe(df[["nome", "gols"]].sort_values(by="gols", ascending=False).head(10), hide_index=True)
    with c2:
        st.markdown("### 🎯 Assistências")
        st.dataframe(df[["nome", "assistencias"]].sort_values(by="assistencias", ascending=False).head(10), hide_index=True)
    with c3:
        st.markdown("### ⭐ Craque do Barça")
        st.dataframe(df[["nome", "total"]].sort_values(by="total", ascending=False).head(10), hide_index=True)

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
        if st.button("💾 Salvar"):
            db["jogadores"] = edit.to_dict(orient="records")
            salvar_db()
            st.success("Salvo com sucesso!")
    else:
        st.info("Nenhum jogador cadastrado ainda.")

def page_rodadas():
    st.subheader("📅 Registrar Rodada")
    data_r = st.date_input("Data", value=date.today())

    if not db["jogadores"]:
        st.warning("Cadastre jogadores antes.")
        return

    nomes = [j["nome"] for j in db["jogadores"]]
    jogadores_sel = st.multiselect("Jogadores", nomes)

    rodada = []
    for n in jogadores_sel:
        c1, c2, c3 = st.columns(3)
        with c1: g = st.number_input(f"Gols ({n})", min_value=0, step=1)
        with c2: a = st.number_input(f"Assistências ({n})", min_value=0, step=1)
        with c3: c = st.checkbox(f"Craque ({n})")
        rodada.append({"nome": n, "gols": g, "assist": a, "craque": int(c)})

    if st.button("Salvar rodada"):
        db["rodadas"].append({"data": str(data_r), "dados": rodada})
        salvar_db()
        st.success("Rodada salva com sucesso!")

def page_admin():
    st.subheader("⚙️ Administração")
    if st.button("Zerar banco ⚠️"):
        db.update({"jogadores": [], "rodadas": []})
        salvar_db()
        st.success("Banco zerado!")
    st.download_button("📤 Baixar database.json", json.dumps(db, indent=2), "database.json")

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
    escolha = st.radio("Navegar", paginas.keys())

paginas[escolha]()
