import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão de Sandálias Nuvem", layout="wide", page_icon="👡")

# --- CONEXÃO DIRETA COM A NOVA PLANILHA ---
# Link da sua nova planilha atualizada
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"

# Padrão de tamanhos com hífen (-)
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

@st.cache_data(ttl=0)
def carregar_dados():
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Tenta ler as abas. Se a aba não existir, ele cria um DataFrame vazio para não travar o app.
    try:
        estoque = conn.read(spreadsheet=URL_PLANILHA, worksheet="Estoque", ttl=0).dropna(how='all')
    except:
        # Caso a aba ainda se chame "Página1", ele tenta ler a primeira aba disponível
        estoque = conn.read(spreadsheet=URL_PLANILHA, ttl=0).dropna(how='all')
    
    try:
        pedidos = conn.read(spreadsheet=URL_PLANILHA, worksheet="Pedidos", ttl=0).dropna(how='all')
    except:
        pedidos = pd.DataFrame(columns=["Data", "Cliente", "Telefone", "Loja", "Cidade", "Item", "Qtd"])
        
    try:
        clientes = conn.read(spreadsheet=URL_PLANILHA, worksheet="Clientes", ttl=0).dropna(how='all')
    except:
        clientes = pd.DataFrame(columns=["Nome", "Loja", "Telefone", "Cidade"])
    
    # Limpeza de cabeçalhos
    estoque.columns = estoque.columns.str.strip()
    pedidos.columns = pedidos.columns.str.strip()
    clientes.columns = clientes.columns.str.strip()
    
    return conn, estoque, pedidos, clientes

try:
    conn, df_estoque, df_pedidos, df_clientes = carregar_dados()
except Exception as e:
    st.error(f"### ❌ Erro ao conectar na nova planilha")
    st.write(f"Detalhe técnico: {e}")
    st.stop()

# --- INTERFACE PRINCIPAL ---
st.title("👡 Sistema de Gestão - Estoque Xinelo de Dedo")
abas = st.tabs(["📊 Estoque", "🛒 Nova Venda", "👥 Clientes", "📜 Histórico", "✨ Cadastro Modelos"])

# --- ABA 1: ESTOQUE ---
with abas[0]:
    st.subheader("Disponibilidade Atual")
    if not df_estoque.empty:
        st.dataframe(df_estoque, use_container_width=True, hide_index=True)
    else:
        st.info("O estoque está vazio. Vá na aba 'Cadastro Modelos' para começar.")

# --- ABA 5: CADASTRO MODELOS (Essencial para começar a nova planilha) ---
with abas[4]:
    st.subheader("✨ Cadastrar Primeiro Modelo")
    with st.form("novo_m"):
        nome_m = st.text_input("Nome do Modelo")
        cols = st.columns(5)
        q_ini = {}
        for i, t in enumerate(TAMANHOS_PADRAO):
            q_ini[t] = cols[i%5].number_input(f"Tam {t}", min_value=0, step=1)
        
        if st.form_submit_button("Salvar na Planilha 💾"):
            if nome_m:
                linha = {"Modelo": nome_m}
                linha.update(q_ini)
                df_atualizado
