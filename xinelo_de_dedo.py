import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
import re

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão de Sandálias Nuvem", layout="wide", page_icon="👡")

# Configurações de IDs (Baseado no seu link de pasta)
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
ID_PASTA_FOTOS = "1JbPRCBYbCI4pByztZgtlH_6NoZXm_Myq" 
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- FUNÇÃO PARA CONECTAR AO DRIVE API USANDO SUA CREDENCIAL ---
def get_drive_service():
    # Puxa as credenciais que você já configurou no secrets.toml para o GSheets
    info = st.secrets["connections"]["gsheets"]
    creds = service_account.Credentials.from_service_account_info(
        info, 
        scopes=['https://www.googleapis.com/auth/drive']
    )
    return build('drive', 'v3', credentials=creds)

# --- FUNÇÃO DE UPLOAD AUTOMÁTICO PARA O DRIVE ---
def upload_para_drive(file):
    try:
        service = get_drive_service()
        file_metadata = {
            'name': f"FOTO_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.name}",
            'parents': [ID_PASTA_FOTOS]
        }
        media = MediaIoBaseUpload(io.BytesIO(file.getvalue()), mimetype=file.type, resumable=True)
        uploaded_file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        file_id = uploaded_file.get('id')
        
        # Torna a imagem visível para o App (Leitura pública via link direto)
        service.permissions().create(fileId=file_id, body={'type': 'anyone', 'role': 'reader'}).execute()
        
        return f"https://drive.google.com/uc?export=view&id={file_id}"
    except Exception as e:
        st.error(f"Erro no upload para o Drive: {e}")
        return ""

# --- CARREGAMENTO DE DADOS ---
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
        st.error(f"Erro na conexão com a planilha: {e}")
        return None, None, None, None

conn, df_estoque, df_pedidos, df_clientes = carregar_dados()

def atualizar_planilha(aba, dataframe):
    df_limpo = dataframe.astype(str)
    df_limpo = df_limpo.loc[:, ~df_limpo.columns.str.contains('^Unnamed')]
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_limpo)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Erro ao salvar na planilha: {e}")

# --- INTERFACE ---
st.title("👡 Gestão Comercial - Sandálias Nuvem")

if conn is not None:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Estoque", "🛒 Vendas", "👥 Clientes", "📜 Histórico", "✨ Cadastro"])

    # --- ABA 1: ESTOQUE ---
    with tab1:
        c_head1, c_head2 = st.columns([5, 1])
        c_head1.subheader("📦 Inventário Atual")
        modo_edicao = c_head2.toggle("🔓 Editar")

        if df_estoque.empty:
            st.info("Nenhum modelo no sistema.")
        else:
            for idx, row in df_estoque.iterrows():
                with st.expander(f"👟 {row['Modelo']}"):
                    col_img, col_info = st.columns([1, 3])
                    
                    if pd.notna(row.get('Imagem')) and str(row['Imagem']).startswith('http'):
                        col_img.image(row['Imagem'], width=180)
                    
                    if modo_edicao:
                        n_nome = col_info.text_input("Nome", value=row['Modelo'], key=f"ed_n_{idx}")
                        nova_foto = col_info.file_uploader("Trocar Foto", type=['png','jpg','jpeg'], key=f"up_ed_{idx}")
                        
                        cb1, cb2 = col_info.columns(2)
                        if cb1.button("Salvar ✅", key=f"sv_{idx}"):
                            df_estoque.at[idx, 'Modelo'] = n_nome
                            if nova_foto:
                                with st.spinner("Enviando foto para o Drive..."):
                                    df_estoque.at[idx, 'Imagem'] = upload_para_drive(nova_foto)
                            atualizar_planilha("Estoque", df_estoque)
                            st.rerun()
                        
                        with cb2:
                            if st.checkbox("Confirmar exclusão?", key=f"chk_m_{idx}"):
                                if st.button("APAGAR MODELO 🗑️", key=f"del_m_{idx}"):
                                    df_estoque = df_estoque.drop(idx)
                                    atualizar_planilha("Estoque", df_estoque)
                                    st.rerun()
                    else:
                        col_info.dataframe(row[TAMANHOS_PADRAO].to_frame().T, hide_index=True)

        st.divider()
        st.subheader("📥 Registrar Entrada")
        with st.form("entrada"):
            c1, c2, c3 = st.columns(3)
            mod_e = c1.selectbox("Modelo", df_estoque['Modelo'].unique() if not df_estoque.empty else [])
            tam_e = c2.selectbox("Tamanho", TAMANHOS_PADRAO)
            qtd_e = c3.number_input("Quantidade", min_value=1)
            if st.form_submit_button("Confirmar Entrada ➕"):
                idx_e = df_estoque.index[df_estoque['Modelo'] == mod_e][0]
                estoque_atual = int(pd.to_numeric(df_estoque.at[idx_e, tam_e], errors='coerce') or 0)
                df_estoque.at[idx_e, tam_e] = estoque_atual + qtd_e
                
                novo_h = pd.DataFrame([{"Data": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": "FORNECEDOR", "Resumo do Pedido": f"ENTRADA: {mod_e} ({tam_e}) +{qtd_e}"}])
                df_pedidos = pd.concat([df_pedidos, novo_h], ignore_index=True)
                
                atualizar_planilha("Estoque", df_estoque)
                atualizar_planilha("Pedidos", df_pedidos)
                st.rerun()

    # --- ABA 2: VENDAS (CARRINHO) ---
    with tab2:
        if 'carrinho' not in st.session_state: st.session_state.carrinho = []
        st.subheader("🛒 Carrinho")
        if not df_clientes.empty and not df_estoque.empty:
            v_cli = st.selectbox("Selecione o Cliente", df_clientes['Nome'].unique())
            c1, c2 = st.columns([1.5, 2.5])
            with c1:
                v_mod = st.selectbox("Modelo", df_estoque['Modelo'].unique())
                v_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO)
                v_qtd = st.number_input("Qtd", min_value=1, max_value=50)
                if st.button("Adicionar ao Carrinho ➕"):
                    st.session_state.carrinho.append({"Modelo": v_mod, "Tamanho": v_tam, "Qtd": v_qtd})
            with c2:
                if st.session_state.carrinho:
                    st.table(pd.DataFrame(st.session_state.carrinho))
                    if st.button("Finalizar Venda 🚀"):
                        resumo = []
                        for item in st.session_state.carrinho:
                            idx_e = df_estoque.index[df_estoque['Modelo'] == item['Modelo']][0]
                            df_estoque.at[idx_e, item['Tamanho']] = int(df_estoque.at[idx_e, item['Tamanho']]) - item['Qtd']
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
                col_t.write(f"Loja: {row.get('Loja','')} | Tel: {row.get('Telefone','')} | Cidade: {row.get('Cidade','')}")
                if col_d.checkbox("Confirmar?", key=f"c_cl_{idx}"):
                    if col_d.button("Apagar Cliente 🗑️", key=f"d_cl_{idx}"):
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
            if c_a.checkbox("Confirmar?", key=f"c_h_{idx}"):
                if c_a.button("Apagar Registro 🗑️", key=f"d_h_{idx}"):
                    df_pedidos = df_pedidos.drop(idx)
                    atualizar_planilha("Pedidos", df_pedidos)
                    st.rerun()

    # --- ABA 5: CADASTRO ---
    with tab5:
        tipo = st.radio("O que deseja cadastrar?", ["Modelo", "Cliente"], horizontal=True)
        if tipo == "Modelo":
            with st.form("f_mod"):
                m_n = st.text_input("Nome do Modelo")
                m_f = st.file_uploader("Foto do Modelo (Upload Direto para o Drive)", type=['png','jpg','jpeg'])
                cols = st.columns(5)
                q_d = {t: cols[i%5].number_input(f"T {t}", min_value=0) for i, t in enumerate(TAMANHOS_PADRAO)}
                if st.form_submit_button("Cadastrar Modelo ✨"):
                    if m_n:
                        with st.spinner("Enviando imagem para o Google Drive..."):
                            img_url = upload_para_drive(m_f) if m_f else ""
                        ni = {"Modelo": m_n, "Imagem": img_url}
                        ni.update(q_d)
                        df_estoque = pd.concat([df_estoque, pd.DataFrame([ni])], ignore_index=True)
                        atualizar_planilha("Estoque", df_estoque)
                        st.rerun()
        else:
            with st.form("f_cli"):
                cn = st.text_input("Nome"); cl = st.text_input("Loja"); ct = st.text_input("Telefone"); cc = st.text_input("Cidade")
                if st.form_submit_button("Cadastrar Cliente 👤"):
                    nc = pd.DataFrame([{"Nome": cn, "Loja": cl, "Telefone": ct, "Cidade": cc}])
                    df_clientes = pd.concat([df_clientes, nc], ignore_index=True)
                    atualizar_planilha("Clientes", df_clientes)
                    st.rerun()
                    
