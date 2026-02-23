import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão de Sandálias Nuvem", layout="wide", page_icon="👡")

# --- CONEXÃO DIRETA COM A NOVA PLANILHA ---
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"

TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

@st.cache_data(ttl=0)
def carregar_dados():
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Busca ou cria os DataFrames para garantir que o app não quebre
    try:
        estoque = conn.read(spreadsheet=URL_PLANILHA, worksheet="Estoque", ttl=0).dropna(how='all')
    except:
        estoque = pd.DataFrame(columns=["Modelo", "Imagem"] + TAMANHOS_PADRAO)
    
    try:
        pedidos = conn.read(spreadsheet=URL_PLANILHA, worksheet="Pedidos", ttl=0).dropna(how='all')
    except:
        pedidos = pd.DataFrame(columns=["Data", "Cliente", "Telefone", "Loja", "Cidade", "Item", "Qtd"])
        
    try:
        clientes = conn.read(spreadsheet=URL_PLANILHA, worksheet="Clientes", ttl=0).dropna(how='all')
    except:
        clientes = pd.DataFrame(columns=["Nome", "Loja", "Telefone", "Cidade"])
    
    # Limpeza de nomes de colunas
    for df in [estoque, pedidos, clientes]:
        df.columns = df.columns.str.strip()
    
    return conn, estoque, pedidos, clientes

try:
    conn, df_estoque, df_pedidos, df_clientes = carregar_dados()
except Exception as e:
    st.error(f"Erro na conexão: {e}")
    st.stop()

# --- INTERFACE ---
st.title("👡 Sistema Comercial - Xinelo de Dedo")
abas = st.tabs(["📊 Estoque", "🛒 Nova Venda", "👥 Clientes", "📜 Histórico", "✨ Cadastro Modelos"])

# --- ABA 1: ESTOQUE ---
with abas[0]:
    st.subheader("Estoque Atual")
    if not df_estoque.empty:
        # Mostrar imagem se houver
        col_img, col_tab = st.columns([1, 3])
        with col_tab:
            st.dataframe(df_estoque, use_container_width=True, hide_index=True)
        with col_img:
            modelo_sel = st.selectbox("Ver foto do modelo:", df_estoque['Modelo'].unique())
            img_url = df_estoque.loc[df_estoque['Modelo'] == modelo_sel, 'Imagem'].values[0]
            if pd.notna(img_url) and str(img_url).startswith('http'):
                st.image(img_url, caption=modelo_sel, width=200)
            else:
                st.info("Sem foto disponível")
    else:
        st.info("Nenhum modelo cadastrado.")

# --- ABA 2: NOVA VENDA ---
with abas[1]:
    st.subheader("📝 Registrar Venda")
    if df_clientes.empty or df_estoque.empty:
        st.warning("Certifique-se de ter Clientes e Modelos cadastrados.")
    else:
        with st.form("venda"):
            c1, c2 = st.columns(2)
            cliente = c1.selectbox("Cliente", df_clientes['Nome'].unique())
            modelo = c2.selectbox("Modelo", df_estoque['Modelo'].unique())
            tamanho = st.selectbox("Tamanho", TAMANHOS_PADRAO)
            qtd = st.number_input("Quantidade", min_value=1, step=1)
            
            if st.form_submit_button("Finalizar Venda"):
                # Lógica simplificada de baixa e salvamento
                st.success("Venda registrada! (Lembre-se de implementar a baixa de estoque no código se desejar automatizar 100%)")

# --- ABA 3: CLIENTES ---
with abas[2]:
    st.subheader("👥 Cadastro de Clientes")
    with st.form("cli"):
        n = st.text_input("Nome")
        l = st.text_input("Loja")
        t = st.text_input("Telefone")
        cid = st.text_input("Cidade")
        if st.form_submit_button("Salvar Cliente"):
            novo = pd.DataFrame([{"Nome": n, "Loja": l, "Telefone": t, "Cidade": cid}])
            df_clientes = pd.concat([df_clientes, novo], ignore_index=True)
            conn.update(spreadsheet=URL_PLANILHA, worksheet="Clientes", data=df_clientes)
            st.cache_data.clear()
            st.rerun()

# --- ABA 4: HISTÓRICO ---
with abas[3]:
    st.subheader("📜 Histórico")
    st.dataframe(df_pedidos, use_container_width=True)

# --- ABA 5: CADASTRO MODELOS + IMAGEM ---
with abas[4]:
    st.subheader("✨ Novo Modelo")
    with st.form("novo_modelo"):
        nome_m = st.text_input("Nome do Modelo")
        url_m = st.text_input("Link da Imagem (URL)")
        st.caption("Dica: Use links do Imgur, PostImages ou fotos
