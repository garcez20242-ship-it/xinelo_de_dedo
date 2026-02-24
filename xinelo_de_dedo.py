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
        # Extrai o ID do arquivo usando expressão regular
        match = re.search(r'[-\w]{25,}', url)
        if match:
            file_id = match.group()
            return f"https://drive.google.com/uc?export=view&id={file_id}"
    return url

# --- FUNÇÃO DE CARREGAMENTO (USANDO SECRETS E CONTA DE SERVIÇO) ---
@st.cache_data(ttl=0)
def carregar_dados():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        def ler_aba(nome, colunas):
            try:
                df = conn.read(spreadsheet=URL_PLANILHA, worksheet=nome, ttl=0).dropna(how='all')
                if df.empty:
                    return pd.DataFrame(columns=colunas)
                df.columns = df.columns.str.strip()
                return df
            except Exception:
                return pd.DataFrame(columns=colunas)

        df_e = ler_aba("Estoque", ["Modelo", "Imagem"] + TAMANHOS_PADRAO)
        df_p = ler_aba("Pedidos", ["Data", "Cliente", "Resumo do Pedido"])
        df_c = ler_aba("Clientes", ["Nome", "Loja", "Telefone", "Cidade"])
        
        return conn, df_e, df_p, df_c
    except Exception as e:
        st.error(f"Erro na conexão com a planilha: {e}")
        return None, None, None, None

conn, df_estoque, df_pedidos, df_clientes = carregar_dados()

# --- FUNÇÃO PARA SALVAR ---
def atualizar_planilha(aba, dataframe):
    # Converte tudo para string para evitar erros de serialização no Google Sheets
    df_limpo = dataframe.astype(str)
    # Remove colunas fantasmas geradas por leitura incorreta
    df_limpo = df_limpo.loc[:, ~df_limpo.columns.str.contains('^Unnamed')]
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_limpo)
        st.cache_data.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao salvar na aba {aba}: {e}")

# --- INTERFACE PRINCIPAL ---
st.title("👡 Sistema de Gestão Comercial - Xinelo de Dedo")

if conn is not None:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Estoque", "🛒 Nova Venda", "👥 Clientes", "📜 Histórico", "✨ Cadastro"])

    # --- ABA 1: ESTOQUE (VISUALIZAÇÃO, EDIÇÃO E EXCLUSÃO) ---
    with tab1:
        st.subheader("Gerenciamento de Inventário")
        if df_estoque.empty:
            st.info("Nenhum modelo cadastrado no estoque.")
        else:
            for idx, row in df_estoque.iterrows():
                with st.expander(f"📦 Modelo: {row['Modelo']}"):
                    c1, c2 = st.columns([1, 2])
                    
                    # Exibição da Imagem
                    link_img = row.get('Imagem', "")
                    if pd.notna(link_img) and str(link_img).startswith('http'):
                        c1.image(link_img, width=250)
                    else:
                        c1.warning("Sem imagem cadastrada ou link inválido.")

                    # Edição de Informações Básicas
                    novo_nome = c2.text_input("Editar Nome do Modelo", value=row['Modelo'], key=f"edit_nome_{idx}")
                    novo_link = c2.text_input("Editar Link da Imagem", value=link_img if pd.notna(link_img) else "", key=f"edit_img_{idx}")
                    
                    col_btn1, col_btn2 = c2.columns(2)
                    if col_btn1.button("Salvar Alterações ✅", key=f"btn_salvar_{idx}"):
                        df_estoque.at[idx, 'Modelo'] = novo_nome
                        df_estoque.at[idx, 'Imagem'] = converter_link_drive(novo_link)
                        atualizar_planilha("Estoque", df_estoque)
                    
                    if col_btn2.button("Excluir Modelo 🗑️", key=f"btn_excluir_{idx}"):
                        df_estoque = df_estoque.drop(idx)
                        atualizar_planilha("Estoque", df_estoque)

                    st.divider()
                    st.write("**Ajuste de Quantidades por Tamanho:**")
                    # Editor de dados para os tamanhos
                    df_tam_edit = row[TAMANHOS_PADRAO].to_frame().T
                    res_edit = st.data_editor(df_tam_edit, key=f"editor_estoque_{idx}", hide_index=True)
                    
                    if st.button("Confirmar Atualização de Quantidades 🔄", key=f"btn_update_qtd_{idx}"):
                        for t in TAMANHOS_PADRAO:
                            df_estoque.at[idx, t] = res_edit.at[0, t]
                        atualizar_planilha("Estoque", df_estoque)

    # --- ABA 2: NOVA VENDA (COM BAIXA NO ESTOQUE) ---
    with tab2:
        st.subheader("Registrar Novo Pedido")
        if df_clientes.empty or df_estoque.empty:
            st.warning("É necessário ter clientes e modelos cadastrados para realizar uma venda.")
        else:
            with st.form("form_venda"):
                c1, c2 = st.columns(2)
                v_cli = c1.selectbox("Selecione o Cliente", df_clientes['Nome'].unique())
                v_mod = c2.selectbox("Selecione o Modelo", df_estoque['Modelo'].unique())
                
                c3, c4 = st.columns(2)
                v_tam = c3.selectbox("Tamanho", TAMANHOS_PADRAO)
                v_qtd = c4.number_input("Quantidade", min_value=1, step=1)
                
                if st.form_submit_button("Finalizar Venda 🚀"):
                    # Localiza o índice do modelo selecionado
                    idx_e = df_estoque.index[df_estoque['Modelo'] == v_mod][0]
                    # Verifica estoque disponível
                    estoque_atual = int(pd.to_numeric(df_estoque.at[idx_e, v_tam], errors='coerce') or 0)
                    
                    if estoque_atual >= v_qtd:
                        # 1. Subtrai do estoque
                        df_estoque.at[idx_e, v_tam] = estoque_atual - v_qtd
                        atualizar_planilha("Estoque", df_estoque)
                        
                        # 2. Registra no Histórico de Pedidos
                        novo_pedido = pd.DataFrame([{
                            "Data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "Cliente": v_cli,
                            "Resumo do Pedido": f"{v_mod} ({v_tam}) - {v_qtd} un"
                        }])
                        df_pedidos = pd.concat([df_pedidos, novo_pedido], ignore_index=True)
                        atualizar_planilha("Pedidos", df_pedidos)
                        st.success(f"Venda registrada com sucesso! {v_qtd} unidades retiradas do estoque.")
                    else:
                        st.error(f"Estoque insuficiente! O saldo atual do tamanho {v_tam} para o modelo {v_mod} é de {estoque_atual} unidades.")

    # --- ABA 3: CLIENTES (GESTÃO) ---
    with tab3:
        st.subheader("Gerenciar Carteira de Clientes")
        if df_clientes.empty:
            st.info("Nenhum cliente cadastrado.")
        else:
            for idx, row in df_clientes.iterrows():
                with st.expander(f"👤 {row['Nome']} - {row.get('Loja', 'Sem Loja')}"):
                    c1, c2, c3 = st.columns(3)
                    
                    edit_nome_c = c1.text_input("Nome", value=row['Nome'], key=f"c_nome_{idx}")
                    edit_loja_c = c2.text_input("Loja", value=row.get('Loja', ''), key=f"c_loja_{idx}")
                    edit_tel_c = c3.text_input("Telefone", value=row.get('Telefone', ''), key=f"c_tel_{idx}")
                    
                    c4, c5 = st.columns([2, 1])
                    edit_cid_c = c4.text_input("Cidade", value=row.get('Cidade', ''), key=f"c_cid_{idx}")
                    
                    st.write(" ")
                    col_btn_c1, col_btn_c2 = st.columns(2)
                    if col_btn_c1.button("Salvar Alterações Cliente ✅", key=f"btn_c_save_{idx}"):
                        df_clientes.at[idx, 'Nome'] = edit_nome_c
                        df_clientes.at[idx, 'Loja'] = edit_loja_c
                        df_clientes.at[idx, 'Telefone'] = edit_tel_c
                        df_clientes.at[idx, 'Cidade'] = edit_cid_c
                        atualizar_planilha("Clientes", df_clientes)
                        
                    if col_btn_c2.button("Remover Cliente 🗑️", key=f"btn_c_del_{idx}"):
                        df_clientes = df_clientes.drop(idx)
                        atualizar_planilha("Clientes", df_clientes)

    # --- ABA 4: HISTÓRICO (VISUALIZAÇÃO DE VENDAS) ---
    with tab4:
        st.subheader("📜 Histórico Geral de Vendas")
        if df_pedidos.empty:
            st.info("Ainda não foram registradas vendas.")
        else:
            # Mostra os pedidos mais recentes primeiro
            st.dataframe(
                df_pedidos[["Data", "Cliente", "Resumo do Pedido"]].sort_index(ascending=False), 
                use_container_width=True, 
                hide_index=True
            )

    # --- ABA 5: CADASTRO (NOVOS MODELOS E CLIENTES) ---
    with tab5:
        st.subheader("✨ Novos Cadastros")
        opcao = st.radio("Selecione o tipo de cadastro:", ["Modelo de Sandália", "Novo Cliente"], horizontal=True)
        
        st.divider()
        
        if opcao == "Modelo de Sandália":
            with st.form("form_cad_modelo"):
                m_nome = st.text_input("Nome do Modelo (Ex: Nuvem Pro)")
                m_link = st.text_input("Link da Imagem (Google Drive)")
                st.caption("Certifique-se de que a imagem no Drive está como 'Qualquer pessoa com o link'.")
                
                st.write("**Quantidade Inicial por Tamanho:**")
                cols = st.columns(5)
                qtd_iniciais = {}
                for i, t in enumerate(TAMANHOS_PADRAO):
                    qtd_iniciais[t] = cols[i % 5].number_input(f"Tam {t}", min_value=0, step=1, key=f"new_qtd_{t}")
                
                if st.form_submit_button("Cadastrar Modelo ✨"):
                    if m_nome:
                        # Prepara o novo dicionário
                        nova_linha = {
                            "Modelo": m_nome, 
                            "Imagem": converter_link_drive(m_link)
                        }
                        nova_linha.update(qtd_iniciais)
                        
                        df_estoque = pd.concat([df_estoque, pd.DataFrame([nova_linha])], ignore_index=True)
                        atualizar_planilha("Estoque", df_estoque)
                    else:
                        st.error("O nome do modelo é obrigatório.")
        
        else:
            with st.form("form_cad_cliente"):
                c_nome = st.text_input("Nome Completo do Cliente")
                c_loja = st.text_input("Nome da Loja")
                c_tel = st.text_input("Telefone / WhatsApp")
                c_cid = st.text_input("Cidade")
                
                if st.form_submit_button("Cadastrar Cliente 👤"):
                    if c_nome:
                        novo_c = pd.DataFrame([{
                            "Nome": c_nome, 
                            "Loja": c_loja, 
                            "Telefone": c_tel, 
                            "Cidade": c_cid
                        }])
                        df_clientes = pd.concat([df_clientes, novo_c], ignore_index=True)
                        atualizar_planilha("Clientes", df_clientes)
                    else:
                        st.error("O nome do cliente é obrigatório.")
