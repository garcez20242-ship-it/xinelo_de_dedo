import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import re

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão de Sandálias Nuvem", layout="wide", page_icon="👡")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- FUNÇÃO PARA CONVERTER LINK DO DRIVE EM LINK DE IMAGEM DIRETA ---
def converter_link_drive(url):
    if "drive.google.com" in url:
        # Extrai o ID do arquivo do link
        match = re.search(r'[-\w]{25,}', url)
        if match:
            file_id = match.group()
            return f"https://drive.google.com/uc?export=view&id={file_id}"
    return url

# --- FUNÇÃO DE CARREGAMENTO ---
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

    # Adicionada a coluna "Imagem" no estoque
    df_e = ler_aba("Estoque", ["Modelo", "Imagem"] + TAMANHOS_PADRAO)
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

# --- INTERFACE ---
st.title("👡 Sistema de Gestão com Imagens")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Estoque", "🛒 Nova Venda", "👥 Clientes", "📜 Histórico", "✨ Cadastro"])

# --- ABA 1: ESTOQUE (COM IMAGENS) ---
with tab1:
    st.subheader("Gerenciar Inventário e Fotos")
    if df_estoque.empty:
        st.info("Nenhum modelo cadastrado.")
    else:
        for idx, row in df_estoque.iterrows():
            with st.expander(f"📦 {row['Modelo']}"):
                col_img, col_txt = st.columns([1, 2])
                
                # Exibição da Imagem
                link_img = row.get('Imagem', "")
                if pd.notna(link_img) and str(link_img).startswith('http'):
                    col_img.image(link_img, width=200)
                else:
                    col_img.info("Sem foto")

                # Edição
                novo_nome = col_txt.text_input("Nome do Modelo", value=row['Modelo'], key=f"n_{idx}")
                novo_link = col_txt.text_input("Link da Imagem (Drive ou Web)", value=link_img, key=f"img_{idx}")
                
                c1, c2 = col_txt.columns(2)
                if c1.button("Salvar Alterações ✅", key=f"sv_{idx}"):
                    df_estoque.at[idx, 'Modelo'] = novo_nome
                    df_estoque.at[idx, 'Imagem'] = converter_link_drive(novo_link)
                    atualizar_planilha("Estoque", df_estoque)
                
                if c2.button("Excluir Modelo 🗑️", key=f"del_{idx}"):
                    df_estoque = df_estoque.drop(idx)
                    atualizar_planilha("Estoque", df_estoque)

                st.write("**Estoque atual:**")
                df_temp = row[TAMANHOS_PADRAO].to_frame().T
                res_edit = st.data_editor(df_temp, key=f"ed_{idx}", hide_index=True)
                if st.button("Atualizar Quantidades 🔄", key=f"q_{idx}"):
                    for t in TAMANHOS_PADRAO:
                        df_estoque.at[idx, t] = res_edit.at[0, t]
                    atualizar_planilha("Estoque", df_estoque)

# --- ABA 5: CADASTRO (COM IMAGEM) ---
with tab5:
    st.subheader("✨ Novos Registros")
    escolha = st.radio("O que cadastrar?", ["Modelo", "Cliente"], horizontal=True)
    
    if escolha == "Modelo":
        with st.form("f_mod"):
            m_n = st.text_input("Nome do Modelo")
            m_i = st.text_input("Link da Imagem (Google Drive)")
            st.caption("Dica: Clique em 'Compartilhar' no Drive e mude para 'Qualquer pessoa com o link' antes de colar o link aqui.")
            
            cols = st.columns(5)
            q_dic = {t: cols[i%5].number_input(t, min_value=0) for i, t in enumerate(TAMANHOS_PADRAO)}
            
            if st.form_submit_button("Cadastrar Modelo"):
                if m_n:
                    link_direto = converter_link_drive(m_i)
                    nl = {"Modelo": m_n, "Imagem": link_direto}
                    nl.update(q_dic)
                    df_estoque = pd.concat([df_estoque, pd.DataFrame([nl])], ignore_index=True)
                    atualizar_planilha("Estoque", df_estoque)
    else:
        # (O resto do código de cliente permanece igual ao anterior)
        with st.form("f_cli"):
            cn = st.text_input("Nome"); cl = st.text_input("Loja")
            if st.form_submit_button("Salvar Cliente"):
                nc = pd.DataFrame([{"Nome": cn, "Loja": cl}])
                df_clientes = pd.concat([df_clientes, nc], ignore_index=True)
                atualizar_planilha("Clientes", df_clientes)

# (Abas de Venda e Histórico permanecem as mesmas do código anterior)
