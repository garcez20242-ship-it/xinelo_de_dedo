import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão de Sandálias Nuvem", layout="wide", page_icon="👡")

# --- CONEXÃO DIRETA COM A NOVA PLANILHA ---
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

@st.cache_data(ttl=0)
def carregar_dados():
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Carregar Estoque
    try:
        estoque = conn.read(spreadsheet=URL_PLANILHA, worksheet="Estoque", ttl=0).dropna(how='all')
    except:
        estoque = pd.DataFrame(columns=["Modelo", "Imagem"] + TAMANHOS_PADRAO)
    
    # Carregar Pedidos
    try:
        pedidos = conn.read(spreadsheet=URL_PLANILHA, worksheet="Pedidos", ttl=0).dropna(how='all')
    except:
        pedidos = pd.DataFrame(columns=["Data", "Cliente", "Telefone", "Loja", "Cidade", "Item", "Qtd"])
        
    # Carregar Clientes
    try:
        clientes = conn.read(spreadsheet=URL_PLANILHA, worksheet="Clientes", ttl=0).dropna(how='all')
    except:
        clientes = pd.DataFrame(columns=["Nome", "Loja", "Telefone", "Cidade"])
    
    # Limpeza de colunas
    for df in [estoque, pedidos, clientes]:
        df.columns = df.columns.str.strip()
    
    return conn, estoque, pedidos, clientes

try:
    conn, df_estoque, df_pedidos, df_clientes = carregar_dados()
except Exception as e:
    st.error(f"Erro na conexão: {e}")
    st.stop()

# --- INTERFACE ---
st.title("👡 Sistema Comercial - Xinelo de Dedo")
abas = st.tabs(["📊 Estoque", "🛒 Nova Venda", "👥 Clientes", "📜 Histórico", "✨ Cadastro Modelos"])

# --- ABA 1: ESTOQUE ---
with abas[0]:
    st.subheader("Disponibilidade de Inventário")
    if not df_estoque.empty:
        col_tabela, col_foto = st.columns([3, 1])
        with col_tabela:
            st.dataframe(df_estoque, use_container_width=True, hide_index=True)
        with col_foto:
            modelo_f = st.selectbox("Visualizar Foto:", df_estoque['Modelo'].unique())
            img_url = df_estoque.loc[df_estoque['Modelo'] == modelo_f, 'Imagem'].values[0]
            if pd.notna(img_url) and str(img_url).startswith('http'):
                st.image(img_url, caption=modelo_f)
            else:
                st.info("Nenhuma imagem associada.")
    else:
        st.info("Ainda não há modelos cadastrados. Vá na aba 'Cadastro Modelos'.")

# --- ABA 2: NOVA VENDA (COM BAIXA AUTOMÁTICA) ---
with abas[1]:
    st.subheader("📝 Registar Novo Pedido")
    if df_clientes.empty or df_estoque.empty:
        st.warning("Cadastre primeiro os Clientes e os Modelos.")
    else:
        with st.form("venda_form"):
            c1, c2, c3 = st.columns(3)
            cliente_v = c1.selectbox("Selecione o Cliente", df_clientes['Nome'].unique())
            modelo_v = c2.selectbox("Selecione o Modelo", df_estoque['Modelo'].unique())
            tam_v = c3.selectbox("Tamanho", TAMANHOS_PADRAO)
            qtd_v = st.number_input("Quantidade Desejada", min_value=1, step=1)
            
            if st.form_submit_button("Finalizar e Dar Baixa"):
                # Verificar se tem stock
                idx_e = df_estoque.index[df_estoque['Modelo'] == modelo_v][0]
                stock_atual = int(pd.to_numeric(df_estoque.at[idx_e, tam_v], errors='coerce') or 0)
                
                if stock_atual >= qtd_v:
                    # 1. Atualiza Estoque
                    df_estoque.at[idx_e, tam_v] = stock_atual - qtd_v
                    conn.update(spreadsheet=URL_PLANILHA, worksheet="Estoque", data=df_estoque)
                    
                    # 2. Grava Pedido
                    dados_c = df_clientes[df_clientes['Nome'] == cliente_v].iloc[0]
                    novo_p = pd.DataFrame([{
                        "Data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "Cliente": cliente_v,
                        "Telefone": dados_c['Telefone'],
                        "Loja": dados_c['Loja'],
                        "Cidade": dados_c['Cidade'],
                        "Item": f"{modelo_v} ({tam_v})",
                        "Qtd": qtd_v
                    }])
                    df_pedidos = pd.concat([df_pedidos, novo_p], ignore_index=True)
                    conn.update(spreadsheet=URL_PLANILHA, worksheet="Pedidos", data=df_pedidos)
                    
                    st.cache_data.clear()
                    st.success(f"Venda realizada! Restam {stock_atual - qtd_v} un no estoque.")
                    st.rerun()
                else:
                    st.error(f"Estoque insuficiente! Disponível apenas {stock_atual} unidades.")

# --- ABA 3: CLIENTES ---
with abas[2]:
    st.subheader("👥 Cadastro de Clientes")
    with st.form("form_c"):
        nc, lc, tc, cc = st.columns(4)
        nome = nc.text_input("Nome Cliente")
        loja = lc.text_input("Nome da Loja")
        tel = tc.text_input("Telefone")
        cid = cc.text_input("Cidade")
        if st.form_submit_button("Salvar Cliente"):
            if nome:
                novo_c = pd.DataFrame([{"Nome": nome, "Loja": loja, "Telefone": tel, "Cidade": cid}])
                df_clientes = pd.concat([df_clientes, novo_c], ignore_index=True)
                conn.update(spreadsheet=URL_PLANILHA, worksheet="Clientes", data=df_clientes)
                st.cache_data.clear()
                st.success("Cliente salvo!")
                st.rerun()

# --- ABA 4: HISTÓRICO ---
with abas[3]:
    st.subheader("📜 Histórico de Vendas Realizadas")
    st.dataframe(df_pedidos.sort_index(ascending=False), use_container_width=True, hide_index=True)

# --- ABA 5: CADASTRO MODELOS (DETALHADO) ---
with abas[4]:
    st.subheader("✨ Cadastrar Novo Modelo de Sandália")
    with st.form("novo_modelo_completo"):
        col1, col2 = st.columns(2)
        nome_mod = col1.text_input("Nome do Modelo (ex: Nuvem Confort)")
        url_img = col2.text_input("Link da Imagem (URL do Imgur ou Google)")
        
        st.write("---")
        st.write("**Estoque Inicial por Tamanho:**")
        
        # Criação de 5 colunas para os tamanhos ficarem organizados
        c1, c2, c3, c4, c5 = st.columns(5)
        t_vals = {}
        for i, tam in enumerate(TAMANHOS_PADRAO):
            # Distribui os campos de números entre as colunas
            col_alvo = [c1, c2, c3, c4, c5][i % 5]
            t_vals[tam] = col_alvo.number_input(f"Tamanho {tam}", min_value=0, step=1, value=0)
            
        st.write("---")
        if st.form_submit_button("Cadastrar Modelo no Sistema 💾"):
            if nome_mod:
                # Cria a linha com Nome, Imagem e as quantidades
                nova_linha = {"Modelo": nome_mod, "Imagem": url_img}
                nova_linha.update(t_vals)
                
                # Adiciona ao DataFrame e envia para a Planilha
                df_estoque = pd.concat([df_estoque, pd.DataFrame([nova_linha])], ignore_index=True)
                conn.update(spreadsheet=URL_PLANILHA, worksheet="Estoque", data=df_estoque)
                
                st.cache_data.clear()
                st.success(f"Modelo '{nome_mod}' cadastrado com sucesso!")
                st.rerun()
            else:
                st.error("Por favor, dê um nome ao modelo.")
