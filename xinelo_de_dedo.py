import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestão de Sandálias Nuvem", layout="wide", page_icon="👡")

# LINK DIRETO DA SUA PLANILHA (Link limpo para evitar Erro 400)
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1ZLN9wcg89UBcBZrViLmuAK-fU9GtMEMgNlGk7F6VVUs/edit"

# No seu código, mude esta linha para:
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]
# --- CONEXÃO GOOGLE SHEETS ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Lendo as abas usando o link direto
    df_estoque = conn.read(spreadsheet=URL_PLANILHA, worksheet="Estoque", ttl=0)
    df_pedidos = conn.read(spreadsheet=URL_PLANILHA, worksheet="Pedidos", ttl=0)
    df_clientes = conn.read(spreadsheet=URL_PLANILHA, worksheet="Clientes", ttl=0)
except Exception as e:
    st.error(f"Erro ao acessar as abas. Verifique se os nomes 'Estoque', 'Pedidos' e 'Clientes' estão corretos na planilha. Detalhe: {e}")
    st.stop()

# --- SIDEBAR (ALERTAS) ---
with st.sidebar:
    st.header("🔔 Alertas de Estoque")
    alertas = []
    for index, row in df_estoque.iterrows():
        for tam in TAMANHOS_PADRAO:
            if tam in row and pd.to_numeric(row[tam], errors='coerce') < 3:
                alertas.append(f"{row['Modelo']} ({tam}): {row[tam]} un")
    
    if alertas:
        for a in alertas: st.warning(a)
    else:
        st.success("Estoque em dia!")

st.title("👡 Sistema de Gestão Comercial")
abas = st.tabs(["📊 Estoque", "🛒 Nova Venda", "👥 Clientes", "📜 Histórico", "✨ Cadastro Modelos"])

# --- ABA 1: ESTOQUE ---
with abas[0]:
    st.subheader("Disponibilidade em Tempo Real")
    st.dataframe(df_estoque, use_container_width=True, hide_index=True)
    
    st.divider()
    st.write("**Reposição Rápida:**")
    c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
    mod_rep = c1.selectbox("Modelo para Repor", df_estoque['Modelo'].unique())
    tam_rep = c2.selectbox("Tamanho", TAMANHOS_PADRAO, key="rep_t")
    qtd_rep = c3.number_input("Qtd", min_value=1, step=1, key="rep_q")
    
    if c4.button("Repor ✅"):
        idx = df_estoque.index[df_estoque['Modelo'] == mod_rep][0]
        df_estoque.at[idx, tam_rep] = int(df_estoque.at[idx, tam_rep]) + qtd_rep
        conn.update(spreadsheet=URL_PLANILHA, worksheet="Estoque", data=df_estoque)
        st.success("Estoque atualizado!")
        st.rerun()

# --- ABA 2: VENDA (COM DROPDOWN DE CLIENTES) ---
with abas[1]:
    st.subheader("📝 Registrar Pedido")
    
    if df_clientes.empty:
        st.warning("Cadastre um cliente na aba 'Clientes' antes de realizar uma venda.")
    else:
        cliente_selecionado = st.selectbox("Selecionar Cliente", df_clientes['Nome'].unique())
        dados_c = df_clientes[df_clientes['Nome'] == cliente_selecionado].iloc[0]
        st.info(f"📍 **Loja:** {dados_c['Loja']} | **Cidade:** {dados_c['Cidade']}")

        st.divider()
        
        if 'carrinho' not in st.session_state:
            st.session_state.carrinho = []

        st.write("### 🛒 Carrinho")
        i1, i2, i3, i4 = st.columns([3, 2, 2, 1])
        mod_v = i1.selectbox("Escolher Modelo", df_estoque['Modelo'])



