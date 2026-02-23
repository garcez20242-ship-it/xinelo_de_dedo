import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestão de Sandálias Nuvem", layout="wide", page_icon="👡")

TAMANHOS_PADRAO = ["25/26", "27/28", "29/30", "31/32", "33/34", "35/36", "37/38", "39/40", "41/42", "43/44"]

# --- CONEXÃO GOOGLE SHEETS ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_estoque = conn.read(worksheet="Estoque", ttl=0)
    df_pedidos = conn.read(worksheet="Pedidos", ttl=0)
    df_clientes = conn.read(worksheet="Clientes", ttl=0) # Nova aba de clientes
except Exception as e:
    st.error("Erro de Conexão: Configure o link da planilha nos Secrets do Streamlit Cloud.")
    st.stop()

# --- SIDEBAR (ALERTAS) ---
with st.sidebar:
    st.header("🔔 Alertas de Estoque")
    alertas = []
    for index, row in df_estoque.iterrows():
        for tam in TAMANHOS_PADRAO:
            if tam in row and row[tam] < 3:
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
        df_estoque.at[idx, tam_rep] += qtd_rep
        conn.update(worksheet="Estoque", data=df_estoque)
        st.success("Estoque atualizado!")
        st.rerun()

# --- ABA 2: VENDA (COM DROPDOWN DE CLIENTES) ---
with abas[1]:
    st.subheader("📝 Registrar Pedido")
    
    if df_clientes.empty:
        st.warning("Cadastre um cliente na aba 'Clientes' antes de realizar uma venda.")
    else:
        # Seleção de Cliente via Dropdown
        cliente_selecionado = st.selectbox("Selecionar Cliente", df_clientes['Nome'].unique())
        
        # Puxa os dados automáticos do cliente selecionado
        dados_c = df_clientes[df_clientes['Nome'] == cliente_selecionado].iloc[0]
        st.info(f"📍 **Loja:** {dados_c['Loja']} | **Cidade:** {dados_c['Cidade']} | **Tel:** {dados_c['Telefone']}")

        st.divider()
        
        if 'carrinho' not in st.session_state:
            st.session_state.carrinho = []

        st.write("### 🛒 Carrinho")
        i1, i2, i3, i4 = st.columns([3, 2, 2, 1])
        mod_v = i1.selectbox("Escolher Modelo", df_estoque['Modelo'].unique())
        tam_v = i2.selectbox("Escolher Tamanho", TAMANHOS_PADRAO, key="v_t")
        qtd_v = i3.number_input("Qtd", min_value=1, step=1, key="v_q")

        if i4.button("Adicionar ➕"):
            estoque_atual = df_estoque.loc[df_estoque['Modelo'] == mod_v, tam_v].values[0]
            if estoque_atual >= qtd_v:
                st.session_state.carrinho.append({"modelo": mod_v, "tamanho": tam_v, "quantidade": qtd_v})
                st.toast(f"{mod_v} adicionado!")
            else:
                st.error(f"Estoque insuficiente! Disponível: {estoque_atual}")

        if st.session_state.carrinho:
            st.write("---")
            for idx, item in enumerate(st.session_state.carrinho):
                st.write(f"🔹 {item['quantidade']}x {item['modelo']} (Tam: {item['tamanho']})")
            
            if st.button("FINALIZAR VENDA ✅", type="primary"):
                data_v = datetime.now().strftime("%d/%m/%Y %H:%M")
                novos_pedidos = []
                
                for item in st.session_state.carrinho:
                    # 1. Baixa no Estoque
                    idx_e = df_estoque.index[df_estoque['Modelo'] == item['modelo']][0]
                    df_estoque.at[idx_e, item['tamanho']] -= item['quantidade']
                    
                    # 2. Registro do Pedido (usa dados do dropdown)
                    novos_pedidos.append({
                        "Data": data_v, 
                        "Cliente": cliente_selecionado, 
                        "Telefone": dados_c['Telefone'],
                        "Loja": dados_c['Loja'], 
                        "Cidade": dados_c['Cidade'],
                        "Item": f"{item['modelo']} ({item['tamanho']})", 
                        "Qtd": item['quantidade']
                    })
                
                df_novos_p = pd.DataFrame(novos_pedidos)
                df_pedidos_fim = pd.concat([df_pedidos, df_novos_p], ignore_index=True)
                
                conn.update(worksheet="Estoque", data=df_estoque)
                conn.update(worksheet="Pedidos", data=df_pedidos_fim)
                
                st.session_state.carrinho = []
                st.success("Venda salva com sucesso!")
                st.rerun()

# --- ABA 3: CADASTRO DE CLIENTES ---
with abas[2]:
    st.subheader("👥 Cadastro de Clientes")