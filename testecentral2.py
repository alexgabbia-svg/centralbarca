# testecentral2_final_v2.py
# Central do Barça - final v2
# - Dashboard: top3 + categorias + puskas + melhor quinteto (editável/zerável)
# - Rankings editáveis a partir do Dashboard (formulário em massa)
# - Jogadores: editar nome e posição em massa (renomeia manual_totals)
# - Registrar rodada: multi-select + campos por jogador
# - Replaces experimental_rerun with st.rerun; uses timedelta for periods
# Requirements: streamlit, pandas, openpyxl

import streamlit as st
import pandas as pd
import json, os
from datetime import date, datetime, timedelta
from collections import defaultdict

# ---------------- Config ----------------
APP_TITLE = "Central do Barça — Dados e Estatísticas"
DATA_DIR = "central_data"
DB_FILE = os.path.join(DATA_DIR, "db.json")
ADMIN_PWD = "barca123"

os.makedirs(DATA_DIR, exist_ok=True)

WEIGHTS = {
    "craque": 100,
    "artilheiro": 90,
    "assistencia": 80,
    "defensor": 60,
    "goleiro": 50,
    "coringa": 40,
    "capitao": 30
}

ACCENT = "#ff6600"
CARD_BG = "#0f0f10"
TEXT = "#eaeaea"

st.set_page_config(page_title=APP_TITLE, layout="wide")
st.markdown(f"""
<style>
body {{ background:#0b0c0d; color:{TEXT}; }}
.card {{ background:{CARD_BG}; border-radius:8px; padding:12px; margin-bottom:14px; border:1px solid {ACCENT}; }}
.pos-badge {{ display:inline-block; padding:6px 10px; border-radius:10px; background:{ACCENT}; color:#000; font-weight:700; }}
.stButton>button {{ background:{ACCENT} !important; color:#000 !important; font-weight:700; }}
.small-muted {{ color: rgba(255,255,255,0.6); font-size:13px; }}
.rank-row {{}}
</style>
""", unsafe_allow_html=True)

# ---------------- DB helpers ----------------
def empty_db():
    return {
        "jogadores": [],   # {"Nome","Posição"}
        "rodadas": [],     # {"date": "YYYY-MM-DD", "records":[{Nome,presente,Gols,Assistencias, flags..., puskas_votes}]}
        "manual_totals": {},  # per-player manual adjustments and overrides
        "melhor_quinteto": [],  # list of {"players":[...5...], "vitorias": n}
        "meta": {"created": datetime.now().isoformat()}
    }

def load_db_disk():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return empty_db()
    return empty_db()

def save_db_disk(db):
    tmp = DB_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DB_FILE)

# ---------------- Session init ----------------
if "db" not in st.session_state:
    st.session_state.db = load_db_disk()
    st.session_state.dirty = False

if "admin" not in st.session_state:
    st.session_state.admin = False

if "new_player_rows" not in st.session_state:
    st.session_state.new_player_rows = []
if "new_rodada_rows" not in st.session_state:
    st.session_state.new_rodada_rows = []
if "show_edit_section" not in st.session_state:
    st.session_state.show_edit_section = None  # used to hold which ranking is being edited

# ---------------- Auth ----------------
def admin_login(pwd):
    if pwd == ADMIN_PWD:
        st.session_state.admin = True
        st.success("Login admin OK")
    else:
        st.error("Senha incorreta")

def admin_logout():
    st.session_state.admin = False
    st.success("Logout OK")

# ---------------- Utilities ----------------
def ensure_player(nome, pos="Indefinido"):
    if not nome:
        return
    if any(p["Nome"] == nome for p in st.session_state.db["jogadores"]):
        return
    st.session_state.db["jogadores"].append({"Nome": nome, "Posição": pos})
    st.session_state.dirty = True

def parse_date_obj(x):
    if isinstance(x, date):
        return x
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, str) and x:
        try:
            return date.fromisoformat(x)
        except:
            try:
                return pd.to_datetime(x).date()
            except:
                return None
    return None

# When renaming a player, update manual_totals keys and rodadas records names
def rename_player(old, new):
    db = st.session_state.db
    # update jogadores list
    for p in db["jogadores"]:
        if p["Nome"] == old:
            p["Nome"] = new
    # update manual_totals key
    mt = db.get("manual_totals", {})
    if old in mt:
        mt[new] = mt.pop(old)
    # update rodadas records
    for rd in db.get("rodadas", []):
        for rec in rd.get("records", []):
            if rec.get("Nome") == old:
                rec["Nome"] = new
    st.session_state.db = db
    st.session_state.dirty = True

# ---------------- Aggregation ----------------
def aggregate_totals(period_start=None, period_end=None):
    db = st.session_state.db
    goals = defaultdict(int)
    assists = defaultdict(int)
    cat_counts = {k:defaultdict(int) for k in ["craque_vit","art","assist","def","goleiro","coringa","capitao","puskas_votes"]}

    # manual totals
    manual = db.get("manual_totals", {}) or {}
    for nome, vals in manual.items():
        goals[nome] += int(vals.get("Gols",0) or 0)
        assists[nome] += int(vals.get("Assistencias",0) or 0)
        if vals.get("craque_vitorias_manual"):
            cat_counts["craque_vit"][nome] += int(vals.get("craque_vitorias_manual") or 0)
        if vals.get("art_manual"):
            cat_counts["art"][nome] += int(vals.get("art_manual") or 0)
        if vals.get("assist_manual"):
            cat_counts["assist"][nome] += int(vals.get("assist_manual") or 0)
        if vals.get("def_manual"):
            cat_counts["def"][nome] += int(vals.get("def_manual") or 0)
        if vals.get("goleiro_manual"):
            cat_counts["goleiro"][nome] += int(vals.get("goleiro_manual") or 0)
        if vals.get("coringa_manual"):
            cat_counts["coringa"][nome] += int(vals.get("coringa_manual") or 0)
        if vals.get("capitao_manual"):
            cat_counts["capitao"][nome] += int(vals.get("capitao_manual") or 0)
        if vals.get("puskas_manual"):
            cat_counts["puskas_votes"][nome] += int(vals.get("puskas_manual") or 0)

    # rodadas
    for rd in db.get("rodadas", []):
        rd_date = parse_date_obj(rd.get("date"))
        if period_start and period_end:
            if not rd_date:
                continue
            if rd_date < period_start or rd_date > period_end:
                continue
        for rec in rd.get("records", []):
            nome = rec.get("Nome")
            if rec.get("presente", True):
                goals[nome] += int(rec.get("Gols",0) or 0)
                assists[nome] += int(rec.get("Assistencias",0) or 0)
            if rec.get("craque_flag"):
                cat_counts["craque_vit"][nome] += 1
            if rec.get("art_flag"):
                cat_counts["art"][nome] += 1
            if rec.get("assist_flag"):
                cat_counts["assist"][nome] += 1
            if rec.get("defensor_flag"):
                cat_counts["def"][nome] += 1
            if rec.get("goleiro_flag"):
                cat_counts["goleiro"][nome] += 1
            if rec.get("coringa_flag"):
                cat_counts["coringa"][nome] += 1
            if rec.get("capitao_flag"):
                cat_counts["capitao"][nome] += 1
            v = int(rec.get("puskas_votes",0) or 0)
            if v:
                cat_counts["puskas_votes"][nome] += v

    # craque auto points
    craque_auto = defaultdict(int)
    for n,cnt in cat_counts["craque_vit"].items(): craque_auto[n] += cnt * WEIGHTS["craque"]
    for n,cnt in cat_counts["art"].items(): craque_auto[n] += cnt * WEIGHTS["artilheiro"]
    for n,cnt in cat_counts["assist"].items(): craque_auto[n] += cnt * WEIGHTS["assistencia"]
    for n,cnt in cat_counts["def"].items(): craque_auto[n] += cnt * WEIGHTS["defensor"]
    for n,cnt in cat_counts["goleiro"].items(): craque_auto[n] += cnt * WEIGHTS["goleiro"]
    for n,cnt in cat_counts["coringa"].items(): craque_auto[n] += cnt * WEIGHTS["coringa"]
    for n,cnt in cat_counts["capitao"].items(): craque_auto[n] += cnt * WEIGHTS["capitao"]

    craque_manual_pts = {}
    for nome, vals in manual.items():
        if vals.get("craque_points_manual"):
            craque_manual_pts[nome] = int(vals.get("craque_points_manual") or 0)

    craque_final = defaultdict(int)
    all_names = set(list(goals.keys()) + list(assists.keys()) + list(craque_auto.keys()) + list(craque_manual_pts.keys()) + [p["Nome"] for p in st.session_state.db.get("jogadores", [])])
    for n in all_names:
        craque_final[n] = int(craque_auto.get(n,0)) + int(craque_manual_pts.get(n,0))

    return dict(goals), dict(assists), {k:dict(v) for k,v in cat_counts.items()}, dict(craque_auto), dict(craque_manual_pts), dict(craque_final)

def fmt_rank(d, top_n=None):
    arr = [(k,v) for k,v in d.items() if v is not None and v!=0]
    arr_sorted = sorted(arr, key=lambda x:-x[1])
    res=[]; last_val=None; last_pos=0
    for idx,(name,val) in enumerate(arr_sorted, start=1):
        if last_val is None:
            pos=1; last_pos=1
        else:
            pos = last_pos if val==last_val else idx; last_pos=pos
        last_val=val
        res.append((f"{pos}º", name, val))
        if top_n and len(res)>=top_n:
            break
    return res

# ---------------- UI ----------------
def sidebar():
    st.sidebar.title(APP_TITLE)
    if st.session_state.admin:
        st.sidebar.markdown("**Modo: Admin**")
        if st.sidebar.button("Logout"):
            admin_logout()
    else:
        st.sidebar.markdown("**Modo: Público**")
        pwd = st.sidebar.text_input("Senha admin", type="password")
        if st.sidebar.button("Entrar como admin"):
            admin_login(pwd)
    st.sidebar.markdown("---")
    page = st.sidebar.radio("Navegar", ["Dashboard","Jogadores","Registrar Rodada","Rodadas","Import/Export","Admin"])
    if st.session_state.dirty:
        st.sidebar.warning("Alterações não salvas em disco.")
    return page

# ---------- Dashboard functions for editing ----------
def edit_ranking_form(kind, mapping, value_label):
    """
    kind: internal name (e.g., 'artilharia','assistencias','craque_final','craque_vit','def','coringa','capitao','goleiro','puskas')
    mapping: dict name->value
    value_label: shown label (e.g., 'Gols' / 'Assistências' / 'Pontos')
    """
    st.markdown(f"### Editar {value_label}")
    db = st.session_state.db
    names = sorted(set(list(mapping.keys()) + [p["Nome"] for p in db.get("jogadores",[])]))
    with st.form(f"edit_{kind}_form"):
        entries=[]
        for nome in names:
            cur = mapping.get(nome, 0)
            cols = st.columns([3,1])
            cols[0].markdown(f"**{nome}**")
            val = cols[1].number_input("", value=int(cur or 0), key=f"edit_{kind}_{nome}", format="%d")
            entries.append((nome,int(val)))
        submit = st.form_submit_button("Salvar alterações")
        if submit:
            mt = db.setdefault("manual_totals", {})
            for nome,val in entries:
                mt.setdefault(nome, {})
                if kind == "artilharia":
                    mt[nome]["Gols"] = int(val)
                elif kind == "assistencias":
                    mt[nome]["Assistencias"] = int(val)
                elif kind == "craque_final":
                    mt[nome]["craque_points_manual"] = int(val)
                elif kind == "craque_vit":
                    mt[nome]["craque_vitorias_manual"] = int(val)
                elif kind == "def":
                    mt[nome]["def_manual"] = int(val)
                elif kind == "coringa":
                    mt[nome]["coringa_manual"] = int(val)
                elif kind == "capitao":
                    mt[nome]["capitao_manual"] = int(val)
                elif kind == "goleiro":
                    mt[nome]["goleiro_manual"] = int(val)
                elif kind == "puskas":
                    mt[nome]["puskas_manual"] = int(val)
            st.session_state.db = db
            st.session_state.dirty = True
            st.success("Alterações salvas em memória.")
            st.rerun()

# ---------------- UI pages ----------------
def page_dashboard():
    # Logo + título
    col1, col2 = st.columns([1, 4])
    with col1:
        st.image("barca_logo.png", width=120)
    with col2:
        st.markdown(
            "<h1 style='color:#FFA500; font-weight:800;'>Central do Barça - Dados e Estatísticas</h1>",
            unsafe_allow_html=True
        )

    st.markdown("---")
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='color:{ACCENT}'>Dashboard</h2>", unsafe_allow_html=True)

    period = st.radio("Período", ["Mensal","Trimestral","Semestral","Anual","Histórico"], index=1, horizontal=True)
    today = date.today()
    if period == "Mensal":
        start = today - timedelta(days=30); end = today
    elif period == "Trimestral":
        start = today - timedelta(days=90); end = today
    elif period == "Semestral":
        start = today - timedelta(days=180); end = today
    elif period == "Anual":
        start = today - timedelta(days=365); end = today
    else:
        start=None; end=None

    goals, assists, cat_counts, craque_auto, craque_manual, craque_final = aggregate_totals(period_start=start, period_end=end)

    # Top row: Artilharia | Assistências | Craque do Barça
    c1,c2,c3 = st.columns(3)
    with c1:
        st.markdown("### 🥅 Artilharia")
        rows = fmt_rank(goals)
        limit = 20
        for pos,name,val in rows[:limit]:
            st.markdown(f"<div style='display:flex;justify-content:space-between;padding:2px 0'><div><span class='pos-badge'>{pos}</span> {name}</div><div style='color:{ACCENT}; font-weight:800'>{val}</div></div>", unsafe_allow_html=True)
        if len(rows) > limit:
            if st.button("Ver mais artilharia"):
                for pos,name,val in rows[limit:]:
                    st.markdown(f"<div style='display:flex;justify-content:space-between;padding:2px 0'><div><span class='pos-badge'>{pos}</span> {name}</div><div style='color:{ACCENT}; font-weight:800'>{val}</div></div>", unsafe_allow_html=True)
        if st.session_state.admin:
            if st.button("Editar Artilharia"):
                st.session_state.show_edit_section = ("artilharia", goals)
    with c2:
        st.markdown("### 🎯 Assistências")
        rows = fmt_rank(assists)
        limit = 20
        for pos,name,val in rows[:limit]:
            st.markdown(f"<div style='display:flex;justify-content:space-between;padding:2px 0'><div><span class='pos-badge'>{pos}</span> {name}</div><div style='color:{ACCENT}; font-weight:800'>{val}</div></div>", unsafe_allow_html=True)
        if len(rows) > limit:
            if st.button("Ver mais assistências"):
                for pos,name,val in rows[limit:]:
                    st.markdown(f"<div style='display:flex;justify-content:space-between;padding:2px 0'><div><span class='pos-badge'>{pos}</span> {name}</div><div style='color:{ACCENT}; font-weight:800'>{val}</div></div>", unsafe_allow_html=True)
        if st.session_state.admin:
            if st.button("Editar Assistências"):
                st.session_state.show_edit_section = ("assistencias", assists)
    with c3:
        st.markdown("### 🌟 Craque do Barça")
        rows = fmt_rank(craque_final)
        limit = 20
        for pos,name,val in rows[:limit]:
            st.markdown(f"<div style='display:flex;justify-content:space-between;padding:2px 0'><div><span class='pos-badge'>{pos}</span> {name}</div><div style='color:{ACCENT}; font-weight:800'>{val}</div></div>", unsafe_allow_html=True)
        if len(rows) > limit:
            if st.button("Ver mais Craque do Barça"):
                for pos,name,val in rows[limit:]:
                    st.markdown(f"<div style='display:flex;justify-content:space-between;padding:2px 0'><div><span class='pos-badge'>{pos}</span> {name}</div><div style='color:{ACCENT}; font-weight:800'>{val}</div></div>", unsafe_allow_html=True)
        if st.session_state.admin:
            if st.button("Editar Craque do Barça (pontos manuais)"):
                st.session_state.show_edit_section = ("craque_final", craque_final)

    st.markdown("---")

    # categories
    cat_cols = st.columns(5)
    cats_info = [
        ("Craque da Rodada", cat_counts.get("craque_vit",{}), "craque_vit"),
        ("Defensor", cat_counts.get("def",{}), "def"),
        ("Coringa", cat_counts.get("coringa",{}), "coringa"),
        ("Capitão", cat_counts.get("capitao",{}), "capitao"),
        ("Goleiro", cat_counts.get("goleiro",{}), "goleiro")
    ]
    for col, (title, mapping, key) in zip(cat_cols, cats_info):
        col.markdown(f"### {title}")
        rows = fmt_rank(mapping)
        limit = 10
        for pos,name,val in rows[:limit]:
            col.markdown(f"<div style='display:flex;justify-content:space-between'><div><span class='pos-badge'>{pos}</span> {name}</div><div style='color:{ACCENT}; font-weight:800'>{val}</div></div>", unsafe_allow_html=True)
        if len(rows) > limit:
            if col.button(f"Ver mais {title}"):
                for pos,name,val in rows[limit:]:
                    col.markdown(f"<div style='display:flex;justify-content:space-between'><div><span class='pos-badge'>{pos}</span> {name}</div><div style='color:{ACCENT}; font-weight:800'>{val}</div></div>", unsafe_allow_html=True)
        if st.session_state.admin:
            if col.button(f"Editar {title}"):
                st.session_state.show_edit_section = (key, mapping)

    # Puskás and Melhor Quinteto area
    lower_cols = st.columns([3,2])
    with lower_cols[0]:
        st.markdown("### 🏆 Puskás (votos)")
        # render name and votes closer together (same small div)
        rows = fmt_rank(cat_counts.get("puskas_votes",{}))
        limit = 20
        for pos,name,val in rows[:limit]:
            st.markdown(f"<div style='display:flex;justify-content:space-between;gap:8px'><div><span class='pos-badge'>{pos}</span> {name}</div><div style='min-width:48px;text-align:right;color:{ACCENT}; font-weight:800'>{val}</div></div>", unsafe_allow_html=True)
        if len(rows) > limit:
            if st.button("Ver mais Puskás"):
                for pos,name,val in rows[limit:]:
                    st.markdown(f"<div style='display:flex;justify-content:space-between;gap:8px'><div><span class='pos-badge'>{pos}</span> {name}</div><div style='min-width:48px;text-align:right;color:{ACCENT}; font-weight:800'>{val}</div></div>", unsafe_allow_html=True)
        if st.session_state.admin:
            if st.button("Editar Puskás"):
                st.session_state.show_edit_section = ("puskas", cat_counts.get("puskas_votes",{}))
            if st.button("Zerar Puskás"):
                st.session_state.db["manual_totals"] = {k: {**v, "puskas_manual":0} if isinstance(v, dict) else v for k,v in st.session_state.db.get("manual_totals",{}).items()}
                # also remove puskas votes from rodadas? requirement was manual reset, so only manual_totals set to 0
                st.session_state.dirty = True
                st.success("Puskás zerado (manuais).")
    with lower_cols[1]:
        st.markdown("### 🔰 Melhor Quinteto")
        meq = st.session_state.db.get("melhor_quinteto", [])
        # show each quinteto in one line with position and victories
        for idx,q in enumerate(meq, start=1):
            players = ", ".join(q.get("players",[]))
            v = q.get("vitorias",0)
            st.markdown(f"<div style='display:flex;justify-content:space-between;padding:4px 0'><div><span class='pos-badge'>{idx}º</span> {players}</div><div style='color:{ACCENT}; font-weight:800'>{v} vitórias</div></div>", unsafe_allow_html=True)
        if not meq:
            st.markdown("<div class='small-muted'>Nenhum quinteto registrado.</div>", unsafe_allow_html=True)
        if st.session_state.admin:
            if st.button("Adicionar Quinteto"):
                st.session_state.show_edit_section = ("add_quinteto", None)
            if st.button("Editar Quintetos"):
                st.session_state.show_edit_section = ("edit_quintetos", meq)
            if st.button("Zerar Quintetos"):
                st.session_state.db["melhor_quinteto"] = []
                st.session_state.dirty = True
                st.success("Ranking de quintetos zerado.")

    # Show edit section if any
    if st.session_state.show_edit_section:
        kind, data = st.session_state.show_edit_section
        st.markdown("---")
        if kind in ("artilharia","assistencias","craque_final","craque_vit","def","coringa","capitao","goleiro","puskas"):
            # call generic editor
            label = {
                "artilharia":"Artilharia (Gols)",
                "assistencias":"Assistências",
                "craque_final":"Craque do Barça (pontos manuais)",
                "craque_vit":"Craque da Rodada (vezes)",
                "def":"Defensor (vezes)",
                "coringa":"Coringa (vezes)",
                "capitao":"Capitão (vezes)",
                "goleiro":"Goleiro (vezes)",
                "puskas":"Puskás (votos)"
            }[kind]
            edit_ranking_form(kind if kind!="craque_final" else "craque_final", data if data is not None else {}, label)
        elif kind == "add_quinteto":
            st.markdown("### Adicionar novo Quinteto")
            with st.form("add_quinteto_form"):
                p1 = st.text_input("Jogador 1")
                p2 = st.text_input("Jogador 2")
                p3 = st.text_input("Jogador 3")
                p4 = st.text_input("Jogador 4")
                p5 = st.text_input("Jogador 5")
                vits = st.number_input("Vitórias", min_value=0, value=0, format="%d")
                submit = st.form_submit_button("Adicionar Quinteto")
                if submit:
                    quint = {"players":[x.strip() for x in [p1,p2,p3,p4,p5] if x.strip()], "vitorias": int(vits)}
                    if quint["players"]:
                        mq = st.session_state.db.setdefault("melhor_quinteto", [])
                        mq.append(quint)
                        st.session_state.dirty = True
                        st.success("Quinteto adicionado.")
                        st.session_state.show_edit_section = None
                        st.rerun()
                    else:
                        st.warning("Insira pelo menos um nome.")
        elif kind == "edit_quintetos":
            st.markdown("### Editar Quintetos")
            meq = st.session_state.db.get("melhor_quinteto", [])
            if not meq:
                st.info("Nenhum quinteto para editar.")
            else:
                with st.form("edit_quintetos_form"):
                    modified=[]
                    for i,q in enumerate(meq):
                        cols = st.columns([3,1,1])
                        players_str = ", ".join(q.get("players",[]))
                        p_input = cols[0].text_input(f"Quinteto {i+1} (nomes separados por vírgula)", value=players_str, key=f"q_players_{i}")
                        v = cols[1].number_input("Vitórias", min_value=0, value=q.get("vitorias",0), key=f"q_v_{i}", format="%d")
                        rem = cols[2].checkbox("Remover", key=f"q_rem_{i}")
                        modified.append((p_input, int(v), rem))
                    submit = st.form_submit_button("Salvar quintetos")
                    if submit:
                        newlist=[]
                        for p_input,v,rem in modified:
                            if rem: continue
                            players = [x.strip() for x in p_input.split(",") if x.strip()]
                            newlist.append({"players":players,"vitorias":v})
                        st.session_state.db["melhor_quinteto"] = newlist
                        st.session_state.dirty = True
                        st.success("Quintetos atualizados.")
                        st.session_state.show_edit_section = None
                        st.rerun()
        # close edit section
    st.markdown("</div>", unsafe_allow_html=True)

def page_jogadores():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='color:{ACCENT}'>Jogadores</h2>", unsafe_allow_html=True)
    db = st.session_state.db

    # Bulk-add rows UI
    st.markdown("#### Adicionar vários jogadores de uma vez")
    cadd = st.columns([1,1,1])
    if cadd[0].button("+ Adicionar linha"):
        st.session_state.new_player_rows.append(len(st.session_state.new_player_rows))
    if cadd[1].button("Limpar linhas novas"):
        st.session_state.new_player_rows = []

    if st.session_state.new_player_rows:
        with st.form("bulk_add_players"):
            new_players=[]
            for idx in st.session_state.new_player_rows:
                cols = st.columns([2,1,1,1,1,1,1,1,1,1,1,1])
                nome = cols[0].text_input("Nome", key=f"np_nome_{idx}")
                pos = cols[1].text_input("Posição", key=f"np_pos_{idx}", value="Indefinido")
                gols = cols[2].number_input("Gols", min_value=0, value=0, key=f"np_g_{idx}", format="%d")
                ass = cols[3].number_input("Assist", min_value=0, value=0, key=f"np_a_{idx}", format="%d")
                craq_v = cols[4].number_input("Craque (vezes)", min_value=0, value=0, key=f"np_cqv_{idx}", format="%d")
                craq_pts_manual = cols[5].number_input("Craque pts man", min_value=0, value=0, key=f"np_cqpm_{idx}", format="%d")
                art = cols[6].number_input("Art pts (manual)", min_value=0, value=0, key=f"np_art_{idx}", format="%d")
                asc = cols[7].number_input("Assist pts (manual)", min_value=0, value=0, key=f"np_asc_{idx}", format="%d")
                defp = cols[8].number_input("Def pts (manual)", min_value=0, value=0, key=f"np_def_{idx}", format="%d")
                cor = cols[9].number_input("Coringa pts (manual)", min_value=0, value=0, key=f"np_cor_{idx}", format="%d")
                cap = cols[10].number_input("Capitão pts (manual)", min_value=0, value=0, key=f"np_cap_{idx}", format="%d")
                pus = cols[11].number_input("Puskás votos (manual)", min_value=0, value=0, key=f"np_pus_{idx}", format="%d")
                new_players.append({
                    "Nome": nome.strip() if nome else "",
                    "Posição": pos.strip() if pos else "Indefinido",
                    "Gols": int(gols), "Assistencias": int(ass),
                    "craque_v": int(craq_v), "craque_pts_manual": int(craq_pts_manual),
                    "art_manual": int(art), "assist_manual": int(asc), "def_manual": int(defp),
                    "coringa_manual": int(cor), "capitao_manual": int(cap), "puskas_manual": int(pus)
                })
            submit = st.form_submit_button("Salvar linhas (adicionar jogadores)")
            if submit:
                added=0
                for p in new_players:
                    if not p["Nome"]: continue
                    if not any(j["Nome"] == p["Nome"] for j in db["jogadores"]):
                        db["jogadores"].append({"Nome": p["Nome"], "Posição": p["Posição"]})
                    mt = db.setdefault("manual_totals", {})
                    mt.setdefault(p["Nome"], {})
                    mt[p["Nome"]]["Gols"] = int(mt[p["Nome"]].get("Gols",0) or 0) + p["Gols"]
                    mt[p["Nome"]]["Assistencias"] = int(mt[p["Nome"]].get("Assistencias",0) or 0) + p["Assistencias"]
                    if p["craque_v"]:
                        mt[p["Nome"]]["craque_vitorias_manual"] = int(mt[p["Nome"]].get("craque_vitorias_manual",0) or 0) + p["craque_v"]
                    if p["craque_pts_manual"]:
                        mt[p["Nome"]]["craque_points_manual"] = int(mt[p["Nome"]].get("craque_points_manual",0) or 0) + p["craque_pts_manual"]
                    mt[p["Nome"]]["art_manual"] = int(mt[p["Nome"]].get("art_manual",0) or 0) + p["art_manual"]
                    mt[p["Nome"]]["assist_manual"] = int(mt[p["Nome"]].get("assist_manual",0) or 0) + p["assist_manual"]
                    mt[p["Nome"]]["def_manual"] = int(mt[p["Nome"]].get("def_manual",0) or 0) + p["def_manual"]
                    mt[p["Nome"]]["coringa_manual"] = int(mt[p["Nome"]].get("coringa_manual",0) or 0) + p["coringa_manual"]
                    mt[p["Nome"]]["capitao_manual"] = int(mt[p["Nome"]].get("capitao_manual",0) or 0) + p["capitao_manual"]
                    mt[p["Nome"]]["puskas_manual"] = int(mt[p["Nome"]].get("puskas_manual",0) or 0) + p["puskas_manual"]
                    db["manual_totals"] = mt
                    added += 1
                st.session_state.dirty = True
                st.success(f"{added} jogadores adicionados em memória.")
                st.session_state.new_player_rows = []
                st.rerun()

    # Show aggregated players table with edit option for Name/Position
    goals, assists, cat_counts, craque_auto, craque_manual, craque_final = aggregate_totals()
    rows = []
    for p in db["jogadores"]:
        nome = p["Nome"]
        rows.append({
            "Nome": nome,
            "Posição": p.get("Posição",""),
            "Gols": goals.get(nome,0),
            "Assistências": assists.get(nome,0),
            "Craque vits (cnt)": cat_counts.get("craque_vit",{}).get(nome,0),
            "Craque pts (final)": craque_final.get(nome,0),
            "Puskás (votes)": cat_counts.get("puskas_votes",{}).get(nome,0)
        })
    if rows:
        st.dataframe(pd.DataFrame(rows).sort_values(by="Craque pts (final)", ascending=False).reset_index(drop=True), use_container_width=True)
    else:
        st.info("Nenhum jogador cadastrado.")

    # Edit players (name and position) in mass
    st.markdown("### Editar Nome / Posição (em massa)")
    if st.session_state.admin and db["jogadores"]:
        with st.form("edit_players_form"):
            entries=[]
            for p in db["jogadores"]:
                cols = st.columns([3,2])
                new_name = cols[0].text_input("Nome", value=p["Nome"], key=f"edit_name_{p['Nome']}")
                new_pos = cols[1].text_input("Posição", value=p.get("Posição",""), key=f"edit_pos_{p['Nome']}")
                entries.append((p["Nome"], new_name.strip(), new_pos.strip()))
            submit = st.form_submit_button("Salvar alterações de nomes/posições")
            if submit:
                renamed_map = {}
                for old, new, pos in entries:
                    if new and new != old:
                        # rename in jogadores and other structures
                        rename_player(old, new)
                        renamed_map[old] = new
                    # update position
                    for p in st.session_state.db["jogadores"]:
                        if p["Nome"] == (renamed_map.get(old, old)):
                            p["Posição"] = pos or p.get("Posição","")
                st.session_state.dirty = True
                st.success("Nomes e posições atualizados.")
                st.rerun()
    else:
        if not st.session_state.admin:
            st.info("Faça login como admin para editar jogadores.")

    st.markdown("</div>", unsafe_allow_html=True)

def page_registrar_rodada():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='color:{ACCENT}'>Registrar Rodada</h2>", unsafe_allow_html=True)
    if not st.session_state.admin:
        st.warning("Faça login como admin"); st.markdown("</div>", unsafe_allow_html=True); return
    db = st.session_state.db
    if not db["jogadores"]:
        st.info("Nenhum jogador cadastrado. Adicione jogadores em 'Jogadores'"); st.markdown("</div>", unsafe_allow_html=True); return

    rd_date = st.date_input("Data da rodada", value=date.today())

    player_names = [p["Nome"] for p in db["jogadores"]]
    selected = st.multiselect("Selecione os jogadores que participaram (multi-select)", options=player_names)

    if selected:
        st.markdown("Preencha os campos abaixo para os jogadores selecionados")
        with st.form("rodada_multi_form"):
            entries=[]
            for nome in selected:
                cols = st.columns([2,1,1,1,1,1,1,1,1,1,1,1])
                cols[0].markdown(f"**{nome}**")
                presente = cols[1].checkbox("Presente", value=True, key=f"rd_pres_{nome}")
                gols = cols[2].number_input("Gols", min_value=0, value=0, key=f"rd_g_{nome}", format="%d")
                assists = cols[3].number_input("Assist", min_value=0, value=0, key=f"rd_a_{nome}", format="%d")
                craq = cols[4].checkbox("Craque", key=f"rd_cq_{nome}")
                art = cols[5].checkbox("Artilheiro", key=f"rd_art_{nome}")
                assf = cols[6].checkbox("Assist", key=f"rd_as_{nome}")
                deff = cols[7].checkbox("Defensor", key=f"rd_def_{nome}")
                gof = cols[8].checkbox("Goleiro", key=f"rd_gol_{nome}")
                corf = cols[9].checkbox("Coringa", key=f"rd_cor_{nome}")
                capf = cols[10].checkbox("Capitão", key=f"rd_cap_{nome}")
                pusv = cols[11].number_input("Puskás votos", min_value=0, value=0, key=f"rd_pus_{nome}", format="%d")
                entries.append({
                    "Nome": nome,
                    "presente": bool(presente),
                    "Gols": int(gols),
                    "Assistencias": int(assists),
                    "craque_flag": bool(craq),
                    "art_flag": bool(art),
                    "assist_flag": bool(assf),
                    "defensor_flag": bool(deff),
                    "goleiro_flag": bool(gof),
                    "coringa_flag": bool(corf),
                    "capitao_flag": bool(capf),
                    "puskas_votes": int(pusv)
                })
            # Option: register a quinteto winner for this rodada (optional)
            with st.expander("Registrar quinteto vencedor desta rodada (opcional)"):
                q_sel = []
                for i in range(5):
                    q_sel.append(st.selectbox(f"Jogador {i+1}", options=[""] + player_names, key=f"q_sel_{i}"))
            submit = st.form_submit_button("Salvar rodada (multi)")
            if submit:
                if entries:
                    rd_obj = {"date": rd_date.isoformat(), "records": entries}
                    # if quinteto registered, add to manual quintet list as manual (user wanted manual quintet counts)
                    quint_players = [x for x in q_sel if x and x.strip()]
                    if quint_players:
                        mq = st.session_state.db.setdefault("melhor_quinteto", [])
                        # check if identical quintet exists (order-sensitive or not? we'll consider order-insensitive)
                        def normalize(q): return sorted([s.lower() for s in q])
                        found=False
                        for q in mq:
                            if normalize(q.get("players",[])) == normalize(quint_players):
                                q["vitorias"] = int(q.get("vitorias",0)) + 1
                                found=True
                                break
                        if not found:
                            mq.append({"players":quint_players,"vitorias":1})
                    st.session_state.db["rodadas"].append(rd_obj)
                    st.session_state.dirty = True
                    st.success(f"Rodada com {len(entries)} registros adicionada em memória.")
                    st.rerun()
                else:
                    st.warning("Nenhuma linha válida.")
    else:
        st.info("Selecione jogadores acima para preencher os dados da rodada.")

    st.markdown("</div>", unsafe_allow_html=True)

def page_rodadas():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='color:{ACCENT}'>Rodadas (Histórico)</h2>", unsafe_allow_html=True)
    db = st.session_state.db
    if not db["rodadas"]:
        st.info("Nenhuma rodada registrada."); st.markdown("</div>", unsafe_allow_html=True); return
    dates = sorted({r.get("date","") for r in db["rodadas"] if r.get("date")}, reverse=True)
    sel = st.selectbox("Escolha data", [""] + dates)
    if not sel:
        st.markdown("</div>", unsafe_allow_html=True); return
    rows=[]
    for rd in db["rodadas"]:
        if rd.get("date") == sel:
            rows.extend(rd.get("records", []))
    if rows:
        st.dataframe(pd.DataFrame(rows).sort_values(by="Gols", ascending=False).reset_index(drop=True), use_container_width=True)
    else:
        st.info("Nada para mostrar nessa data.")
    st.markdown("</div>", unsafe_allow_html=True)

def page_import_export():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='color:{ACCENT}'>Import / Export / Salvar DB</h2>", unsafe_allow_html=True)
    db = st.session_state.db
    c1,c2 = st.columns(2)
    with c1:
        if st.button("Salvar DB em disco"):
            save_db_disk(db)
            st.session_state.dirty = False
            st.success(f"DB salvo em {DB_FILE}")
        if st.button("Carregar DB do disco (substitui em memória)"):
            st.session_state.db = load_db_disk()
            st.session_state.dirty = False
            st.success("DB carregado do disco")
        if st.button("Resetar DB em memória (zerar)"):
            st.session_state.db = empty_db()
            st.session_state.dirty = True
            st.success("DB em memória zerado")
    with c2:
        st.download_button("Exportar snapshot (JSON)", json.dumps(db, ensure_ascii=False, indent=2), file_name="central_do_barca_snapshot.json", mime="application/json")
        st.markdown("---")
        st.markdown("Importar Excel (opcional) — colunas mínimas: Nome, Gols, Assistências, coluna Data opcional.")
        up = st.file_uploader("Upload .xlsx (opcional)", type=["xlsx"])
        if up:
            try:
                df = pd.read_excel(up, sheet_name=0)
                st.write("Preview (primeiras linhas):")
                st.dataframe(df.head())
                if st.button("Importar XLSX (substituir rodadas em memória)"):
                    cols = {c.lower(): c for c in df.columns}
                    name_col = None; gols_col=None; assist_col=None; date_col=None
                    for k,orig in cols.items():
                        if "nome" in k or "name" in k: name_col = orig
                        if "gol" in k and gols_col is None: gols_col = orig
                        if "assist" in k and assist_col is None: assist_col = orig
                        if "data" in k or "date" in k: date_col = orig
                    if not (name_col and gols_col and assist_col):
                        st.error("Planilha precisa ter colunas Nome, Gols e Assistências")
                    else:
                        grouped = {}
                        for _, r in df.iterrows():
                            nome = str(r[name_col]).strip()
                            gols = int(r[gols_col]) if not pd.isna(r[gols_col]) else 0
                            assist = int(r[assist_col]) if not pd.isna(r[assist_col]) else 0
                            if date_col and not pd.isna(r.get(date_col)):
                                d = pd.to_datetime(r[date_col]).date().isoformat()
                            else:
                                d = date.today().isoformat()
                            grouped.setdefault(d, []).append({"Nome":nome,"Gols":int(gols),"Assistencias":int(assist)})
                            ensure_player(nome)
                        # build rodadas
                        new_rodadas=[]
                        for d, items in grouped.items():
                            recs=[]
                            for it in items:
                                recs.append({"Nome":it["Nome"], "presente":True, "Gols":int(it["Gols"]), "Assistencias":int(it["Assistencias"]),
                                             "craque_flag":False,"art_flag":False,"assist_flag":False,"defensor_flag":False,"goleiro_flag":False,"coringa_flag":False,"capitao_flag":False,"puskas_votes":0})
                            new_rodadas.append({"date": d, "records": recs})
                        st.session_state.db["rodadas"] = new_rodadas
                        st.session_state.dirty = True
                        st.success("Import aplicado em memória. Salve DB se quiser persistir.")
            except Exception as e:
                st.error(f"Erro lendo planilha: {e}")
    st.markdown("</div>", unsafe_allow_html=True)

def page_admin():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='color:{ACCENT}'>Admin</h2>", unsafe_allow_html=True)
    if st.session_state.admin:
        if st.button("Mostrar DB (debug)"):
            st.code(json.dumps(st.session_state.db, ensure_ascii=False, indent=2))
        st.markdown("---")
        st.markdown("Salvar / Remover DB")
        if st.button("Apagar DB em disco (cuidado)"):
            try:
                if os.path.exists(DB_FILE):
                    os.remove(DB_FILE)
                    st.success("Arquivo em disco removido.")
                else:
                    st.info("Nenhum arquivo salvo em disco.")
            except Exception as e:
                st.error(f"Erro ao apagar: {e}")
    else:
        st.info("Faça login como admin para ferramentas avançadas.")
    st.markdown("</div>", unsafe_allow_html=True)

# Router
def main():
    st.title(APP_TITLE)
    page = sidebar()
    if page == "Dashboard":
        page_dashboard()
    elif page == "Jogadores":
        page_jogadores()
    elif page == "Registrar Rodada":
        page_registrar_rodada()
    elif page == "Rodadas":
        page_rodadas()
    elif page == "Import/Export":
        page_import_export()
    else:
        page_admin()

if __name__ == "__main__":
    main()

