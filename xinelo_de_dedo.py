import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Xinelo v6.1", layout="wide", page_icon="🩴")

# --- TÍTULO ---
st.title("🩴 Gestão Xinelo de Dedo v6.1 - Sistema Completo")
st.markdown("---")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- FUNÇÕES DE APOIO ---
def get_data_hora():
    return (datetime.now() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")

def limpar_valor(valor):
    try:
        if pd.isna(valor) or str(valor).strip() == "": return 0.0
        v = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
        return float(v)
    except: return 0.0

def gerar_recibo(r):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(190, 10, "RECIBO DE VENDA", ln=True, align="C")
        pdf.ln(5)
        pdf.set_font("Arial", "", 12)
        pdf.cell(190, 8, f"Data: {r['Data']}", ln=True)
        pdf.cell(190, 8, f"Cliente: {r['Cliente']}", ln=True)
        pdf.ln(5)
        pdf.multi_cell(190, 8, f"Resumo dos Itens:\n{r['Resumo']}")
        pdf.ln(5)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(190, 10, f"TOTAL: R$ {limpar_valor(r['Valor Total']):.2f}", ln=True, align="R")
        return pdf.output(dest='S').encode('latin-1')
    except: return b""

# --- CONEXÃO ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=5)
def carregar_dados():
    def ler(aba, cols):
        try:
            df = conn.read(spreadsheet=URL_PLANILHA, worksheet=aba, ttl="0s")
            if df is not None and not df.empty:
                df = df.dropna(how='all').loc[:, ~df.columns.str.contains('^Unnamed')]
                df.columns = df.columns.str.strip()
                return df
            return pd.DataFrame(columns=cols)
        except: return pd.DataFrame(columns=cols)
    
    return {
        "est": ler("Estoque", ["Modelo"] + TAMANHOS_PADRAO),
        "ped": ler("Pedidos", ["Data", "Cliente", "Resumo", "Valor Total", "Status Pagto"]),
        "cli": ler("Clientes", ["Nome", "Loja", "Cidade", "Telefone"]),
        "ins": ler("Insumos", ["Data", "Descricao", "Valor"]),
        "lem": ler("Lembretes", ["Data", "Nome", "Valor"]),
        "aqui": ler("Aquisicoes", ["Data", "Resumo", "Valor Total"])
    }

d = carregar_dados()
df_estoque = d["est"].sort_values("Modelo") if not d["est"].empty else d["est"]
df_pedidos, df_clientes = d["ped"], d["cli"].sort_values("Nome") if not d["cli"].empty else d["cli"]
df_insumos, df_lembretes, df_aquisicoes = d["ins"], d["lem"], d["aqui"]

def salvar_blindado(aba, df_novo, df_antigo):
    if len(df_antigo) > 1 and len(df_novo) <= 1:
        st.error("🚨 BLOQUEIO: Falha de sincronização. Tente novamente em 10s.")
        return False
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_novo.astype(str).replace('nan', ''))
        st.cache_data.clear()
        st.success("✅ Sincronizado!")
        time.sleep(1)
        st.rerun()
    except Exception as e: st.error(f"Erro: {e}")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("🔄 Sistema")
    if st.button("Forçar Atualização"):
        st.cache_data.clear(); st.rerun()
    
    st.divider()
    st.header("💳 Fiados")
    if not df_pedidos.empty:
        p = df_pedidos[df_pedidos['Status Pagto'].str.contains("Pendente", case=False, na=False)]
        if not p.empty:
            st.warning(f"**Total: R$ {p['Valor Total'].apply(limpar_valor).sum():.2f}**")
            for c, v in p.groupby('Cliente')['Valor Total'].apply(lambda x: x.apply(limpar_valor).sum()).items():
                st.caption(f"👤 {c}: R$ {v:.2f}")

    st.divider()
    st.header("⚠️ Estoque Baixo")
    for _, r in df_estoque.iterrows():
        criticos = [f"{t}({int(float(r[t]))})" for t in TAMANHOS_PADRAO if (int(float(r[t])) if r[t]!="" else 0) <= 3]
        if criticos: st.error(f"**{r['Modelo']}**\n{', '.join(criticos)}")

# --- ABAS ---
tabs = st.tabs(["📊 Estoque", "✨ Novo Modelo", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato", "📅 Lembretes"])

with tabs[0]: # 1. ESTOQUE
    st.subheader("📋 Inventário A-Z")
    c1, c2 = st.columns([1, 2])
    with c1:
        st.write("**Entrada de Mercadoria**")
        m_e = st.selectbox("Escolha o Modelo", df_estoque['Modelo'].unique()) if not df_estoque.empty else None
        t_e = st.selectbox("Escolha o Tamanho", TAMANHOS_PADRAO)
        q_e = st.number_input("Qtd", min_value=1)
        v_e = st.number_input("Custo Unit R$", min_value=0.0)
        if st.button("Registrar Entrada") and m_e:
            df_e = df_estoque.copy()
            idx = df_e.index[df_e['Modelo'] == m_e][0]
            df_e.at[idx, t_e] = int(float(df_e.at[idx, t_e])) + q_e
            salvar_blindado("Estoque", df_e, df_estoque)
            salvar_blindado("Aquisicoes", pd.concat([df_aquisicoes, pd.DataFrame([{"Data": get_data_hora(), "Resumo": f"{m_e}({t_e}x{q_e})", "Valor Total": q_e*v_e}])]), df_aquisicoes)
    with c2: st.dataframe(df_estoque, hide_index=True)

with tabs[1]: # 2. NOVO MODELO
    with st.form("n_m"):
        n_n = st.text_input("Nome do Novo Modelo")
        if st.form_submit_button("Cadastrar"):
            if n_n:
                novo = {"Modelo": n_n}; novo.update({t: 0 for t in TAMANHOS_PADRAO})
                salvar_blindado("Estoque", pd.concat([df_estoque, pd.DataFrame([novo])]), df_estoque)

with tabs[2]: # 3. VENDAS
    c1, c2 = st.columns(2)
    with c1:
        v_c = st.selectbox("Cliente", list(df_clientes['Nome'].unique()) + ["Avulso"])
        v_m = st.selectbox("Modelo ", df_estoque['Modelo'].unique())
        v_t = st.selectbox("Tam ", TAMANHOS_PADRAO)
        v_p = st.number_input("Preço R$ ", min_value=0.0)
        v_q = st.number_input("Qtd ", min_value=1)
        if st.button("➕ Adicionar"):
            if 'c' not in st.session_state: st.session_state.c = []
            st.session_state.c.append({"Mod": v_m, "Tam": v_t, "Qtd": v_q, "Pre": v_p})
            st.rerun()
    with c2:
        if 'c' in st.session_state and st.session_state.c:
            tot, res = 0, []
            for i, it in enumerate(st.session_state.c):
                st.write(f"**{it['Mod']} {it['Tam']}** x{it['Qtd']} - R$ {it['Pre']*it['Qtd']:.2f}")
                if st.button("🗑️", key=f"c_{i}"): st.session_state.c.pop(i); st.rerun()
                tot += it['Pre']*it['Qtd']; res.append(f"{it['Mod']}({it['Tam']}x{it['Qtd']})")
            v_s = st.radio("Status", ["Pago", "Pendente"], horizontal=True)
            if st.button("🚀 Finalizar Venda", type="primary"):
                df_e = df_estoque.copy()
                for it in st.session_state.c:
                    idx = df_e.index[df_e['Modelo'] == it['Mod']][0]
                    df_e.at[idx, it['Tam']] = int(float(df_e.at[idx, it['Tam']])) - it['Qtd']
                salvar_blindado("Estoque", df_e, df_estoque)
                salvar_blindado("Pedidos", pd.concat([df_pedidos, pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_c, "Resumo": " | ".join(res), "Valor Total": tot, "Status Pagto": v_s}])]), df_pedidos)
                st.session_state.c = []; st.rerun()

with tabs[3]: # 4. INSUMOS
    with st.form("f_i"):
        desc_i = st.text_input("Gasto"); val_i = st.number_input("Valor R$", min_value=0.0)
        if st.form_submit_button("Salvar Gasto"):
            salvar_blindado("Insumos", pd.concat([df_insumos, pd.DataFrame([{"Data": get_data_hora(), "Descricao": desc_i, "Valor": val_i}])]), df_insumos)
    st.dataframe(df_insumos, hide_index=True)

with tabs[4]: # 5. CLIENTES
    with st.form("f_cl"):
        n = st.text_input("Nome"); l = st.text_input("Loja"); ci = st.text_input("Cidade"); t = st.text_input("WhatsApp")
        if st.form_submit_button("Cadastrar"):
            salvar_blindado("Clientes", pd.concat([df_clientes, pd.DataFrame([{"Nome": n, "Loja": l, "Cidade": ci, "Telefone": t}])]), df_clientes)
    st.dataframe(df_clientes, hide_index=True)

with tabs[5]: # 6. EXTRATO
    if not df_pedidos.empty:
        for idx, r in df_pedidos.sort_index(ascending=False).iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([0.1, 0.1, 0.1, 0.7])
                if c1.button("🗑️", key=f"d_{idx}"): salvar_blindado("Pedidos", df_pedidos.drop(idx), df_pedidos)
                if "Pendente" in str(r['Status Pagto']) and c2.button("✅", key=f"p_{idx}"):
                    df_up = df_pedidos.copy(); df_up.loc[idx, 'Status Pagto'] = "Pago"
                    salvar_blindado("Pedidos", df_up, df_pedidos)
                c3.download_button("📄", gerar_recibo(r), f"recibo_{idx}.pdf", key=f"pdf_{idx}")
                st.write(f"**{r['Data']}** | {r['Cliente']} | {r['Resumo']} | **R$ {limpar_valor(r['Valor Total']):.2f}**")

with tabs[6]: # 7. LEMBRETES
    with st.form("f_l"):
        t_l = st.text_input("Título"); v_l = st.number_input("Valor R$ ", min_value=0.0)
        if st.form_submit_button("Agendar"):
            salvar_blindado("Lembretes", pd.concat([df_lembretes, pd.DataFrame([{"Data": get_data_hora(), "Nome": t_l, "Valor": v_l}])]), df_lembretes)
    st.dataframe(df_lembretes, hide_index=True)
