import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão de Sandálias Nuvem", layout="wide", page_icon="👡")

# --- CONEXÃO DIRETA COM A PLANILHA ---
# Link limpo para evitar Erro 400
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1ZLN9wcg89UBcBZrViLmuAK-fU9GtMEMgNlGk7F6VVUs/edit"

# Tamanhos atualizados para usar hífen conforme sua planilha
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # ttl=0 garante que o app sempre busque dados novos e não use cache com erro
    df_estoque = conn.read(spreadsheet=URL_PLANILHA, worksheet="Estoque", ttl=0)
    df_pedidos = conn.read(spreadsheet=URL_PLANILHA, worksheet="Pedidos", ttl=0)
    df_clientes = conn.read(spreadsheet=URL_PLANILHA, worksheet="Clientes", ttl=0)
except Exception as e:
    st.error("### ❌ Erro de Conexão")
    st.write(f"Detalhe técnico: {e}")
    st.info("Dica: Verifique se as abas na planilha se chamam exatamente: Estoque, Pedidos e Clientes.")
    st.stop()

# --- SIDEBAR (ALERTAS DE ESTOQUE BAIXO) ---
with st.sidebar:
    st.header("🔔 Alertas")
    alertas = []
    # Verifica se há menos de 3 unidades em qualquer tamanho
    for index, row in df_estoque.iterrows():
        for tam in TAMANHOS_PADRAO:
            if tam in row:
                qtd = pd.to_numeric(row[tam], errors='coerce')
                if qtd < 3:
                    alertas.append(f"{row['Modelo']} ({tam}): {int(qtd) if not pd.isna(qtd) else 0} un")
    
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
        # Converte para int para garantir que o cálculo funcione
        atual = int(pd.to_numeric(df_estoque.at[idx, tam_rep], errors='coerce') or 0)
        df_estoque.at[idx, tam_rep] = atual + qtd_rep
        conn.update(spreadsheet=URL_PLANILHA, worksheet="Estoque", data=df_estoque)
        st.success("Estoque atualizado!")
        st.rerun()
