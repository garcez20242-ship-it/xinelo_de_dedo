import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import re

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão de Sandálias Nuvem", layout="wide", page_icon="👡")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- FUNÇÕES AUXILIARES ---
def converter_link_drive(url):
    if url and "drive.google.com" in url:
        match = re.search(r'[-\w]{25,}', url)
        if match:
            file_id = match.group()
            return f"https://drive.google.com/uc?export=view&id={file_id}"
    return url

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

def atualizar_planilha(aba, dataframe):
    df_limpo = dataframe.astype(str)
    df_limpo = df_limpo.loc[:, ~df_limpo.columns.str.contains('^Unnamed')]
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_limpo)
        st.cache_data.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- ESTADO DO CARRINHO ---
if 'carrinho' not in st.session_state:
    st.session_state.carrinho = []

# --- INTERFACE ---
st.title("👡 Sistema Comercial - Xinelo de Dedo")

if conn is not None:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Estoque & Aquisição", "🛒 Carrinho de Vendas", "👥 Clientes", "📜 Histórico", "✨ Cadastro"])

    # --- ABA 1: ESTOQUE & AQUISIÇÃO ---
    with tab1:
        # Cabeçalho da Lista de Estoque
        c_head1, c_head2 = st.columns([5, 1])
        c_head1.subheader("📦 Inventário Atual")
        modo_edicao = c_head2.toggle("🔓 Editar", help="Habilitar renomeação e exclusão")

        if df_estoque.empty:
            st.info("Nenhum modelo no sistema.")
        else:
            # Lista de Modelos
            for idx, row in df_estoque.iterrows():
                with st.expander(f"👟 {row['Modelo']}"):
                    col_img, col_info = st.columns([1, 3])
                    
                    if pd.notna(row.get('Imagem')) and str(row['Imagem']).startswith('http'):
                        col_img.image(row['Imagem'], width=150)
                    else:
                        col_img.write("Sem foto")

                    if modo_edicao:
                        n_nome = col_info.text_input("Nome", value=row['Modelo'], key=f"n_{idx}")
                        n_img = col_info.text_input("Link Imagem", value=row.get('Imagem',''), key=f"i_{idx}")
                        c_b1, c_b2 = col_info.columns(2)
                        if c_b1.button("Salvar ✅", key=f"s_{idx}"):
                            df_estoque.at[idx, 'Modelo'] = n_nome
                            df_estoque.at[idx, 'Imagem'] = converter_link_drive(n_img)
                            atualizar_planilha("Estoque", df_estoque)
                        if c_b2.button("Excluir 🗑️", key=f"d_{idx}"):
                            df_estoque = df_estoque.drop(idx)
                            atualizar_planilha("Estoque", df_estoque)
                    else:
                        col_info.dataframe(row[TAMANHOS_PADRAO].to_frame().T, hide_index=True)

        st.divider()

        # Seção de Entrada Geral (Movida para o fim)
        st.subheader("📥 Registrar Entrada de Mercadoria")
        with st.form("entrada_geral"):
            c_a1, c_a2, c_a3 = st.columns(3)
            a_mod = c_a1.selectbox("Selecione o Modelo", df_estoque['Modelo'].unique())
            a_tam = c_a2.selectbox("Selecione o Tamanho", TAMANHOS_PADRAO)
            a_qtd = c_a3.number_input("Quantidade para adicionar ao estoque", min_value=1, step=1)
            if st.form_submit_button("Confirmar Entrada no Sistema ➕"):
                idx_e = df_estoque.index[df_estoque['Modelo'] == a_mod][0]
                atual = int(pd.to_numeric(df_estoque.at[idx_e, a_tam], errors='coerce') or 0)
                df_estoque.at[idx_e, a_tam] = atual + a_qtd
                atualizar_planilha("Estoque", df_estoque)
                # Registro no Histórico
                novo_h = pd.DataFrame([{"Data": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": "FORNECEDOR", "Resumo do Pedido": f"ENTRADA: {a_mod} ({a_tam}) +{a_qtd} un"}])
                df_pedidos = pd.concat([df_pedidos, novo_h], ignore_index=True)
                atualizar_planilha("Pedidos", df_pedidos)

    # --- ABA 2: CARRINHO DE VENDAS ---
    with tab2:
        st.subheader("🛒 Carrinho de Vendas")
        if df_clientes.empty or df_estoque.empty:
            st.warning("Verifique se há clientes e modelos cadastrados.")
        else:
            c1, c2 = st.columns([1.5, 2.5])
            with c1:
                st.write("**Adicionar Item**")
                v_cli = st.selectbox("Cliente", df_clientes['Nome'].unique())
                v_mod = st.selectbox("Modelo", df_estoque['Modelo'].unique())
                v_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO)
                v_qtd = st.number_input("Qtd (Máx 50)", min_value=1, max_value=50)
                if st.button("Adicionar ao Carrinho ➕"):
                    st.session_state.carrinho.append({"Modelo": v_mod, "Tamanho": v_tam, "Qtd": v_qtd})
                    st.toast("Item adicionado!")

            with c2:
                st.write(f"**Pedido: {v_cli}**")
                if not st.session_state.carrinho:
                    st.info("Carrinho vazio.")
                else:
                    st.table(pd.DataFrame(st.session_state.carrinho))
                    cl1, cl2 = st.columns(2)
                    if cl1.button("Limpar 🗑️"):
                        st.session_state.carrinho = []
                        st.rerun()
                    if cl2.button("Finalizar Venda 🚀"):
                        resumo = []
                        erro = False
                        for item in st.session_state.carrinho:
                            idx_e = df_estoque.index[df_estoque['Modelo'] == item['Modelo']][0]
                            atual = int(pd.to_numeric(df_estoque.at[idx_e, item['Tamanho']], errors='coerce') or 0)
                            if atual < item['Qtd']:
                                st.error(f"Sem estoque: {item['Modelo']} {item['Tamanho']}")
                                erro = True; break
                        if not erro:
                            for item in st.session_state.carrinho:
                                idx_e = df_estoque.index[df_estoque['Modelo'] == item['Modelo']][0]
                                df_estoque.at[idx_e, item['Tamanho']] = int(df_estoque.at[idx_e, item['Tamanho']]) - item['Qtd']
                                resumo.append(f"{item['Modelo']} ({item['Tamanho']}) x{item['Qtd']}")
                            atualizar_planilha("Estoque", df_estoque)
                            novo_p = pd.DataFrame([{"Data": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": v_cli, "Resumo do Pedido": " | ".join(resumo)}])
                            df_pedidos = pd.concat([df_pedidos, novo_p], ignore_index=True)
                            atualizar_planilha("Pedidos", df_pedidos)
                            st.session_state.carrinho = []
                            st.success("Venda processada!")

    # --- ABA 3: CLIENTES ---
    with tab3:
        st.subheader("Clientes")
        if not df_clientes.empty:
            for idx, row in df_clientes.iterrows():
                with st.expander(f"👤 {row['Nome']}"):
                    c_c1, c_c2 = st.columns(2)
                    n_c = c_c1.text_input("Nome", value=row['Nome'], key=f"cn_{idx}")
                    l_c = c_c2.text_input("Loja", value=row.get('Loja', ''), key=f"cl_{idx}")
                    t_c = c_c1.text_input("Tel", value=row.get('Telefone', ''), key=f"ct_{idx}")
                    cid_c = c_c2.text_input("Cidade", value=row.get('Cidade', ''), key=f"cc_{idx}")
                    if st.button("Salvar ✅", key=f"sc_{idx}"):
                        df_clientes.at[idx, 'Nome'], df_clientes.at[idx, 'Loja'] = n_c, l_c
                        df_clientes.at[idx, 'Telefone'], df_clientes.at[idx, 'Cidade'] = t_c, cid_c
                        atualizar_planilha("Clientes", df_clientes)
                    if st.button("Excluir 🗑️", key=f"rc_{idx}"):
                        df_clientes = df_clientes.drop(idx); atualizar_planilha("Clientes", df_clientes)

    # --- ABA 4: HISTÓRICO ---
    with tab4:
        st.subheader("Histórico")
        st.dataframe(df_pedidos.sort_index(ascending=False), use_container_width=True, hide_index=True)

    # --- ABA 5: CADASTRO ---
    with tab5:
        tipo = st.radio("Cadastro:", ["Modelo", "Cliente"], horizontal=True)
        if tipo == "Modelo":
            with st.form("fm"):
                m_n = st.text_input("Nome"); m_i = st.text_input("Link Imagem")
                cols = st.columns(5)
                q_d = {t: cols[i%5].number_input(f"T{t}", min_value=0) for i, t in enumerate(TAMANHOS_PADRAO)}
                if st.form_submit_button("Cadastrar ✨"):
                    ni = {"Modelo": m_n, "Imagem": converter_link_drive(m_i)}; ni.update(q_d)
                    df_estoque = pd.concat([df_estoque, pd.DataFrame([ni])], ignore_index=True); atualizar_planilha("Estoque", df_estoque)
        else:
            with st.form("fc"):
                cn = st.text_input("Nome"); cl = st.text_input("Loja"); ct = st.text_input("Tel"); cc = st.text_input("Cid")
                if st.form_submit_button("Cadastrar 👤"):
                    nc = pd.DataFrame([{"Nome": cn, "Loja": cl, "Telefone": ct, "Cidade": cc}])
                    df_clientes = pd.concat([df_clientes, nc], ignore_index=True); atualizar_planilha("Clientes", df_clientes)
