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

# --- ESTADO DO CARRINHO (PERSISTÊNCIA NA SESSÃO) ---
if 'carrinho' not in st.session_state:
    st.session_state.carrinho = []

st.title("👡 Sistema Comercial Integrado")

if conn is not None:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Estoque & Aquisição", "🛒 Carrinho de Vendas", "👥 Clientes", "📜 Histórico", "✨ Cadastro"])

    # --- ABA 1: ESTOQUE & AQUISIÇÃO ---
    with tab1:
        st.subheader("Gerenciamento de Inventário")
        c_t1, c_t2 = st.columns([4, 1])
        modo_edicao = c_t2.toggle("🔓 Modo Edição", help="Libera alteração de nomes, imagens e exclusão")

        if df_estoque.empty:
            st.info("Nenhum modelo cadastrado.")
        else:
            for idx, row in df_estoque.iterrows():
                with st.expander(f"📦 {row['Modelo']}"):
                    col_img, col_info, col_aq = st.columns([1, 2, 1.5])
                    
                    # 1. Imagem
                    if pd.notna(row.get('Imagem')) and str(row['Imagem']).startswith('http'):
                        col_img.image(row['Imagem'], width=150)
                    else:
                        col_img.info("Sem foto")

                    # 2. Informações ou Edição
                    if modo_edicao:
                        n_nome = col_info.text_input("Editar Nome", value=row['Modelo'], key=f"en_{idx}")
                        n_img = col_info.text_input("Link Imagem", value=row.get('Imagem',''), key=f"ei_{idx}")
                        c_btn1, c_btn2 = col_info.columns(2)
                        if c_btn1.button("Salvar Alterações ✅", key=f"sv_{idx}"):
                            df_estoque.at[idx, 'Modelo'] = n_nome
                            df_estoque.at[idx, 'Imagem'] = converter_link_drive(n_img)
                            atualizar_planilha("Estoque", df_estoque)
                        if c_btn2.button("Excluir Modelo 🗑️", key=f"del_{idx}"):
                            df_estoque = df_estoque.drop(idx)
                            atualizar_planilha("Estoque", df_estoque)
                    else:
                        col_info.markdown(f"### {row['Modelo']}")
                        col_info.write("**Saldos Atuais:**")
                        col_info.dataframe(row[TAMANHOS_PADRAO].to_frame().T, hide_index=True)

                    # 3. Registro de Aquisição (Somar ao Estoque)
                    col_aq.markdown("#### ➕ Registrar Entrada")
                    a_tam = col_aq.selectbox("Tamanho para entrada", TAMANHOS_PADRAO, key=f"aq_t_{idx}")
                    a_qtd = col_aq.number_input("Quantidade adquirida", min_value=1, key=f"aq_q_{idx}")
                    if col_aq.button("Confirmar Entrada 📥", key=f"aq_b_{idx}"):
                        atual = int(pd.to_numeric(df_estoque.at[idx, a_tam], errors='coerce') or 0)
                        df_estoque.at[idx, a_tam] = atual + a_qtd
                        atualizar_planilha("Estoque", df_estoque)
                        
                        novo_h = pd.DataFrame([{
                            "Data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "Cliente": "FORNECEDOR",
                            "Resumo do Pedido": f"ENTRADA: {row['Modelo']} ({a_tam}) +{a_qtd} un"
                        }])
                        df_pedidos = pd.concat([df_pedidos, novo_h], ignore_index=True)
                        atualizar_planilha("Pedidos", df_pedidos)

    # --- ABA 2: CARRINHO DE VENDAS (SAÍDA) ---
    with tab2:
        st.subheader("🛒 Registrar Venda")
        if df_clientes.empty or df_estoque.empty:
            st.warning("Cadastre clientes e modelos primeiro.")
        else:
            c1, c2 = st.columns([1.5, 2.5])
            with c1:
                st.markdown("### 📝 Adicionar ao Carrinho")
                v_cli = st.selectbox("Selecione o Cliente", df_clientes['Nome'].unique())
                v_mod = st.selectbox("Selecione o Modelo", df_estoque['Modelo'].unique())
                v_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO)
                v_qtd = st.number_input("Quantidade (Máx 50)", min_value=1, max_value=50)
                
                if st.button("Adicionar Item ➕"):
                    st.session_state.carrinho.append({"Modelo": v_mod, "Tamanho": v_tam, "Qtd": v_qtd})
                    st.toast(f"Item {v_mod} adicionado!")

            with c2:
                st.markdown(f"### 🛍️ Carrinho de {v_cli}")
                if not st.session_state.carrinho:
                    st.info("O carrinho está vazio.")
                else:
                    st.table(pd.DataFrame(st.session_state.carrinho))
                    col_limpar, col_finalizar = st.columns(2)
                    
                    if col_limpar.button("Limpar Carrinho 🗑️"):
                        st.session_state.carrinho = []
                        st.rerun()
                    
                    if col_finalizar.button("Finalizar Venda 🚀"):
                        resumo_itens = []
                        erro = False
                        for item in st.session_state.carrinho:
                            idx_e = df_estoque.index[df_estoque['Modelo'] == item['Modelo']][0]
                            atual = int(pd.to_numeric(df_estoque.at[idx_e, item['Tamanho']], errors='coerce') or 0)
                            if atual < item['Qtd']:
                                st.error(f"Estoque insuficiente para {item['Modelo']} {item['Tamanho']} (Disponível: {atual})")
                                erro = True
                                break
                        
                        if not erro:
                            for item in st.session_state.carrinho:
                                idx_e = df_estoque.index[df_estoque['Modelo'] == item['Modelo']][0]
                                df_estoque.at[idx_e, item['Tamanho']] = int(df_estoque.at[idx_e, item['Tamanho']]) - item['Qtd']
                                resumo_itens.append(f"{item['Modelo']} ({item['Tamanho']}) x{item['Qtd']}")
                            
                            atualizar_planilha("Estoque", df_estoque)
                            novo_p = pd.DataFrame([{"Data": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": v_cli, "Resumo do Pedido": " | ".join(resumo_itens)}])
                            df_pedidos = pd.concat([df_pedidos, novo_p], ignore_index=True)
                            atualizar_planilha("Pedidos", df_pedidos)
                            st.session_state.carrinho = []
                            st.success("Venda processada com sucesso!")

    # --- ABA 3: CLIENTES (GESTÃO COMPLETA) ---
    with tab3:
        st.subheader("Base de Clientes")
        if not df_clientes.empty:
            for idx, row in df_clientes.iterrows():
                with st.expander(f"👤 {row['Nome']} - {row.get('Loja', '')}"):
                    c_c1, c_c2, c_c3 = st.columns(3)
                    n_c = c_c1.text_input("Nome", value=row['Nome'], key=f"cn_{idx}")
                    l_c = c_c2.text_input("Loja", value=row.get('Loja', ''), key=f"cl_{idx}")
                    t_c = c_c3.text_input("Telefone", value=row.get('Telefone', ''), key=f"ct_{idx}")
                    cid_c = st.text_input("Cidade", value=row.get('Cidade', ''), key=f"ccid_{idx}")
                    
                    col_b1, col_b2 = st.columns(2)
                    if col_b1.button("Salvar Dados ✅", key=f"sc_{idx}"):
                        df_clientes.at[idx, 'Nome'] = n_c
                        df_clientes.at[idx, 'Loja'] = l_c
                        df_clientes.at[idx, 'Telefone'] = t_c
                        df_clientes.at[idx, 'Cidade'] = cid_c
                        atualizar_planilha("Clientes", df_clientes)
                    if col_b2.button("Remover Cliente 🗑️", key=f"rc_{idx}"):
                        df_clientes = df_clientes.drop(idx)
                        atualizar_planilha("Clientes", df_clientes)

    # --- ABA 4: HISTÓRICO ---
    with tab4:
        st.subheader("📜 Movimentações Completas")
        st.dataframe(df_pedidos.sort_index(ascending=False), use_container_width=True, hide_index=True)

    # --- ABA 5: CADASTRO ---
    with tab5:
        st.subheader("✨ Novos Registros")
        tipo = st.radio("Selecione o tipo:", ["Modelo de Sandália", "Novo Cliente"], horizontal=True)
        
        if tipo == "Modelo de Sandália":
            with st.form("cad_modelo_full"):
                m_n = st.text_input("Nome do Modelo")
                m_i = st.text_input("Link da Imagem (Google Drive)")
                st.write("**Estoque Inicial:**")
                cols = st.columns(5)
                q_d = {t: cols[i%5].number_input(f"T {t}", min_value=0, key=f"new_m_{t}") for i, t in enumerate(TAMANHOS_PADRAO)}
                if st.form_submit_button("Cadastrar Modelo ✨"):
                    if m_n:
                        ni = {"Modelo": m_n, "Imagem": converter_link_drive(m_i)}; ni.update(q_d)
                        df_estoque = pd.concat([df_estoque, pd.DataFrame([ni])], ignore_index=True)
                        atualizar_planilha("Estoque", df_estoque)
        else:
            with st.form("cad_cliente_full"):
                c_n = st.text_input("Nome Completo")
                c_l = st.text_input("Nome da Loja")
                c_t = st.text_input("WhatsApp / Telefone")
                c_c = st.text_input("Cidade")
                if st.form_submit_button("Cadastrar Cliente 👤"):
                    if c_n:
                        nc = pd.DataFrame([{"Nome": c_n, "Loja": c_l, "Telefone": c_t, "Cidade": c_c}])
                        df_clientes = pd.concat([df_clientes, nc], ignore_index=True)
                        atualizar_planilha("Clientes", df_clientes)
