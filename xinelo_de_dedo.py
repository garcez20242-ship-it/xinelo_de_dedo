import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão de Sandálias Nuvem", layout="wide", page_icon="👡")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

@st.cache_data(ttl=0)
def carregar_dados():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        estoque = conn.read(spreadsheet=URL_PLANILHA, worksheet="Estoque", ttl=0).dropna(how='all')
    except:
        estoque = pd.DataFrame(columns=["Modelo", "Imagem"] + TAMANHOS_PADRAO)
    try:
        pedidos = conn.read(spreadsheet=URL_PLANILHA, worksheet="Pedidos", ttl=0).dropna(how='all')
    except:
        pedidos = pd.DataFrame(columns=["Data", "Cliente", "Telefone", "Loja", "Cidade", "Item", "Qtd"])
    try:
        clientes = conn.read(spreadsheet=URL_PLANILHA, worksheet="Clientes", ttl=0).dropna(how='all')
    except:
        clientes = pd.DataFrame(columns=["Nome", "Loja", "Telefone", "Cidade"])
    
    for df in [estoque, pedidos, clientes]:
        df.columns = df.columns.str.strip()
    return conn, estoque, pedidos, clientes

conn, df_estoque, df_pedidos, df_clientes = carregar_dados()

# --- FUNÇÃO AUXILIAR PARA SALVAR ---
def atualizar_planilha(aba, dataframe):
    conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=dataframe)
    st.cache_data.clear()
    st.rerun()

# --- SIDEBAR (ALERTAS DE ESTOQUE BAIXO) ---
with st.sidebar:
    st.header("🔔 Alertas de Reposição")
    alertas = []
    for _, row in df_estoque.iterrows():
        for tam in TAMANHOS_PADRAO:
            qtd = pd.to_numeric(row[tam], errors='coerce')
            if not pd.isna(qtd) and qtd < 3:
                alertas.append(f"{row['Modelo']} ({tam}): {int(qtd)} un")
    if alertas:
        for a in alertas: st.warning(a)
    else:
        st.success("Estoque normalizado.")

st.title("👡 Sistema Comercial Completo")
abas = st.tabs(["📊 Estoque e Edição", "🛒 Nova Venda", "👥 Clientes", "📜 Histórico", "✨ Cadastro"])

# --- ABA 1: ESTOQUE E EDIÇÃO ---
with abas[0]:
    st.subheader("Gerenciar Inventário")
    if df_estoque.empty:
        st.info("Nenhum modelo cadastrado.")
    else:
        for index, row in df_estoque.iterrows():
            with st.expander(f"📦 Modelo: {row['Modelo']}"):
                col1, col2, col3, col4 = st.columns([1, 2, 1, 1])
                
                # Exibir imagem se houver
                if pd.notna(row['Imagem']) and str(row['Imagem']).startswith('http'):
                    col1.image(row['Imagem'], width=100)
                
                novo_nome = col2.text_input("Alterar Nome", value=row['Modelo'], key=f"edit_m_{index}")
                nova_img = col2.text_input("Alterar Link Imagem", value=row['Imagem'], key=f"edit_img_{index}")
                
                if col3.button("Salvar Alterações ✅", key=f"sv_m_{index}"):
                    df_estoque.at[index, 'Modelo'] = novo_nome
                    df_estoque.at[index, 'Imagem'] = nova_img
                    atualizar_planilha("Estoque", df_estoque)
                
                if col4.button("Excluir Modelo 🗑️", key=f"del_m_{index}"):
                    df_estoque = df_estoque.drop(index)
                    atualizar_planilha("Estoque", df_estoque)
                
                # Edição rápida de quantidades
                st.write("**Quantidades atuais:**")
                edit_q = st.data_editor(row[TAMANHOS_PADRAO].to_frame().T, key=f"ed_qtd_{index}")
                if st.button("Atualizar Quantidades 🔄", key=f"btn_q_{index}"):
                    for t in TAMANHOS_PADRAO:
                        df_estoque.at[index, t] = edit_q.at[0, t]
                    atualizar_planilha("Estoque", df_estoque)

# --- ABA 2: NOVA VENDA (COM BAIXA AUTOMÁTICA) ---
with abas[1]:
    st.subheader("📝 Registrar Venda")
    if df_clientes.empty or df_estoque.empty:
        st.warning("Cadastre clientes e modelos primeiro.")
    else:
        with st.form("venda_form"):
            c1, c2, c3 = st.columns(3)
            cli_v = c1.selectbox("Cliente", df_clientes['Nome'].unique())
            mod_v = c2.selectbox("Modelo", df_estoque['Modelo'].unique())
            tam_v = c3.selectbox("Tamanho", TAMANHOS_PADRAO)
            qtd_v = st.number_input("Qtd", min_value=1, step=1)
            
            if st.form_submit_button("Finalizar Venda"):
                idx_e = df_estoque.index[df_estoque['Modelo'] == mod_v][0]
                estoque_atual = int(pd.to_numeric(df_estoque.at[idx_e, tam_v], errors='coerce') or 0)
                
                if estoque_atual >= qtd_v:
                    # Baixa no estoque
                    df_estoque.at[idx_e, tam_v] = estoque_atual - qtd_v
                    atualizar_planilha("Estoque", df_estoque)
                    
                    # Registro no histórico
                    dados_c = df_clientes[df_clientes['Nome'] == cli_v].iloc[0]
                    novo_p = pd.DataFrame([{
                        "Data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "Cliente": cli_v, "Telefone": dados_c['Telefone'],
                        "Loja": dados_c['Loja'], "Cidade": dados_c['Cidade'],
                        "Item": f"{mod_v} ({tam_v})", "Qtd": qtd_v
                    }])
                    df_pedidos = pd.concat([df_pedidos, novo_p], ignore_index=True)
                    atualizar_planilha("Pedidos", df_pedidos)
                    st.success("Venda realizada com sucesso!")
                else:
                    st.error(f"Estoque insuficiente! Disponível: {estoque_atual}")

# --- ABA 3: CLIENTES (EDIÇÃO E EXCLUSÃO) ---
with abas[2]:
    st.subheader("Gerenciar Clientes")
    for index, row in df_clientes.iterrows():
        with st.expander(f"👤 {row['Nome']} ({row['Loja']})"):
            c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
            en = c1.text_input("Nome", value=row['Nome'], key=f"en_{index}")
            el = c2.text_input("Loja", value=row['Loja'], key=f"el_{index}")
            
            if c3.button("Atualizar ✅", key=f"upc_{index}"):
                df_clientes.at[index, 'Nome'] = en
                df_clientes.at[index, 'Loja'] = el
                atualizar_planilha("Clientes", df_clientes)
            
            if c4.button("Excluir 🗑️", key=f"dlc_{index}"):
                df_clientes = df_clientes.drop(index)
                atualizar_planilha("Clientes", df_clientes)

# --- ABA 4: HISTÓRICO ---
with abas[3]:
    st.subheader("📜 Histórico")
    st.dataframe(df_pedidos.sort_index(ascending=False), use_container_width=True, hide_index=True)

# --- ABA 5: CADASTRO ---
with abas[4]:
    st.subheader("✨ Novos Registros")
    tipo = st.selectbox("O que deseja cadastrar?", ["Modelo", "Cliente"])
    if tipo == "Modelo":
        with st.form("cad_mod"):
            nm = st.text_input("Nome do Modelo")
            im = st.text_input("URL da Imagem")
            cols = st.columns(5)
            q_dic = {t: cols[i%5].number_input(f"Tam {t}", min_value=0) for i, t in enumerate(TAMANHOS_PADRAO)}
            if st.form_submit_button("Cadastrar Modelo"):
                nl = {"Modelo": nm, "Imagem": im}; nl.update(q_dic)
                df_estoque = pd.concat([df_estoque, pd.DataFrame([nl])], ignore_index=True)
                atualizar_planilha("Estoque", df_estoque)
    else:
        with st.form("cad_cli"):
            cn = st.text_input("Nome"); cl = st.text_input("Loja")
            ct = st.text_input("Telefone"); cc = st.text_input("Cidade")
            if st.form_submit_button("Cadastrar Cliente"):
                nc = pd.DataFrame([{"Nome": cn, "Loja": cl, "Telefone": ct, "Cidade": cc}])
                df_clientes = pd.concat([df_clientes, nc], ignore_index=True)
                atualizar_planilha("Clientes", df_clientes)
