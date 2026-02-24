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
    """Converte links do Google Drive para link direto de imagem."""
    if not url or not isinstance(url, str):
        return url
    
    # Se for link do Drive (compartilhamento normal ou export)
    if "drive.google.com" in url:
        match = re.search(r'([-\w]{25,})', url)
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
                # ttl=0 garante que ele tente ler o dado mais fresco possível
                df = conn.read(spreadsheet=URL_PLANILHA, worksheet=nome, ttl=0).dropna(how='all')
                if df.empty: return pd.DataFrame(columns=colunas)
                df.columns = df.columns.str.strip()
                return df
            except: return pd.DataFrame(columns=colunas)
        
        df_e = ler_aba("Estoque", ["Modelo", "Imagem"] + TAMANHOS_PADRAO)
        df_p = ler_aba("Pedidos", ["Data", "Cliente", "Resumo do Pedido"])
        df_c = ler_aba("Clientes", ["Nome", "Loja", "Telefone", "Cidade"])
        
        # Limpeza visual: garantir que a coluna Imagem seja string e converter links
        if "Imagem" in df_e.columns:
            df_e["Imagem"] = df_e["Imagem"].apply(converter_link_drive)
            
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
        st.cache_data.clear() # Limpa o cache para a próxima leitura
    except Exception as e:
        st.error(f"Erro ao salvar na aba {aba}: {e}")

# --- ESTADO DO CARRINHO ---
if 'carrinho' not in st.session_state:
    st.session_state.carrinho = []

# --- INTERFACE ---
st.title("👡 Sistema Comercial Integrado")

if conn is not None:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Estoque & Aquisição", "🛒 Carrinho de Vendas", "👥 Clientes", "📜 Histórico", "✨ Cadastro"])

    # --- ABA 1: ESTOQUE & AQUISIÇÃO ---
    with tab1:
        c_head1, c_head2 = st.columns([5, 1])
        c_head1.subheader("📦 Inventário Atual")
        modo_edicao = c_head2.toggle("🔓 Editar", help="Habilitar edição e exclusão de modelos")

        if df_estoque.empty:
            st.info("Nenhum modelo no sistema.")
        else:
            for idx, row in df_estoque.iterrows():
                with st.expander(f"👟 {row['Modelo']}"):
                    col_img, col_info = st.columns([1, 3])
                    
                    # Lógica de Imagem
                    url_img = row.get('Imagem')
                    if pd.notna(url_img) and str(url_img).startswith('http'):
                        col_img.image(url_img, width=180)
                    else:
                        col_img.info("Sem imagem válida")
                    
                    if modo_edicao:
                        n_nome = col_info.text_input("Editar Nome", value=row['Modelo'], key=f"edit_m_n_{idx}")
                        n_img = col_info.text_input("Link Imagem (Drive)", value=row.get('Imagem',''), key=f"edit_m_i_{idx}")
                        
                        col_btn1, col_btn2 = col_info.columns(2)
                        if col_btn1.button("Salvar Alterações ✅", key=f"btn_m_s_{idx}"):
                            df_estoque.at[idx, 'Modelo'] = n_nome
                            df_estoque.at[idx, 'Imagem'] = converter_link_drive(n_img)
                            atualizar_planilha("Estoque", df_estoque)
                            st.rerun()
                        
                        with col_btn2:
                            confirma_m = st.checkbox("Confirmar exclusão?", key=f"check_m_{idx}")
                            if st.button("APAGAR MODELO 🗑️", key=f"btn_m_d_{idx}", disabled=not confirma_m):
                                df_estoque = df_estoque.drop(idx)
                                atualizar_planilha("Estoque", df_estoque)
                                st.rerun()
                    else:
                        col_info.dataframe(row[TAMANHOS_PADRAO].to_frame().T, hide_index=True)

        st.divider()
        st.subheader("📥 Registrar Entrada de Mercadoria")
        with st.form("entrada_geral"):
            c_ent1, c_ent2, c_ent3 = st.columns(3)
            a_mod = c_ent1.selectbox("Modelo", df_estoque['Modelo'].unique())
            a_tam = c_ent2.selectbox("Tamanho", TAMANHOS_PADRAO)
            a_qtd = c_ent3.number_input("Quantidade", min_value=1, step=1)
            if st.form_submit_button("Confirmar Entrada ➕"):
                idx_e = df_estoque.index[df_estoque['Modelo'] == a_mod][0]
                atual = int(pd.to_numeric(df_estoque.at[idx_e, a_tam], errors='coerce') or 0)
                df_estoque.at[idx_e, a_tam] = atual + a_qtd
                novo_h = pd.DataFrame([{"Data": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": "FORNECEDOR", "Resumo do Pedido": f"ENTRADA: {a_mod} ({a_tam}) +{a_qtd} un"}])
                df_pedidos = pd.concat([df_pedidos, novo_h], ignore_index=True)
                atualizar_planilha("Estoque", df_estoque)
                atualizar_planilha("Pedidos", df_pedidos)
                st.rerun()

    # --- ABA 2: CARRINHO DE VENDAS ---
    with tab2:
        st.subheader("🛒 Carrinho de Vendas")
        if df_clientes.empty or df_estoque.empty:
            st.warning("Cadastre clientes e modelos primeiro.")
        else:
            c1, c2 = st.columns([1.5, 2.5])
            with c1:
                v_cli = st.selectbox("Cliente", df_clientes['Nome'].unique())
                v_mod = st.selectbox("Modelo", df_estoque['Modelo'].unique())
                v_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO)
                v_qtd = st.number_input("Quantidade (Máx 50)", min_value=1, max_value=50)
                if st.button("Adicionar ao Carrinho ➕"):
                    st.session_state.carrinho.append({"Modelo": v_mod, "Tamanho": v_tam, "Qtd": v_qtd})
                    st.toast("Adicionado!")

            with c2:
                st.write(f"**Pedido: {v_cli}**")
                if st.session_state.carrinho:
                    st.table(pd.DataFrame(st.session_state.carrinho))
                    col_l, col_f = st.columns(2)
                    if col_l.button("Limpar Carrinho 🗑️"):
                        st.session_state.carrinho = []
                        st.rerun()
                    if col_f.button("Finalizar Venda 🚀"):
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
                        st.success("Venda registrada!")
                        st.rerun()

    # --- ABA 3: CLIENTES ---
    with tab3:
        st.subheader("👥 Gestão de Clientes")
        if df_clientes.empty:
            st.info("Nenhum cliente cadastrado.")
        else:
            for idx, row in df_clientes.iterrows():
                with st.expander(f"👤 {row['Nome']} ({row.get('Loja', 'S/L')})"):
                    col_edit, col_del = st.columns([3, 1])
                    with col_edit:
                        st.write(f"**Loja:** {row.get('Loja','')} | **Tel:** {row.get('Telefone','')} | **Cidade:** {row.get('Cidade','')}")
                    
                    with col_del:
                        confirma_c = st.checkbox("Confirmar?", key=f"check_c_{idx}")
                        if st.button("APAGAR CLIENTE 🗑️", key=f"btn_c_d_{idx}", disabled=not confirma_c):
                            df_clientes = df_clientes.drop(idx)
                            atualizar_planilha("Clientes", df_clientes)
                            st.rerun()

    # --- ABA 4: HISTÓRICO ---
    with tab4:
        st.subheader("📜 Histórico de Movimentações")
        if df_pedidos.empty:
            st.info("Nenhum registro encontrado.")
        else:
            for idx in reversed(df_pedidos.index):
                row = df_pedidos.loc[idx]
                with st.container():
                    col_txt, col_act = st.columns([5, 1])
                    col_txt.markdown(f"**{row['Data']}** | **{row['Cliente']}**")
                    col_txt.write(row['Resumo do Pedido'])
                    
                    confirma_h = col_act.checkbox("Confirmar?", key=f"check_h_{idx}")
                    if col_act.button("Apagar Log 🗑️", key=f"btn_h_d_{idx}", disabled=not confirma_h):
                        df_pedidos = df_pedidos.drop(idx)
                        atualizar_planilha("Pedidos", df_pedidos)
                        st.rerun()
                    st.divider()

    # --- ABA 5: CADASTRO ---
    with tab5:
        tipo = st.radio("Selecione o tipo de cadastro:", ["Modelo de Sandália", "Novo Cliente"], horizontal=True)
        if tipo == "Modelo de Sandália":
            with st.form("cad_m"):
                m_n = st.text_input("Nome do Modelo")
                m_i = st.text_input("Link da Imagem (Drive)")
                cols = st.columns(5)
                q_d = {t: cols[i%5].number_input(f"T {t}", min_value=0, key=f"new_m_{t}") for i, t in enumerate(TAMANHOS_PADRAO)}
                if st.form_submit_button("Cadastrar Modelo ✨"):
                    if m_n:
                        # Converte o link antes de salvar na planilha
                        link_direto = converter_link_drive(m_i)
                        ni = {"Modelo": m_n, "Imagem": link_direto}
                        ni.update(q_d)
                        df_estoque = pd.concat([df_estoque, pd.DataFrame([ni])], ignore_index=True)
                        atualizar_planilha("Estoque", df_estoque)
                        st.rerun()
        else:
            with st.form("cad_c"):
                cn = st.text_input("Nome"); cl = st.text_input("Loja"); ct = st.text_input("Telefone"); cc = st.text_input("Cidade")
                if st.form_submit_button("Cadastrar Cliente 👤"):
                    if cn:
                        nc = pd.DataFrame([{"Nome": cn, "Loja": cl, "Telefone": ct, "Cidade": cc}])
                        df_clientes = pd.concat([df_clientes, nc], ignore_index=True)
                        atualizar_planilha("Clientes", df_clientes)
                        st.rerun()
