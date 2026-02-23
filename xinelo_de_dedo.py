import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão de Sandálias Nuvem", layout="wide", page_icon="👡")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- FUNÇÃO DE CARREGAMENTO ROBUSTA ---
@st.cache_data(ttl=0)
def carregar_dados():
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    def ler_aba(nome, colunas):
        try:
            df = conn.read(spreadsheet=URL_PLANILHA, worksheet=nome, ttl=0).dropna(how='all')
            if df.empty:
                return pd.DataFrame(columns=colunas)
            df.columns = df.columns.str.strip()
            return df
        except:
            return pd.DataFrame(columns=colunas)

    df_e = ler_aba("Estoque", ["Modelo"] + TAMANHOS_PADRAO)
    df_p = ler_aba("Pedidos", ["Data", "Cliente", "Resumo do Pedido"])
    df_c = ler_aba("Clientes", ["Nome", "Loja", "Telefone", "Cidade"])
        
    return conn, df_e, df_p, df_c

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
        st.info("💡 Certifique-se de que a planilha está como 'Editor' para qualquer pessoa com o link.")

# --- SIDEBAR (ALERTAS) ---
with st.sidebar:
    st.header("🔔 Alertas")
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
        st.success("Estoque OK!")

st.title("👡 Sistema Comercial - Xinelo de Dedo")

# Criação das abas principais
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Estoque", "🛒 Nova Venda", "👥 Clientes", "📜 Histórico", "✨ Cadastro"])

# --- ABA 1: ESTOQUE (EDIÇÃO E EXCLUSÃO) ---
with tab1:
    st.subheader("Gerenciar Inventário")
    if df_estoque.empty:
        st.info("Nenhum dado encontrado no Estoque.")
    else:
        for idx, row in df_estoque.iterrows():
            with st.expander(f"📦 {row['Modelo']}"):
                c1, c2, c3 = st.columns([2, 1, 1])
                novo_nome = c1.text_input("Renomear", value=row['Modelo'], key=f"edit_mod_{idx}")
                
                if c2.button("Salvar ✅", key=f"btn_s_m_{idx}"):
                    df_estoque.at[idx, 'Modelo'] = novo_nome
                    atualizar_planilha("Estoque", df_estoque)
                
                if c3.button("Excluir 🗑️", key=f"btn_d_m_{idx}"):
                    df_estoque = df_estoque.drop(idx)
                    atualizar_planilha("Estoque", df_estoque)

                st.write("**Quantidades:**")
                df_temp = row[TAMANHOS_PADRAO].to_frame().T
                res_edit = st.data_editor(df_temp, key=f"editor_{idx}", hide_index=True)
                
                if st.button("Atualizar Qtd 🔄", key=f"btn_q_{idx}"):
                    for t in TAMANHOS_PADRAO:
                        df_estoque.at[idx, t] = res_edit.at[0, t]
                    atualizar_planilha("Estoque", df_estoque)

# --- ABA 2: NOVA VENDA (BAIXA AUTOMÁTICA) ---
with tab2:
    st.subheader("📝 Registrar Venda")
    if df_clientes.empty or df_estoque.empty:
        st.warning("Cadastre clientes e modelos primeiro.")
    else:
        with st.form("venda_form"):
            col1, col2, col3, col4 = st.columns(4)
            v_cli = col1.selectbox("Cliente", df_clientes['Nome'].unique())
            v_mod = col2.selectbox("Modelo", df_estoque['Modelo'].unique())
            v_tam = col3.selectbox("Tamanho", TAMANHOS_PADRAO)
            v_qtd = col4.number_input("Qtd", min_value=1, step=1)
            
            if st.form_submit_button("Finalizar Venda"):
                idx_e = df_estoque.index[df_estoque['Modelo'] == v_mod][0]
                q_atual = int(pd.to_numeric(df_estoque.at[idx_e, v_tam], errors='coerce') or 0)
                
                if q_atual >= v_qtd:
                    # Baixa Estoque
                    df_estoque.at[idx_e, v_tam] = q_atual - v_qtd
                    atualizar_planilha("Estoque", df_estoque)
                    # Grava Histórico
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
    if df_clientes.empty:
        st.info("Nenhum cliente cadastrado.")
    else:
        for idx, row in df_clientes.iterrows():
            with st.expander(f"👤 {row['Nome']}"):
                c1, c2, c3 = st.columns([2, 1, 1])
                nome_c = c1.text_input("Nome", value=row['Nome'], key=f"cn_{idx}")
                if c2.button("Atualizar ✅", key=f"cu_{idx}"):
                    df_clientes.at[idx, 'Nome'] = nome_c
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
        with st.form("f_mod"):
            m_n = st.text_input("Nome do Modelo")
            cols = st.columns(5)
            q_dic = {t: cols[i%5].number_input(t, min_value=0) for i, t in enumerate(TAMANHOS_PADRAO)}
            if st.form_submit_button("Cadastrar Modelo"):
                if m_n:
                    nl = {"Modelo": m_n}; nl.update(q_dic)
                    df_estoque = pd.concat([df_estoque, pd.DataFrame([nl])], ignore_index=True)
                    atualizar_planilha("Estoque", df_estoque)
    else:
        with st.form("f_cli"):
            cn = st.text_input("Nome"); cl = st.text_input("Loja")
            ct = st.text_input("Telefone"); cc = st.text_input("Cidade")
            if st.form_submit_button("Cadastrar Cliente"):
                if cn:
                    nc = pd.DataFrame([{"Nome": cn, "Loja": cl, "Telefone": ct, "Cidade": cc}])
                    df_clientes = pd.concat([df_clientes, nc], ignore_index=True)
                    atualizar_planilha("Clientes", df_clientes)
