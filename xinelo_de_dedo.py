import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão de Sandálias Nuvem", layout="wide", page_icon="👡")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

@st.cache_data(ttl=0)
def carregar_dados():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        estoque = conn.read(spreadsheet=URL_PLANILHA, worksheet="Estoque", ttl=0).dropna(how='all')
    except:
        estoque = pd.DataFrame(columns=["Modelo", "Imagem"] + TAMANHOS_PADRAO)
    try:
        pedidos = conn.read(spreadsheet=URL_PLANILHA, worksheet="Pedidos", ttl=0).dropna(how='all')
    except:
        pedidos = pd.DataFrame(columns=["Data", "Cliente", "Resumo do Pedido"])
    try:
        clientes = conn.read(spreadsheet=URL_PLANILHA, worksheet="Clientes", ttl=0).dropna(how='all')
    except:
        clientes = pd.DataFrame(columns=["Nome", "Loja", "Telefone", "Cidade"])
    
    for df in [estoque, pedidos, clientes]:
        df.columns = df.columns.str.strip()
    return conn, estoque, pedidos, clientes

conn, df_estoque, df_pedidos, df_clientes = carregar_dados()

# --- FUNÇÃO AUXILIAR PARA SALVAR ---
def atualizar_planilha(aba, dataframe):
    df_limpo = dataframe.astype(str)
    df_limpo = df_limpo.loc[:, ~df_limpo.columns.str.contains('^Unnamed')]
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_limpo)
        st.cache_data.clear()
        st.success("Dados salvos!")
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}. Verifique se a planilha está como 'Editor' para quem tem o link.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔔 Alertas")
    alertas = []
    for _, row in df_estoque.iterrows():
        for tam in TAMANHOS_PADRAO:
            qtd = pd.to_numeric(row[tam], errors='coerce')
            if not pd.isna(qtd) and qtd < 3:
                alertas.append(f"{row['Modelo']} ({tam}): {int(qtd)} un")
    if alertas:
        for a in alertas: st.warning(a)
    else:
        st.success("Estoque em dia.")

st.title("👡 Gestão Xinelo de Dedo")
abas = st.tabs(["📊 Estoque e Edição", "🛒 Nova Venda", "👥 Clientes", "📜 Histórico", "✨ Cadastro"])

# --- ABA 1: ESTOQUE ---
with abas[0]:
    st.subheader("Gerenciar Inventário")
    if df_estoque.empty:
        st.info("Nenhum modelo cadastrado.")
    else:
        for index, row in df_estoque.iterrows():
            with st.expander(f"📦 {row['Modelo']}"):
                col1, col2, col3, col4 = st.columns([1, 2, 1, 1])
                if pd.notna(row['Imagem']) and str(row['Imagem']).startswith('http'):
                    col1.image(row['Imagem'], width=100)
                
                novo_n = col2.text_input("Renomear", value=row['Modelo'], key=f"edit_m_{index}")
                if col3.button("Salvar ✅", key=f"sv_m_{index}"):
                    df_estoque.at[index, 'Modelo'] = novo_n
                    atualizar_planilha("Estoque", df_estoque)
                if col4.button("Excluir 🗑️", key=f"del_m_{index}"):
                    df_estoque = df_estoque.drop(index)
                    atualizar_planilha("Estoque", df_estoque)
                
                edit_q = st.data_editor(row[TAMANHOS_PADRAO].to_frame().T, key=f"ed_q_{index}")
                if st.button("Atualizar Qtd 🔄", key=f"bq_{index}"):
                    for t in TAMANHOS_PADRAO:
                        df_estoque.at[index, t] = edit_q.at[0, t]
                    atualizar_planilha("Estoque", df_estoque)

# --- ABA 2: NOVA VENDA ---
with abas[1]:
    st.subheader("📝 Registrar Venda")
    if df_clientes.empty or df_estoque.empty:
        st.warning("Cadastre clientes e modelos primeiro.")
    else:
        with st.form("venda"):
            c1, c2, c3, c4 = st.columns(4)
            cli_v = c1.selectbox("Cliente", df_clientes['Nome'].unique())
            mod_v = c2.selectbox("Modelo", df_estoque['Modelo'].unique())
            tam_v = c3.selectbox("Tamanho", TAMANHOS_PADRAO)
            qtd_v = c4.number_input("Qtd", min_value=1, step=1)
            
            if st.form_submit_button("Finalizar Venda"):
                idx_e = df_estoque.index
