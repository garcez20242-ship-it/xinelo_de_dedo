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
    
    # Carrega Estoque
    try:
        estoque = conn.read(spreadsheet=URL_PLANILHA, worksheet="Estoque", ttl=0).dropna(how='all')
    except:
        estoque = pd.DataFrame(columns=["Modelo", "Imagem"] + TAMANHOS_PADRAO)
            
    # Carrega Pedidos
    try:
        pedidos = conn.read(spreadsheet=URL_PLANILHA, worksheet="Pedidos", ttl=0).dropna(how='all')
    except:
        pedidos = pd.DataFrame(columns=["Data", "Cliente", "Resumo do Pedido"])
            
    # Carrega Clientes
    try:
        clientes = conn.read(spreadsheet=URL_PLANILHA, worksheet="Clientes", ttl=0).dropna(how='all')
    except:
        clientes = pd.DataFrame(columns=["Nome", "Loja", "Telefone", "Cidade"])

    # Limpeza de colunas
    for df in [estoque, pedidos, clientes]:
        df.columns = df.columns.str.strip()
        
    return conn, estoque, pedidos, clientes

conn, df_estoque, df_pedidos, df_clientes = carregar_dados()

# --- FUNÇÃO AUXILIAR PARA SALVAR ---
def atualizar_planilha(aba, dataframe):
    df_limpo = dataframe.astype(str)
    # Remove colunas vazias acidentais
    df_limpo = df_limpo.loc[:, ~df_limpo.columns.str.contains('^Unnamed')]
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_limpo)
        st.cache_data.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- SIDEBAR (ALERTAS) ---
with st.sidebar:
    st.header("🔔 Alertas de Estoque")
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

st.title("👡 Sistema Comercial Completo")

# Definição das Abas
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Estoque", "🛒 Nova Venda", "👥 Clientes", "📜 Histórico", "✨ Cadastro"])

# --- ABA 1: ESTOQUE E EDIÇÃO ---
with tab1:
    st.subheader("Gerenciar Modelos e Quantidades")
    if df_estoque.empty:
        st.info("Nenhum modelo cadastrado.")
    else:
        for idx, row in df_estoque.iterrows():
            with st.expander(f"📦 {row['Modelo']}"):
                col_img, col_info = st.columns([1, 3])
                
                if pd.notna(row['Imagem']) and str(row['Imagem']).startswith('http'):
                    col_img.image(row['Imagem'], width=150)
                
                # Campos de Edição
                novo_nome = col_info.text_input("Renomear Modelo", value=row['Modelo'], key=f"edit_name_{idx}")
                novo_link = col_info.text_input("Link da Imagem", value=row['Imagem'] if pd.notna(row['Imagem']) else "", key=f"edit_link_{idx}")
                
                c1, c2 = col_info.columns(2)
                if c1.button("Salvar Alterações ✅", key=f"btn_save_mod_{idx}"):
                    df_estoque.at[idx, 'Modelo'] = novo_nome
                    df_estoque.at[idx, 'Imagem'] = novo_link
                    atualizar_planilha("Estoque", df_estoque)
                
                if c2.button("Excluir Modelo 🗑️", key=f"btn_del_mod_{idx}"):
                    df_estoque = df_estoque.drop(idx)
                    atualizar_planilha("Estoque", df_estoque)

                st.write("**Ajuste de Quantidades:**")
                # Editor de dados para os tamanhos
                df_tam_edit = row[TAMANHOS_PADRAO].to_frame().T
                edit_vals = st.data_editor(df_tam_edit, key=f"editor_q_{idx}", hide_index=True)
                
                if st.button("Atualizar Estoque 🔄", key=f"btn_upd_q_{idx}"):
                    for t in TAMANHOS_PADRAO:
                        df_estoque.at[idx, t] = edit_vals.at[0, t]
                    atualizar_planilha("Estoque", df_estoque)

# --- ABA 2: NOVA VENDA (BAIXA AUTOMÁTICA) ---
with tab2:
    st.subheader("📝 Registrar Pedido")
    if df_clientes.empty or df_estoque.empty:
        st.warning("Cadastre clientes e modelos primeiro.")
    else:
        with st.form("venda_form"):
            c1, c2, c3, c4 = st.columns(4)
            sel_cli = c1.selectbox("Cliente", df_clientes['Nome'].unique())
            sel_mod = c2.selectbox("Modelo", df_estoque['Modelo'].unique())
            sel_tam = c3.selectbox("Tamanho", TAMANHOS_PADRAO)
            sel_qtd = c4.number_input("Qtd", min_value=1, step=1)
            
            if st.form_submit_button("Finalizar Venda"):
                idx_e = df_estoque.index[df_estoque['Modelo'] == sel_mod][0]
                q_atual = int(pd.to_numeric(df_estoque.at[idx_e, sel_tam], errors='coerce') or 0)
                
                if q_atual >= sel_qtd:
                    # 1. Baixa no Estoque
                    df_estoque.at[idx_e, sel_tam] = q_atual - sel_qtd
                    atualizar_planilha("Estoque", df_estoque)
                    
                    # 2. Grava Pedido no Histórico
                    novo_p = pd.DataFrame([{
                        "Data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "Cliente": sel_cli,
                        "Resumo do Pedido": f"{sel_mod} ({sel_tam}) - {sel_qtd} un"
                    }])
                    df_pedidos = pd.concat([df_pedidos, novo_p], ignore_index=True)
                    atualizar_planilha("Pedidos", df_pedidos)
                else:
                    st.error(f"Estoque insuficiente! Disponível: {q_atual}")

# --- ABA 3: CLIENTES (EDIÇÃO E EXCLUSÃO) ---
with tab3:
    st.subheader("Gerenciar Carteira de Clientes")
    if df_clientes.empty:
        st.info("Nenhum cliente cadastrado.")
    else:
        for idx, row in df_clientes.iterrows():
            with st.expander(f"👤 {row['Nome']}"):
                col_a, col_b = st.columns(2)
                novo_cn = col_a.text_input("Nome Cliente", value=row['Nome'], key=f"c_n_{idx}")
                novo_cl = col_b.text_input("Loja", value=row['Loja'], key=f"c_l_{idx}")
                
                c1, c2 = st.columns(2)
                if c1.button("Atualizar Cadastro ✅", key=f"c_up_{idx}"):
                    df_clientes.at[idx, 'Nome'] = novo_cn
                    df_clientes.at[idx, 'Loja'] = novo_cl
                    atualizar_planilha("Clientes", df_clientes)
                
                if c2.button("Excluir Cliente 🗑️", key=f"c_dl_{idx}"):
                    df_clientes = df_clientes.drop(idx)
                    atualizar_planilha("Clientes", df_clientes)

# --- ABA 4: HISTÓRICO ---
with tab4:
    st.subheader("📜 Histórico de Pedidos")
    if not df_pedidos.empty:
        st.dataframe(df_pedidos[["Cliente", "Data", "Resumo do Pedido"]].sort_index(ascending=False), 
                     use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma venda realizada ainda.")

# --- ABA 5: CADASTRO ---
with tab5:
    st.subheader("✨ Novos Registros")
    escolha = st.radio("O que deseja cadastrar?", ["Modelo", "Cliente"], horizontal=True)
    
    if escolha == "Modelo":
        with st.form("cad_mod_form"):
            m_n = st.text_input("Nome do Modelo")
            m_i = st.text_input("Link da Imagem (URL)")
            st.write("Quantidades Iniciais:")
            cols = st.columns(5)
            q_dic = {t: cols[i%5].number_input(f"Tam {t}", min_value=0) for i, t in enumerate(TAMANHOS_PADRAO)}
            
            if st.form_submit_button("Salvar Modelo"):
                if m_n:
                    nl = {"Modelo": m_n, "Imagem": m_i}; nl.update(q_dic)
                    df_estoque = pd.concat([df_estoque, pd.DataFrame([nl])], ignore_index=True)
                    atualizar_planilha("Estoque", df_estoque)
    else:
        with st.form("cad_cli_form"):
            cn = st.text_input("Nome do Cliente")
            cl = st.text_input("Nome da Loja")
            ct = st.text_input("Telefone")
            cc = st.text_input("Cidade")
            
            if st.form_submit_button("Salvar Cliente"):
                if cn:
                    nc = pd.DataFrame([{"Nome": cn, "Loja": cl, "Telefone": ct, "Cidade": cc}])
                    df_clientes = pd.concat([df_clientes, nc], ignore_index=True)
                    atualizar_planilha("Clientes", df_clientes)
