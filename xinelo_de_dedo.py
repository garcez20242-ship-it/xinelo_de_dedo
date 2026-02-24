import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import re

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão de Sandálias Nuvem", layout="wide", page_icon="👡")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- FUNÇÃO AUXILIAR: CONVERTER LINK DO DRIVE ---
def converter_link_drive(url):
    if url and "drive.google.com" in url:
        match = re.search(r'[-\w]{25,}', url)
        if match:
            file_id = match.group()
            return f"https://drive.google.com/uc?export=view&id={file_id}"
    return url

# --- FUNÇÃO DE CARREGAMENTO ---
@st.cache_data(ttl=0)
def carregar_dados():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        def ler_aba(nome, colunas):
            try:
                df = conn.read(spreadsheet=URL_PLANILHA, worksheet=nome, ttl=0).dropna(how='all')
                if df.empty: return pd.DataFrame(columns=colunas)
                df.columns = df.columns.str.strip()
                return df
            except: return pd.DataFrame(columns=colunas)

        df_e = ler_aba("Estoque", ["Modelo", "Imagem"] + TAMANHOS_PADRAO)
        df_p = ler_aba("Pedidos", ["Data", "Cliente", "Resumo do Pedido"])
        df_c = ler_aba("Clientes", ["Nome", "Loja", "Telefone", "Cidade"])
        return conn, df_e, df_p, df_c
    except Exception as e:
        st.error(f"Erro na conexão: {e}")
        return None, None, None, None

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

# --- INTERFACE ---
st.title("👡 Sistema Comercial - Xinelo de Dedo")

if conn is not None:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Estoque", "🛒 Vendas/Aquisição", "👥 Clientes", "📜 Histórico", "✨ Cadastro"])

    # --- ABA 1: ESTOQUE (COM TRAVA DE EDIÇÃO) ---
    with tab1:
        col_t1, col_t2 = st.columns([3, 1])
        col_t1.subheader("Visualização de Inventário")
        modo_edicao = col_t2.toggle("🔓 Modo Edição", help="Ative para renomear modelos ou alterar links")

        if df_estoque.empty:
            st.info("Nenhum modelo cadastrado.")
        else:
            for idx, row in df_estoque.iterrows():
                with st.expander(f"📦 {row['Modelo']}"):
                    c1, c2 = st.columns([1, 2])
                    
                    link_img = row.get('Imagem', "")
                    if pd.notna(link_img) and str(link_img).startswith('http'):
                        c1.image(link_img, width=200)
                    else:
                        c1.warning("Sem imagem")

                    if modo_edicao:
                        # Campos editáveis quando o toggle está ativado
                        novo_nome = c2.text_input("Nome", value=row['Modelo'], key=f"n_{idx}")
                        novo_link = c2.text_input("Link Imagem", value=link_img, key=f"i_{idx}")
                        if c2.button("Salvar Alterações ✅", key=f"sv_{idx}"):
                            df_estoque.at[idx, 'Modelo'] = novo_nome
                            df_estoque.at[idx, 'Imagem'] = converter_link_drive(novo_link)
                            atualizar_planilha("Estoque", df_estoque)
                        if c2.button("Excluir Modelo 🗑️", key=f"del_{idx}"):
                            df_estoque = df_estoque.drop(idx)
                            atualizar_planilha("Estoque", df_estoque)
                    else:
                        # Visualização fixa quando o toggle está desativado
                        c2.write(f"**Nome:** {row['Modelo']}")
                        st.write("**Quantidades em estoque:**")
                        st.dataframe(row[TAMANHOS_PADRAO].to_frame().T, hide_index=True)

    # --- ABA 2: VENDAS E AQUISIÇÃO (ENTRADA E SAÍDA) ---
    with tab2:
        col_v, col_a = st.columns(2)
        
        # --- SEÇÃO DE VENDAS (SAÍDA) ---
        with col_v:
            st.subheader("🛒 Registrar Venda (Saída)")
            with st.form("venda"):
                v_cli = st.selectbox("Cliente", df_clientes['Nome'].unique())
                v_mod = st.selectbox("Modelo", df_estoque['Modelo'].unique(), key="v_mod")
                v_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="v_tam")
                v_qtd = st.number_input("Qtd Vendida", min_value=1)
                if st.form_submit_button("Finalizar Venda 🚀"):
                    idx_e = df_estoque.index[df_estoque['Modelo'] == v_mod][0]
                    estoque_atual = int(pd.to_numeric(df_estoque.at[idx_e, v_tam], errors='coerce') or 0)
                    if estoque_atual >= v_qtd:
                        df_estoque.at[idx_e, v_tam] = estoque_atual - v_qtd
                        atualizar_planilha("Estoque", df_estoque)
                        novo_p = pd.DataFrame([{"Data": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": v_cli, "Resumo do Pedido": f"VENDA: {v_mod} ({v_tam}) - {v_qtd} un"}])
                        df_pedidos = pd.concat([df_pedidos, novo_p], ignore_index=True)
                        atualizar_planilha("Pedidos", df_pedidos)
                    else: st.error("Estoque insuficiente!")

        # --- SEÇÃO DE AQUISIÇÃO (ENTRADA) ---
        with col_a:
            st.subheader("📦 Registrar Aquisição (Entrada)")
            with st.form("aquisicao"):
                a_mod = st.selectbox("Modelo", df_estoque['Modelo'].unique(), key="a_mod")
                a_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="a_tam")
                a_qtd = st.number_input("Qtd Adquirida", min_value=1)
                if st.form_submit_button("Registrar Entrada ➕"):
                    idx_e = df_estoque.index[df_estoque['Modelo'] == a_mod][0]
                    estoque_atual = int(pd.to_numeric(df_estoque.at[idx_e, a_tam], errors='coerce') or 0)
                    df_estoque.at[idx_e, a_tam] = estoque_atual + a_qtd
                    atualizar_planilha("Estoque", df_estoque)
                    novo_p = pd.DataFrame([{"Data": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": "FORNECEDOR", "Resumo do Pedido": f"ENTRADA: {a_mod} ({a_tam}) + {a_qtd} un"}])
                    df_pedidos = pd.concat([df_pedidos, novo_p], ignore_index=True)
                    atualizar_planilha("Pedidos", df_pedidos)

    # --- ABA 3: CLIENTES ---
    with tab3:
        st.subheader("Base de Clientes")
        if df_clientes.empty: st.info("Sem clientes.")
        else:
            for idx, row in df_clientes.iterrows():
                with st.expander(f"👤 {row['Nome']}"):
                    st.write(f"Loja: {row['Loja']} | Tel: {row['Telefone']} | Cidade: {row['Cidade']}")
                    if st.button("Remover 🗑️", key=f"dc_{idx}"):
                        df_clientes = df_clientes.drop(idx)
                        atualizar_planilha("Clientes", df_clientes)

    # --- ABA 4: HISTÓRICO ---
    with tab4:
        st.subheader("📜 Movimentações (Vendas e Entradas)")
        st.dataframe(df_pedidos.sort_index(ascending=False), use_container_width=True, hide_index=True)

    # --- ABA 5: CADASTRO ---
    with tab5:
        tipo = st.radio("Novo cadastro:", ["Modelo", "Cliente"], horizontal=True)
        if tipo == "Modelo":
            with st.form("cad_m"):
                m_n = st.text_input("Nome")
                m_i = st.text_input("Link Drive")
                cols = st.columns(5)
                q_d = {t: cols[i%5].number_input(f"Tam {t}", min_value=0) for i, t in enumerate(TAMANHOS_PADRAO)}
                if st.form_submit_button("Cadastrar"):
                    ni = {"Modelo": m_n, "Imagem": converter_link_drive(m_i)}
                    ni.update(q_d)
                    df_estoque = pd.concat([df_estoque, pd.DataFrame([ni])], ignore_index=True)
                    atualizar_planilha("Estoque", df_estoque)
        else:
            with st.form("cad_c"):
                cn = st.text_input("Nome"); cl = st.text_input("Loja")
                ct = st.text_input("Telefone"); cc = st.text_input("Cidade")
                if st.form_submit_button("Cadastrar Cliente"):
                    nc = pd.DataFrame([{"Nome": cn, "Loja": cl, "Telefone": ct, "Cidade": cc}])
                    df_clientes = pd.concat([df_clientes, nc], ignore_index=True)
                    atualizar_planilha("Clientes", df_clientes)
