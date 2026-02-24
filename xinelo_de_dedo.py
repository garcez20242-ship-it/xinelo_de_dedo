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
        # Não usamos rerun aqui para permitir múltiplas atualizações em sequência se necessário, 
        # mas ele será chamado ao final das funções principais.
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
        modo_edicao = c_head2.toggle("🔓 Editar", help="Habilitar renomeação, troca de imagem e exclusão")

        if df_estoque.empty:
            st.info("Nenhum modelo no sistema.")
        else:
            for idx, row in df_estoque.iterrows():
                with st.expander(f"👟 {row['Modelo']}"):
                    col_img, col_info = st.columns([1, 3])
                    
                    if pd.notna(row.get('Imagem')) and str(row['Imagem']).startswith('http'):
                        col_img.image(row['Imagem'], width=150)
                    else:
                        col_img.write("Sem foto")

                    if modo_edicao:
                        n_nome = col_info.text_input("Editar Nome", value=row['Modelo'], key=f"edit_n_{idx}")
                        n_img = col_info.text_input("Link Imagem", value=row.get('Imagem',''), key=f"edit_i_{idx}")
                        c_b1, c_b2 = col_info.columns(2)
                        if c_b1.button("Salvar Alterações ✅", key=f"btn_s_{idx}"):
                            df_estoque.at[idx, 'Modelo'] = n_nome
                            df_estoque.at[idx, 'Imagem'] = converter_link_drive(n_img)
                            atualizar_planilha("Estoque", df_estoque)
                            st.rerun()
                        if c_b2.button("Excluir Modelo 🗑️", key=f"btn_d_{idx}"):
                            df_estoque = df_estoque.drop(idx)
                            atualizar_planilha("Estoque", df_estoque)
                            st.rerun()
                    else:
                        col_info.write("**Saldos por Tamanho:**")
                        col_info.dataframe(row[TAMANHOS_PADRAO].to_frame().T, hide_index=True)

        st.divider()
        st.subheader("📥 Registrar Entrada de Mercadoria (Geral)")
        with st.form("entrada_geral"):
            c_ent1, c_ent2, c_ent3 = st.columns(3)
            a_mod = c_ent1.selectbox("Modelo", df_estoque['Modelo'].unique())
            a_tam = c_ent2.selectbox("Tamanho", TAMANHOS_PADRAO)
            a_qtd = c_ent3.number_input("Quantidade", min_value=1, step=1)
            
            if st.form_submit_button("Confirmar Entrada ➕"):
                idx_e = df_estoque.index[df_estoque['Modelo'] == a_mod][0]
                estoque_v = pd.to_numeric(df_estoque.at[idx_e, a_tam], errors='coerce')
                atual = int(estoque_v) if pd.notna(estoque_v) else 0
                
                df_estoque.at[idx_e, a_tam] = atual + a_qtd
                
                novo_h = pd.DataFrame([{
                    "Data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "Cliente": "FORNECEDOR",
                    "Resumo do Pedido": f"ENTRADA: {a_mod} ({a_tam}) +{a_qtd} un"
                }])
                df_pedidos = pd.concat([df_pedidos, novo_h], ignore_index=True)
                
                atualizar_planilha("Estoque", df_estoque)
                atualizar_planilha("Pedidos", df_pedidos)
                st.success("Entrada registrada!")
                st.rerun()

    # --- ABA 2: CARRINHO DE VENDAS ---
    with tab2:
        st.subheader("🛒 Carrinho de Vendas")
        if df_clientes.empty or df_estoque.empty:
            st.warning("Cadastre clientes e modelos primeiro.")
        else:
            c1, c2 = st.columns([1.5, 2.5])
            with c1:
                st.markdown("### Adicionar Itens")
                v_cli = st.selectbox("Selecione o Cliente", df_clientes['Nome'].unique())
                v_mod = st.selectbox("Selecione o Modelo", df_estoque['Modelo'].unique())
                v_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO)
                v_qtd = st.number_input("Quantidade (Máx 50)", min_value=1, max_value=50, step=1)
                
                if st.button("Adicionar ao Carrinho ➕"):
                    st.session_state.carrinho.append({
                        "Modelo": v_mod,
                        "Tamanho": v_tam,
                        "Qtd": v_qtd
                    })
                    st.toast("Item adicionado!")

            with c2:
                st.markdown(f"### Pedido de: {v_cli}")
                if not st.session_state.carrinho:
                    st.info("O carrinho está vazio.")
                else:
                    df_car = pd.DataFrame(st.session_state.carrinho)
                    st.table(df_car)
                    
                    col_c1, col_c2 = st.columns(2)
                    if col_c1.button("Limpar Carrinho 🗑️"):
                        st.session_state.carrinho = []
                        st.rerun()
                    
                    if col_c2.button("Finalizar Venda 🚀"):
                        resumo_final = []
                        erro_estoque = False
                        
                        for item in st.session_state.carrinho:
                            idx_e = df_estoque.index[df_estoque['Modelo'] == item['Modelo']][0]
                            estoque_v = pd.to_numeric(df_estoque.at[idx_e, item['Tamanho']], errors='coerce')
                            atual = int(estoque_v) if pd.notna(estoque_v) else 0
                            
                            if atual >= item['Qtd']:
                                df_estoque.at[idx_e, item['Tamanho']] = atual - item['Qtd']
                                resumo_final.append(f"{item['Modelo']} ({item['Tamanho']}) x{item['Qtd']}")
                            else:
                                st.error(f"Estoque insuficiente para {item['Modelo']} {item['Tamanho']} (Disponível: {atual})")
                                erro_estoque = True
                                break
                        
                        if not erro_estoque:
                            novo_p = pd.DataFrame([{
                                "Data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                                "Cliente": v_cli,
                                "Resumo do Pedido": " | ".join(resumo_final)
                            }])
                            df_pedidos = pd.concat([df_pedidos, novo_p], ignore_index=True)
                            
                            atualizar_planilha("Estoque", df_estoque)
                            atualizar_planilha("Pedidos", df_pedidos)
                            st.session_state.carrinho = []
                            st.success("Venda finalizada com sucesso!")
                            st.rerun()

    # --- ABA 3: CLIENTES (GERENCIAMENTO) ---
    with tab3:
        st.subheader("👥 Carteira de Clientes")
        if df_clientes.empty:
            st.info("Nenhum cliente cadastrado.")
        else:
            for idx, row in df_clientes.iterrows():
                with st.expander(f"👤 {row['Nome']} - {row.get('Loja', 'Sem Loja')}"):
                    c_cli1, c_cli2 = st.columns(2)
                    edit_n = c_cli1.text_input("Nome", value=row['Nome'], key=f"c_n_{idx}")
                    edit_l = c_cli2.text_input("Loja", value=row.get('Loja', ''), key=f"c_l_{idx}")
                    edit_t = c_cli1.text_input("Telefone", value=row.get('Telefone', ''), key=f"c_t_{idx}")
                    edit_c = c_cli2.text_input("Cidade", value=row.get('Cidade', ''), key=f"c_c_{idx}")
                    
                    col_cli_btn1, col_cli_btn2 = st.columns(2)
                    if col_cli_btn1.button("Salvar Alterações ✅", key=f"c_s_{idx}"):
                        df_clientes.at[idx, 'Nome'] = edit_n
                        df_clientes.at[idx, 'Loja'] = edit_l
                        df_clientes.at[idx, 'Telefone'] = edit_t
                        df_clientes.at[idx, 'Cidade'] = edit_c
                        atualizar_planilha("Clientes", df_clientes)
                        st.rerun()
                    if col_cli_btn2.button("Excluir Cliente 🗑️", key=f"c_d_{idx}"):
                        df_clientes = df_clientes.drop(idx)
                        atualizar_planilha("Clientes", df_clientes)
                        st.rerun()

    # --- ABA 4: HISTÓRICO ---
    with tab4:
        st.subheader("📜 Histórico de Movimentações")
        if df_pedidos.empty:
            st.info("Nenhuma movimentação registrada.")
        else:
            st.dataframe(df_pedidos.sort_index(ascending=False), use_container_width=True, hide_index=True)

    # --- ABA 5: CADASTRO ---
    with tab5:
        tipo = st.radio("O que deseja cadastrar?", ["Modelo de Sandália", "Novo Cliente"], horizontal=True)
        st.divider()
        
        if tipo == "Modelo de Sandália":
            with st.form("cad_novo_modelo"):
                m_n = st.text_input("Nome do Modelo")
                m_i = st.text_input("Link da Imagem (Drive)")
                st.write("**Quantidades Iniciais:**")
                cols = st.columns(5)
                q_dic = {t: cols[i%5].number_input(f"T {t}", min_value=0, step=1, key=f"q_new_{t}") for i, t in enumerate(TAMANHOS_PADRAO)}
                
                if st.form_submit_button("Cadastrar Modelo ✨"):
                    if m_n:
                        novo_m = {"Modelo": m_n, "Imagem": converter_link_drive(m_i)}
                        novo_m.update(q_dic)
                        df_estoque = pd.concat([df_estoque, pd.DataFrame([novo_m])], ignore_index=True)
                        atualizar_planilha("Estoque", df_estoque)
                        st.success("Modelo cadastrado!")
                        st.rerun()
                    else:
                        st.error("O nome é obrigatório.")
        else:
            with st.form("cad_novo_cliente"):
                c_n = st.text_input("Nome Completo")
                c_l = st.text_input("Nome da Loja")
                c_t = st.text_input("WhatsApp / Telefone")
                c_c = st.text_input("Cidade")
                
                if st.form_submit_button("Cadastrar Cliente 👤"):
                    if c_n:
                        novo_c = pd.DataFrame([{"Nome": c_n, "Loja": c_l, "Telefone": c_t, "Cidade": c_c}])
                        df_clientes = pd.concat([df_clientes, novo_c], ignore_index=True)
                        atualizar_planilha("Clientes", df_clientes)
                        st.success("Cliente cadastrado!")
                        st.rerun()
                    else:
                        st.error("O nome é obrigatório.")
