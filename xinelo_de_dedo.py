import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão de Sandálias Nuvem", layout="wide", page_icon="👡")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- FUNÇÃO DE CARREGAMENTO ---
@st.cache_data(ttl=0)
def carregar_dados():
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Estoque
    try:
        estoque = conn.read(spreadsheet=URL_PLANILHA, worksheet="Estoque", ttl=0).dropna(how='all')
    except:
        estoque = pd.DataFrame(columns=["Modelo"] + TAMANHOS_PADRAO)
            
    # Pedidos
    try:
        pedidos = conn.read(spreadsheet=URL_PLANILHA, worksheet="Pedidos", ttl=0).dropna(how='all')
    except:
        pedidos = pd.DataFrame(columns=["Data", "Cliente", "Resumo do Pedido"])
            
    # Clientes
    try:
        clientes = conn.read(spreadsheet=URL_PLANILHA, worksheet="Clientes", ttl=0).dropna(how='all')
    except:
        clientes = pd.DataFrame(columns=["Nome", "Loja", "Telefone", "Cidade"])

    for df in [estoque, pedidos, clientes]:
        df.columns = df.columns.str.strip()
        
    return conn, estoque, pedidos, clientes

conn, df_estoque, df_pedidos, df_clientes = carregar_dados()

# --- FUNÇÃO PARA SALVAR ---
def atualizar_planilha(aba, dataframe):
    df_limpo = dataframe.astype(str)
    df_limpo = df_limpo.loc[:, ~df_limpo.columns.str.contains('^Unnamed')]
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_limpo)
        st.cache_data.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        st.info("💡 Lembrete: A planilha precisa estar como 'Editor' para qualquer pessoa com o link.")

# --- SIDEBAR (ALERTAS) ---
with st.sidebar:
    st.header("🔔 Alertas de Reposição")
    alertas = []
    for _, row in df_estoque.iterrows():
        for tam in TAMANHOS_PADRAO:
            if tam in row:
                val = pd.to_numeric(row[tam], errors='coerce')
                if not pd.isna(val) and val < 3:
                    alertas.append(f"{row['Modelo']} ({tam}): {int(val)} un")
    if alertas:
        for a in alertas: st.warning(a)
    else:
        st.success("Tudo em dia!")

st.title("👡 Sistema de Gestão Comercial")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Estoque", "🛒 Nova Venda", "👥 Clientes", "📜 Histórico", "✨ Cadastro"])

# --- ABA 1: ESTOQUE E EDIÇÃO ---
with tab1:
    st.subheader("Gerenciar Inventário")
    if df_estoque.empty:
        st.info("Nenhum modelo cadastrado.")
    else:
        for idx, row in df_estoque.iterrows():
            with st.expander(f"📦 {row['Modelo']}"):
                col1, col2, col3 = st.columns([2, 1, 1])
                
                novo_nome = col1.text_input("Renomear Modelo", value=row['Modelo'], key=f"edit_n_{idx}")
                
                if col2.button("Salvar Nome ✅", key=f"btn_s_{idx}"):
                    df_estoque.at[idx, 'Modelo'] = novo_nome
                    atualizar_planilha("Estoque", df_estoque)
                
                if col3.button("Excluir 🗑️", key=f"btn_d_{idx}"):
                    df_estoque = df_estoque.drop(idx)
                    atualizar_planilha("Estoque", df_estoque)

                st.write("**Ajustar Quantidades:**")
                df_edit = row[TAMANHOS_PADRAO].to_frame().T
                novos_q = st.data_editor(df_edit, key=f"ed_q_{idx}", hide_index=True)
                
                if st.button("Atualizar Estoque 🔄", key=f"btn_up_{idx}"):
                    for t in TAMANHOS_PADRAO:
                        df_estoque.at[idx, t] = novos_q.at[0, t]
                    atualizar_planilha("Estoque", df_estoque)

# --- ABA 2: NOVA VENDA ---
with tab2:
    st.subheader("📝 Registrar Pedido")
    if df_clientes.empty or df_estoque.empty:
        st.warning("Cadastre clientes e modelos primeiro.")
    else:
        with st.form("venda"):
            c1, c2, c3, c4 = st.columns(4)
            v_cli = c1.selectbox("Cliente", df_clientes['Nome'].unique())
            v_mod = c2.selectbox("Modelo", df_estoque['Modelo'].unique())
            v_tam = c3.selectbox("Tamanho", TAMANHOS_PADRAO)
            v_qtd = c4.number_input("Qtd", min_value=1, step=1)
            
            if st.form_submit_button("Finalizar Venda"):
                idx_e = df_estoque.index[df_estoque['Modelo'] == v_mod][0]
                q_atual = int(pd.to_numeric(df_estoque.at[idx_e, v_tam], errors='coerce') or 0)
                
                if q_atual >= v_qtd:
                    df_estoque.at[idx_e, v_tam] = q_atual - v_qtd
                    atualizar_planilha("Estoque", df_estoque)
                    
                    novo_p = pd.DataFrame([{
                        "Data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "Cliente": v_cli,
                        "Resumo do Pedido": f"{v_mod} ({v_tam}) - {v_qtd} un"
                    }])
                    df_pedidos = pd.concat([df_pedidos, novo_p], ignore_index=True)
                    atualizar_planilha("Pedidos", df_pedidos)
                else:
                    st.error("Estoque insuficiente!")

# --- ABA 3: CLIENTES ---
with tab3:
    st.subheader("Gerenciar Clientes")
    for idx, row in df_clientes.iterrows():
        with st.expander(f"👤 {row['Nome']}"):
            c1, c2, c3 = st.columns([2, 1, 1])
            novo_c = c1.text_input("Nome", value=row['Nome'], key=f"cn_{idx}")
            if c2.button("Salvar ✅", key=f"cs_{idx}"):
                df_clientes.at[idx, 'Nome'] = novo_c
                atualizar_planilha("Clientes", df_clientes)
            if c3.button("Excluir 🗑️", key=f"cd_{idx}"):
                df_clientes = df_clientes.drop(idx)
                atualizar_planilha("Clientes", df_clientes)

# --- ABA 4: HISTÓRICO ---
with tab4:
    st.subheader("📜 Pedidos Realizados")
    if not df_pedidos.empty:
        st.dataframe(df_pedidos[["Cliente", "Data", "Resumo do Pedido"]].sort_index(ascending=False), 
                     use_container_width=True, hide_index=True)

# --- ABA 5: CADASTRO ---
with tab5:
    st.subheader("✨ Novos Registros")
    escolha = st.radio("O que cadastrar?", ["Modelo", "Cliente"], horizontal=True)
    
    if escolha == "Modelo":
        with st.form("c_mod"):
            m_nome = st.text_input("Nome do Modelo")
            st.write("Quantidades:")
            cols = st.columns(5)
            q_dic = {t: cols[i%5].number_input(t, min_value=0) for i, t in enumerate(TAMANHOS_PADRAO)}
            if st.form_submit_button("Salvar Modelo"):
                if m_nome:
                    nl = {"Modelo": m_nome}; nl.update(q_dic)
                    df_estoque = pd.concat([df_estoque, pd.DataFrame([nl])], ignore_index=True)
                    atualizar_planilha("Estoque", df_estoque)
    else:
        with st.form("c_cli"):
            cn = st.text_input("Nome"); cl = st.text_input("Loja")
            ct = st.text_input("Telefone"); cc = st.text_input("Cidade")
            if st.form_submit_button("Salvar Cliente"):
                if cn:
                    nc = pd.DataFrame([{"Nome": cn, "Loja": cl, "Telefone": ct, "Cidade": cc}])
                    df_clientes = pd.concat([df_clientes, nc], ignore_index=True)
                    atualizar_planilha("Clientes", df_clientes)
                    
