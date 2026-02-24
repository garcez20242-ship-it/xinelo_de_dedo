import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestão Master v5.8", layout="wide", page_icon="🩴")
st.title("🩴 Gestão Xinelo de Dedo v5.8")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- FUNÇÕES ---
def get_data_hora():
    return (datetime.now() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")

def limpar_valor(valor):
    try:
        if pd.isna(valor) or str(valor).strip() == "": return 0.0
        v = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
        return float(v)
    except: return 0.0

def gerar_recibo(r):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 10, "RECIBO DE VENDA", ln=True, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.cell(190, 10, f"Data: {r['Data']} | Cliente: {r['Cliente']}", ln=True)
    pdf.multi_cell(190, 8, f"Resumo: {r['Resumo']}")
    pdf.cell(190, 10, f"Total: R$ {limpar_valor(r['Valor Total']):.2f}", ln=True, align="R")
    return pdf.output(dest='S').encode('latin-1')

# --- CONEXÃO ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=5)
def carregar_dados():
    def ler(aba, cols):
        try:
            df = conn.read(spreadsheet=URL_PLANILHA, worksheet=aba, ttl="0s")
            return df.dropna(how='all').loc[:, ~df.columns.str.contains('^Unnamed')] if df is not None else pd.DataFrame(columns=cols)
        except: return pd.DataFrame(columns=cols)
    
    return {
        "est": ler("Estoque", ["Modelo"] + TAMANHOS_PADRAO),
        "ped": ler("Pedidos", ["Data", "Cliente", "Resumo", "Valor Total", "Status Pagto"]),
        "cli": ler("Clientes", ["Nome", "Loja", "Cidade", "Telefone"]),
        "ins": ler("Insumos", ["Data", "Descricao", "Valor"]),
        "aqui": ler("Aquisicoes", ["Data", "Resumo", "Valor Total"])
    }

d = carregar_dados()
df_estoque = d["est"].sort_values("Modelo")
df_pedidos, df_clientes = d["ped"], d["cli"].sort_values("Nome")
df_insumos, df_aquisicoes = d["ins"], d["aqui"]

def salvar_full(aba, df_novo, df_antigo):
    if len(df_antigo) > 1 and len(df_novo) <= 1:
        st.error("🚨 BLOQUEIO DE SEGURANÇA: Falha na leitura detectada. Tente salvar novamente em 10s.")
        return
    conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_novo.astype(str).replace('nan', ''))
    st.cache_data.clear()
    st.rerun()

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("💳 Financeiro")
    if not df_pedidos.empty:
        p = df_pedidos[df_pedidos['Status Pagto'].str.contains("Pendente", na=False)]
        st.warning(f"Total Fiado: R$ {p['Valor Total'].apply(limpar_valor).sum():.2f}")
    st.header("⚠️ Estoque Crítico")
    for _, r in df_estoque.iterrows():
        b = [f"{t}" for t in TAMANHOS_PADRAO if (int(float(r[t])) if r[t]!="" else 0) <= 2]
        if b: st.error(f"{r['Modelo']}: {b}")

# --- ABAS ---
tabs = st.tabs(["📊 Estoque", "✨ Novo Modelo", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato"])

with tabs[0]: # Estoque Completo
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.subheader("Entrada")
        m = st.selectbox("Modelo", df_estoque['Modelo'].unique())
        t = st.selectbox("Tamanho", TAMANHOS_PADRAO)
        q = st.number_input("Qtd", min_value=1)
        v = st.number_input("Custo Unit R$", min_value=0.0)
        if st.button("Salvar Entrada"):
            df_atu = df_estoque.copy()
            idx = df_atu.index[df_atu['Modelo'] == m][0]
            df_atu.at[idx, t] = int(float(df_atu.at[idx, t])) + q
            salvar_full("Estoque", df_atu, df_estoque)
            salvar_full("Aquisicoes", pd.concat([df_aquisicoes, pd.DataFrame([{"Data": get_data_hora(), "Resumo": f"{m}({t}x{q})", "Valor Total": q*v}])]), df_aquisicoes)
    with c2: st.dataframe(df_estoque, hide_index=True)

with tabs[1]: # Novo Modelo
    with st.form("nm"):
        n_m = st.text_input("Nome Modelo")
        if st.form_submit_button("Cadastrar"):
            novo = {"Modelo": n_m}; novo.update({tam: 0 for tam in TAMANHOS_PADRAO})
            salvar_full("Estoque", pd.concat([df_estoque, pd.DataFrame([novo])]), df_estoque)

with tabs[2]: # Vendas com Carrinho
    c1, c2 = st.columns(2)
    with c1:
        v_c = st.selectbox("Cliente", list(df_clientes['Nome'].unique()) + ["Avulso"])
        v_m = st.selectbox("Modelo ", df_estoque['Modelo'].unique())
        v_t = st.selectbox("Tam ", TAMANHOS_PADRAO)
        v_p = st.number_input("Preço R$ ", min_value=0.0)
        v_q = st.number_input("Qtd ", min_value=1)
        if st.button("➕ Adicionar"):
            if 'cart' not in st.session_state: st.session_state.cart = []
            st.session_state.cart.append({"Mod": v_m, "Tam": v_t, "Qtd": v_q, "Pre": v_p})
    with c2:
        if 'cart' in st.session_state and st.session_state.cart:
            tot, res = 0, []
            for i, it in enumerate(st.session_state.cart):
                st.write(f"{it['Mod']} {it['Tam']} x{it['Qtd']}")
                tot += it['Pre']*it['Qtd']; res.append(f"{it['Mod']}({it['Tam']}x{it['Qtd']})")
            v_s = st.radio("Status", ["Pago", "Pendente"])
            if st.button("Finalizar Venda"):
                df_e = df_estoque.copy()
                for it in st.session_state.cart:
                    idx = df_e.index[df_e['Modelo'] == it['Mod']][0]
                    df_e.at[idx, it['Tam']] = int(float(df_e.at[idx, it['Tam']])) - it['Qtd']
                salvar_full("Estoque", df_e, df_estoque)
                salvar_full("Pedidos", pd.concat([df_pedidos, pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_c, "Resumo": " | ".join(res), "Valor Total": tot, "Status Pagto": v_s}])]), df_pedidos)
                st.session_state.cart = []; st.rerun()

with tabs[4]: # Clientes Completo
    with st.form("fc"):
        st.subheader("Novo Cliente")
        col1, col2 = st.columns(2)
        n = col1.text_input("Nome")
        l = col2.text_input("Loja")
        ci = col1.text_input("Cidade")
        te = col2.text_input("Telefone")
        if st.form_submit_button("Salvar Cliente"):
            salvar_full("Clientes", pd.concat([df_clientes, pd.DataFrame([{"Nome": n, "Loja": l, "Cidade": ci, "Telefone": te}])]), df_clientes)
    st.dataframe(df_clientes, hide_index=True)

with tabs[5]: # Extrato com PDF e Lixeira
    if not df_pedidos.empty:
        for idx, r in df_pedidos.sort_index(ascending=False).iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([0.1, 0.1, 0.1, 0.7])
                if c1.button("🗑️", key=f"d_{idx}"): salvar_full("Pedidos", df_pedidos.drop(idx), df_pedidos)
                if "Pendente" in str(r['Status Pagto']) and c2.button("✅", key=f"p_{idx}"):
                    df_u = df_pedidos.copy(); df_u.loc[idx, 'Status Pagto'] = "Pago"
                    salvar_full("Pedidos", df_u, df_pedidos)
                c3.download_button("📄", gerar_recibo(r), f"recibo_{idx}.pdf", key=f"f_{idx}")
                st.write(f"**{r['Data']}** | {r['Cliente']} | {r['Resumo']} | **R$ {r['Valor Total']}**")
