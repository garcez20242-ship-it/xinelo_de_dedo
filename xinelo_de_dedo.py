import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import io
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Xinelo de Dedo v5.2", layout="wide", page_icon="🩴")

# --- TÍTULO ---
st.title("🩴 Gestão Xinelo de Dedo v5.2")
st.markdown("---")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- FUNÇÕES AUXILIARES ---
def get_data_hora():
    return (datetime.now() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")

def limpar_valor(valor):
    try:
        if pd.isna(valor) or str(valor).strip() == "": return 0.0
        v = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
        return float(v)
    except: return 0.0

def gerar_recibo(dados_venda):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(190, 10, "RECIBO DE VENDA - XINELO DE DEDO", ln=True, align="C")
        pdf.ln(5)
        pdf.set_font("Arial", "", 12)
        pdf.cell(190, 8, f"Data/Hora: {dados_venda.get('Data', 'N/A')}", ln=True)
        pdf.cell(190, 8, f"Cliente: {dados_venda.get('Cliente', 'N/A')}", ln=True)
        pdf.cell(190, 8, f"Status: {dados_venda.get('Status Pagto', 'N/A')}", ln=True)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(190, 8, "Itens do Pedido:", ln=True)
        resumo = str(dados_venda.get('Resumo', '')).replace(" | ", "\n")
        pdf.set_font("Arial", "", 11)
        pdf.multi_cell(190, 8, resumo)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(190, 10, f"VALOR TOTAL: R$ {limpar_valor(dados_venda.get('Valor Total', 0)):.2f}", ln=True, align="R")
        return pdf.output(dest='S').encode('latin-1')
    except: return b""

# --- CONEXÃO E CARREGAMENTO ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=10)
def carregar_dados():
    def ler_aba(aba, colunas_alvo):
        try:
            df = conn.read(spreadsheet=URL_PLANILHA, worksheet=aba, ttl="0s")
            if df is not None and not df.empty:
                df = df.dropna(how='all').loc[:, ~df.columns.str.contains('^Unnamed')]
                df.columns = df.columns.str.strip()
                return df
            return pd.DataFrame(columns=colunas_alvo)
        except: return pd.DataFrame(columns=colunas_alvo)

    return {
        "est": ler_aba("Estoque", ["Modelo"] + TAMANHOS_PADRAO),
        "ped": ler_aba("Pedidos", ["Data", "Cliente", "Resumo", "Valor Total", "Status Pagto", "Forma"]),
        "cli": ler_aba("Clientes", ["Nome", "Loja", "Cidade", "Telefone"]),
        "ins": ler_aba("Insumos", ["Data", "Descricao", "Valor"]),
        "lem": ler_aba("Lembretes", ["Nome", "Data", "Valor"]),
        "his": ler_aba("Historico_Precos", ["Data", "Modelo", "Preco_Unit"]),
        "aqui": ler_aba("Aquisicoes", ["Data", "Resumo", "Valor Total"])
    }

dados = carregar_dados()
df_estoque = dados["est"].sort_values("Modelo") # ORDENAÇÃO ALFABÉTICA AQUI
df_pedidos, df_clientes = dados["ped"], dados["cli"].sort_values("Nome")
df_insumos, df_lembretes, df_hist_precos, df_aquisicoes = dados["ins"], dados["lem"], dados["his"], dados["aqui"]

def salvar(aba, df_novo, df_antigo):
    if not df_antigo.empty and df_novo.empty:
        st.error("Erro de leitura. Tente novamente.")
        return
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_novo.astype(str).replace('nan', ''))
        st.cache_data.clear()
        st.success("✅ Salvo!")
        time.sleep(0.5)
        st.rerun()
    except Exception as e:
        st.error(f"Erro: {e}")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("🔄 Sistema")
    if st.button("Forçar Atualização Geral"):
        st.cache_data.clear()
        st.rerun()
    
    st.divider()
    st.header("💳 Painel Financeiro")
    if not df_pedidos.empty:
        pend = df_pedidos[df_pedidos['Status Pagto'].str.contains("Pendente", case=False, na=False)]
        if not pend.empty:
            st.warning(f"**Fiado: R$ {pend['Valor Total'].apply(limpar_valor).sum():.2f}**")
            for c, v in pend.groupby('Cliente')['Valor Total'].apply(lambda x: x.apply(limpar_valor).sum()).items():
                st.caption(f"👤 {c}: R$ {v:.2f}")
    
    st.divider()
    st.header("⚠️ Alertas de Estoque")
    tem_alerta = False
    for _, row in df_estoque.iterrows():
        baixos = [f"{t}({int(float(row[t]))})" for t in TAMANHOS_PADRAO if (int(float(row[t])) if row[t] != "" else 0) <= 3]
        if baixos:
            st.error(f"**{row['Modelo']}**\n{', '.join(baixos)}")
            tem_alerta = True
    if not tem_alerta: st.success("Estoque OK.")

# --- ABAS ---
tabs = st.tabs(["📊 Estoque", "✨ Novo Modelo", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato", "📅 Lembretes", "📈 Preços"])

# 1. ESTOQUE (ORDEM ALFABÉTICA)
with tabs[0]:
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.subheader("📦 Entrada")
        if not df_estoque.empty:
            m_ent = st.selectbox("Modelo", df_estoque['Modelo'].unique())
            t_ent = st.selectbox("Tamanho", TAMANHOS_PADRAO)
            q_ent = st.number_input("Quantidade", min_value=1)
            c_ent = st.number_input("Custo Unitário R$", min_value=0.0)
            if st.button("Confirmar Entrada"):
                df_atu = df_estoque.copy()
                idx = df_atu.index[df_atu['Modelo'] == m_ent][0]
                df_atu.at[idx, t_ent] = int(float(df_atu.at[idx, t_ent])) + q_ent
                # Salva o estoque primeiro para garantir a entrada
                salvar("Estoque", df_atu, df_estoque)
                # O sistema salvará histórico e aquisições na próxima ação ou você pode adicionar aqui
    with c2:
        st.subheader("📋 Inventário (A-Z)")
        st.dataframe(df_estoque, hide_index=True)

# 2. NOVO MODELO
with tabs[1]:
    with st.form("n_mod"):
        n_m = st.text_input("Nome do Modelo")
        if st.form_submit_button("Cadastrar"):
            if n_m:
                novo = {"Modelo": n_m}; novo.update({t: 0 for t in TAMANHOS_PADRAO})
                salvar("Estoque", pd.concat([df_estoque, pd.DataFrame([novo])], ignore_index=True), df_estoque)

# 3. VENDAS
with tabs[2]:
    c1, c2 = st.columns(2)
    with c1:
        v_cli = st.selectbox("Cliente", list(df_clientes['Nome'].unique()) + ["Avulso"])
        v_mod = st.selectbox("Modelo ", df_estoque['Modelo'].unique())
        v_tam = st.selectbox("Tam ", TAMANHOS_PADRAO)
        v_pre = st.number_input("Preço R$", min_value=0.0)
        v_qtd = st.number_input("Qtd ", min_value=1)
        if st.button("🛒 Adicionar"):
            if 'cart' not in st.session_state: st.session_state.cart = []
            st.session_state.cart.append({"Mod": v_mod, "Tam": v_tam, "Qtd": v_qtd, "Pre": v_pre})
            st.rerun()
    with c2:
        if 'cart' in st.session_state and st.session_state.cart:
            t_v, r_v = 0, []
            for i, it in enumerate(st.session_state.cart):
                st.write(f"**{it['Mod']} ({it['Tam']})** x{it['Qtd']} = R$ {it['Pre']*it['Qtd']:.2f}")
                t_v += it['Pre']*it['Qtd']; r_v.append(f"{it['Mod']}({it['Tam']}x{it['Qtd']})")
            v_st = st.radio("Status", ["Pago", "Pendente"], horizontal=True)
            if st.button("Finalizar Venda"):
                df_e = df_estoque.copy()
                for it in st.session_state.cart:
                    idx = df_e.index[df_e['Modelo'] == it['Mod']][0]
                    df_e.at[idx, it['Tam']] = int(float(df_e.at[idx, it['Tam']])) - it['Qtd']
                salvar("Estoque", df_e, df_estoque)
                salvar("Pedidos", pd.concat([df_pedidos, pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cli, "Resumo": " | ".join(r_v), "Valor Total": t_v, "Status Pagto": v_st, "Forma": "Pix"}])], ignore_index=True), df_pedidos)
                st.session_state.cart = []; st.rerun()

# 5. CLIENTES
with tabs[4]:
    with st.form("f_cli"):
        n_c = st.text_input("Nome"); l_c = st.text_input("Loja"); c_c = st.text_input("Cidade"); t_c = st.text_input("WhatsApp")
        if st.form_submit_button("Salvar Cliente"):
            salvar("Clientes", pd.concat([df_clientes, pd.DataFrame([{"Nome": n_c, "Loja": l_c, "Cidade": c_c, "Telefone": t_c}])], ignore_index=True), df_clientes)
    st.dataframe(df_clientes.sort_values("Nome"), hide_index=True)

# 6. EXTRATO
with tabs[5]:
    vendas = df_pedidos.assign(Tipo="Venda", Ori="Pedidos")
    if not vendas.empty:
        vendas['DT'] = pd.to_datetime(vendas['Data'], dayfirst=True, errors='coerce')
        for idx, r in vendas.sort_values('DT', ascending=False).iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([0.1, 0.1, 0.8])
                if c1.button("🗑️", key=f"d_{idx}"):
                    salvar("Pedidos", df_pedidos[df_pedidos['Data'] != r['Data']], df_pedidos)
                if "Pendente" in str(r['Status Pagto']) and c2.button("✅", key=f"p_{idx}"):
                    df_p = df_pedidos.copy()
                    df_p.loc[df_p['Data'] == r['Data'], 'Status Pagto'] = "Pago"
                    salvar("Pedidos", df_p, df_pedidos)
                st.write(f"**{r['Data']}** | {r['Cliente']} | {r['Resumo']} | **R$ {limpar_valor(r['Valor Total']):.2f}**")
