import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão de Sandálias Nuvem", layout="wide", page_icon="👡")

# --- CONEXÃO DIRETA COM A PLANILHA ---
# Link limpo (sem o ?usp=sharing) para evitar erros de API
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1ZLN9wcg89UBcBZrViLmuAK-fU9GtMEMgNlGk7F6VVUs/edit"

# Tamanhos usando hífen (-) conforme ajustamos na sua planilha
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

@st.cache_data(ttl=0) # Força a limpeza de cache toda vez que atualizar
def carregar_dados():
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Lendo as abas e removendo linhas/colunas totalmente vazias (previne erro 400)
    estoque = conn.read(spreadsheet=URL_PLANILHA, worksheet="estoque", ttl=0).dropna(how='all').dropna(axis=1, how='all')
    pedidos = conn.read(spreadsheet=URL_PLANILHA, worksheet="pedidos", ttl=0).dropna(how='all').dropna(axis=1, how='all')
    clientes = conn.read(spreadsheet=URL_PLANILHA, worksheet="clientes", ttl=0).dropna(how='all').dropna(axis=1, how='all')
    
    # Limpando espaços extras nos nomes das colunas
    estoque.columns = estoque.columns.str.strip()
    pedidos.columns = pedidos.columns.str.strip()
    clientes.columns = clientes.columns.str.strip()
    
    return conn, estoque, pedidos, clientes

try:
    conn, df_estoque, df_pedidos, df_clientes = carregar_dados()
except Exception as e:
    st.error("### ❌ Erro de Conexão com o Google Sheets")
    st.write(f"Detalhe: {e}")
    st.info("Verifique se as abas na planilha se chamam exatamente: **Estoque**, **Pedidos** e **Clientes** (sem espaços).")
    st.stop()

# --- SIDEBAR (ALERTAS) ---
with st.sidebar:
    st.header("🔔 Alertas")
    alertas = []
    for index, row in df_estoque.iterrows():
        for tam in TAMANHOS_PADRAO:
            if tam in row:
                qtd = pd.to_numeric(row[tam], errors='coerce')
                if not pd.isna(qtd) and qtd < 3:
                    alertas.append(f"{row['Modelo']} ({tam}): {int(qtd)} un")
    
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
    modelos_disponiveis = df_estoque['Modelo'].dropna().unique()
    
    if len(modelos_disponiveis) > 0:
        mod_rep = c1.selectbox("Modelo para Repor", modelos_disponiveis)
        tam_rep = c2.selectbox("Tamanho", TAMANHOS_PADRAO, key="rep_t")
        qtd_rep = c3.number_input("Qtd", min_value=1, step=1, key="rep_q")
        
        if c4.button("Repor ✅"):
            idx = df_estoque.index[df_estoque['Modelo'] == mod_rep][0]
            atual = int(pd.to_numeric(df_estoque.at[idx, tam_rep], errors='coerce') or 0)
            df_estoque.at[idx, tam_rep] = atual + qtd_rep
            conn.update(spreadsheet=URL_PLANILHA, worksheet="Estoque", data=df_estoque)
            st.cache_data.clear()
            st.success("Estoque atualizado!")
            st.rerun()

# --- ABA 2: NOVA VENDA ---
with abas[1]:
    st.subheader("📝 Registrar Pedido")
    
    if df_clientes.empty or 'Nome' not in df_clientes.columns:
        st.warning("Cadastre um cliente na aba 'Clientes' primeiro.")
    else:
        clientes_lista = df_clientes['Nome'].dropna().unique()
        cliente_sel = st.selectbox("Selecionar Cliente", clientes_lista)
        dados_c = df_clientes[df_clientes['Nome'] == cliente_sel].iloc[0]
        
        st.info(f"📍 **Loja:** {dados_c.get('Loja', 'N/A')} | **Cidade:** {dados_c.get('Cidade', 'N/A')}")

        if 'carrinho' not in st.session_state:
            st.session_state.carrinho = []

        st.write("### 🛒 Carrinho")
        i1, i2, i3, i4 = st.columns([3, 2, 2, 1])
        mod_v = i1.selectbox("Escolher Modelo", modelos_disponiveis)
        tam_v = i2.selectbox("Escolher Tamanho", TAMANHOS_PADRAO, key="v_t")
        qtd_v = i3.number_input("Qtd", min_value=1, step=1, key="v_q")

        if i4.button("Adicionar ➕"):
            estoque_val = df_estoque.loc[df_estoque['Modelo'] == mod_v, tam_v].values[0]
            estoque_atual = int(pd.to_numeric(estoque_val, errors='coerce') or 0)
            
            if estoque_atual >= qtd_v:
                st.session_state.carrinho.append({"modelo": mod_v, "tamanho": tam_v, "quantidade": qtd_v})
                st.toast(f"{mod_v} adicionado!")
            else:
                st.error(f"Estoque insuficiente! Disponível: {estoque_atual}")

        if st.session_state.carrinho:
            for i, item in enumerate(st.session_state.carrinho):
                st.write(f"{i+1}. {item['quantidade']}x {item['modelo']} (Tam: {item['tamanho']})")
            
            if st.button("FINALIZAR VENDA ✅", type="primary"):
                data_v = datetime.now().strftime("%d/%m/%Y %H:%M")
                novos_pedidos = []
                
                for item in st.session_state.carrinho:
                    idx_e = df_estoque.index[df_estoque['Modelo'] == item['modelo']][0]
                    v_atual = int(pd.to_numeric(df_estoque.at[idx_e, item['tamanho']], errors='coerce') or 0)
                    df_estoque.at[idx_e, item['tamanho']] = v_atual - item['quantidade']
                    
                    novos_pedidos.append({
                        "Data": data_v, "Cliente": cliente_sel, 
                        "Telefone": dados_c.get('Telefone', ''), "Loja": dados_c.get('Loja', ''), 
                        "Cidade": dados_c.get('Cidade', ''), "Item": f"{item['modelo']} ({item['tamanho']})", 
                        "Qtd": item['quantidade']
                    })
                
                df_p_fim = pd.concat([df_pedidos, pd.DataFrame(novos_pedidos)], ignore_index=True)
                conn.update(spreadsheet=URL_PLANILHA, worksheet="Estoque", data=df_estoque)
                conn.update(spreadsheet=URL_PLANILHA, worksheet="Pedidos", data=df_p_fim)
                st.session_state.carrinho = []
                st.cache_data.clear()
                st.success("Venda salva!")
                st.rerun()

# --- ABA 3: CLIENTES ---
with abas[2]:
    st.subheader("👥 Cadastro de Clientes")
    with st.form("form_cli"):
        n = st.text_input("Nome")
        l = st.text_input("Loja")
        t = st.text_input("Telefone")
        c = st.text_input("Cidade")
        if st.form_submit_button("Salvar 💾"):
            if n and l:
                novo = pd.DataFrame([{"Nome": n, "Loja": l, "Telefone": t, "Cidade": c}])
                df_c_fim = pd.concat([df_clientes, novo], ignore_index=True)
                conn.update(spreadsheet=URL_PLANILHA, worksheet="Clientes", data=df_c_fim)
                st.cache_data.clear()
                st.success("Cliente salvo!")
                st.rerun()

# --- ABA 4: HISTÓRICO ---
with abas[3]:
    st.subheader("📜 Histórico de Vendas")
    st.dataframe(df_pedidos.sort_index(ascending=False), use_container_width=True, hide_index=True)

# --- ABA 5: CADASTRO MODELOS ---
with abas[4]:
    st.subheader("✨ Novo Modelo")
    with st.form("novo_m"):
        nome_m = st.text_input("Nome do Modelo")
        cols = st.columns(5)
        q_ini = {}
        for i, t in enumerate(TAMANHOS_PADRAO):
            q_ini[t] = cols[i%5].number_input(f"Tam {t}", min_value=0, step=1)
        
        if st.form_submit_button("Criar Modelo ✨"):
            if nome_m and nome_m not in df_estoque['Modelo'].values:
                linha = {"Modelo": nome_m}
                linha.update(q_ini)
                df_e_fim = pd.concat([df_estoque, pd.DataFrame([linha])], ignore_index=True)
                conn.update(spreadsheet=URL_PLANILHA, worksheet="Estoque", data=df_e_fim)
                st.cache_data.clear()
                st.success("Modelo criado!")
                st.rerun()

