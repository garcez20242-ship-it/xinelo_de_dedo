import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import re

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão de Sandálias Nuvem", layout="wide", page_icon="👡")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- FUNÇÃO PARA CONVERTER LINK DO DRIVE EM IMAGEM DIRETA ---
def tratar_link_drive(url):
    if not url or not isinstance(url, str):
        return ""
    # Extrai o ID do arquivo de links comuns do Drive
    match = re.search(r'(?:id=|[//])([-\w]{25,})', url)
    if match:
        file_id = match.group(1)
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
    except Exception as e:
        st.error(f"Erro ao salvar na aba {aba}: {e}")

# --- INTERFACE ---
st.title("👡 Sistema Comercial - Armazenamento Drive")

if conn is not None:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Estoque", "🛒 Vendas", "👥 Clientes", "📜 Histórico", "✨ Cadastro"])

    # --- ABA 1: ESTOQUE ---
    with tab1:
        c_head1, c_head2 = st.columns([5, 1])
        c_head1.subheader("📦 Inventário Atual")
        modo_edicao = c_head2.toggle("🔓 Editar", help="Habilitar edição de nomes e fotos")

        if df_estoque.empty:
            st.info("Estoque vazio.")
        else:
            for idx, row in df_estoque.iterrows():
                with st.expander(f"👟 {row['Modelo']}"):
                    col_img, col_info = st.columns([1, 3])
                    
                    # Exibição de Imagem do Drive
                    url_raw = row.get('Imagem', '')
                    url_direta = tratar_link_drive(url_raw)
                    
                    if url_direta:
                        col_img.image(url_direta, width=180)
                    else:
                        col_img.warning("Sem imagem")

                    if modo_edicao:
                        n_nome = col_info.text_input("Nome do Modelo", value=row['Modelo'], key=f"ed_m_{idx}")
                        n_link = col_info.text_input("Link de Compartilhamento do Drive", value=url_raw, key=f"ed_l_{idx}")
                        
                        c_b1, c_b2 = col_info.columns(2)
                        if c_b1.button("Salvar ✅", key=f"sv_m_{idx}"):
                            df_estoque.at[idx, 'Modelo'] = n_nome
                            df_estoque.at[idx, 'Imagem'] = n_link
                            atualizar_planilha("Estoque", df_estoque)
                            st.rerun()
                        
                        with c_b2:
                            confirm = st.checkbox("Confirmar?", key=f"chk_m_{idx}")
                            if st.button("APAGAR 🗑️", key=f"del_m_{idx}", disabled=not confirm):
                                df_estoque = df_estoque.drop(idx)
                                atualizar_planilha("Estoque", df_estoque)
                                st.rerun()
                    else:
                        col_info.dataframe(row[TAMANHOS_PADRAO].to_frame().T, hide_index=True)

        st.divider()
        st.subheader("📥 Registrar Entrada (Geral)")
        with st.form("entrada"):
            c1, c2, c3 = st.columns(3)
            a_mod = c1.selectbox("Modelo", df_estoque['Modelo'].unique())
            a_tam = c2.selectbox("Tamanho", TAMANHOS_PADRAO)
            a_qtd = c3.number_input("Qtd", min_value=1, step=1)
            if st.form_submit_button("Confirmar Entrada"):
                idx_e = df_estoque.index[df_estoque['Modelo'] == a_mod][0]
                atual = int(pd.to_numeric(df_estoque.at[idx_e, a_tam], errors='coerce') or 0)
                df_estoque.at[idx_e, a_tam] = atual + a_qtd
                
                novo_h = pd.DataFrame([{"Data": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": "FORNECEDOR", "Resumo do Pedido": f"ENTRADA: {a_mod} ({a_tam}) +{a_qtd}"}])
                df_pedidos = pd.concat([df_pedidos, novo_h], ignore_index=True)
                
                atualizar_planilha("Estoque", df_estoque)
                atualizar_planilha("Pedidos", df_pedidos)
                st.rerun()

    # --- ABA 2: VENDAS ---
    with tab2:
        if 'carrinho' not in st.session_state: st.session_state.carrinho = []
        st.subheader("🛒 Carrinho de Vendas")
        if not df_clientes.empty and not df_estoque.empty:
            v_cli = st.selectbox("Cliente", df_clientes['Nome'].unique())
            c1, c2 = st.columns([1.5, 2.5])
            with c1:
                v_mod = st.selectbox("Modelo", df_estoque['Modelo'].unique())
                v_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO)
                v_qtd = st.number_input("Qtd (Máx 50)", min_value=1, max_value=50)
                if st.button("Adicionar ➕"):
                    st.session_state.carrinho.append({"Modelo": v_mod, "Tamanho": v_tam, "Qtd": v_qtd})
            with c2:
                if st.session_state.carrinho:
                    st.table(pd.DataFrame(st.session_state.carrinho))
                    if st.button("Finalizar Venda 🚀"):
                        resumo = []
                        for item in st.session_state.carrinho:
                            idx_e = df_estoque.index[df_estoque['Modelo'] == item['Modelo']][0]
                            atual = int(pd.to_numeric(df_estoque.at[idx_e, item['Tamanho']], errors='coerce') or 0)
                            df_estoque.at[idx_e, item['Tamanho']] = atual - item['Qtd']
                            resumo.append(f"{item['Modelo']} ({item['Tamanho']}) x{item['Qtd']}")
                        
                        novo_p = pd.DataFrame([{"Data": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": v_cli, "Resumo do Pedido": " | ".join(resumo)}])
                        df_pedidos = pd.concat([df_pedidos, novo_p], ignore_index=True)
                        
                        atualizar_planilha("Estoque", df_estoque)
                        atualizar_planilha("Pedidos", df_pedidos)
                        st.session_state.carrinho = []
                        st.rerun()

    # --- ABA 3: CLIENTES ---
    with tab3:
        st.subheader("👥 Clientes")
        for idx, row in df_clientes.iterrows():
            with st.expander(f"👤 {row['Nome']}"):
                col_t, col_d = st.columns([4, 1])
                col_t.write(f"Loja: {row.get('Loja','')} | Cidade: {row.get('Cidade','')}")
                conf = col_d.checkbox("Confirmar?", key=f"c_c_{idx}")
                if col_d.button("APAGAR", key=f"d_c_{idx}", disabled=not conf):
                    df_clientes = df_clientes.drop(idx)
                    atualizar_planilha("Clientes", df_clientes)
                    st.rerun()

    # --- ABA 4: HISTÓRICO ---
    with tab4:
        st.subheader("📜 Histórico")
        for idx in reversed(df_pedidos.index):
            row = df_pedidos.loc[idx]
            c_t, c_a = st.columns([5, 1])
            c_t.write(f"**{row['Data']}** - {row['Cliente']}: {row['Resumo do Pedido']}")
            conf_h = c_a.checkbox("Confirmar?", key=f"c_h_{idx}")
            if c_a.button("Apagar", key=f"d_h_{idx}", disabled=not conf_h):
                df_pedidos = df_pedidos.drop(idx)
                atualizar_planilha("Pedidos", df_pedidos)
                st.rerun()

    # --- ABA 5: CADASTRO ---
    with tab5:
        tipo = st.radio("Cadastro:", ["Modelo", "Cliente"], horizontal=True)
        if tipo == "Modelo":
            with st.form("cad_mod"):
                m_n = st.text_input("Nome do Modelo")
                m_l = st.text_input("Link de Compartilhamento do Google Drive")
                st.caption("Certifique-se que o link está configurado para 'Qualquer pessoa com o link'")
                cols = st.columns(5)
                q_d = {t: cols[i%5].number_input(f"T{t}", min_value=0) for i, t in enumerate(TAMANHOS_PADRAO)}
                if st.form_submit_button("Cadastrar Modelo"):
                    if m_n:
                        ni = {"Modelo": m_n, "Imagem": m_l}
                        ni.update(q_d)
                        df_estoque = pd.concat([df_estoque, pd.DataFrame([ni])], ignore_index=True)
                        atualizar_planilha("Estoque", df_estoque)
                        st.rerun()
        else:
            with st.form("cad_cli"):
                cn = st.text_input("Nome"); cl = st.text_input("Loja"); cc = st.text_input("Cidade")
                if st.form_submit_button("Cadastrar Cliente"):
                    nc = pd.DataFrame([{"Nome": cn, "Loja": cl, "Cidade": cc}])
                    df_clientes = pd.concat([df_clientes, nc], ignore_index=True)
                    atualizar_planilha("Clientes", df_clientes)
                    st.rerun()
