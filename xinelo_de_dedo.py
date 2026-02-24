import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Xinelo de Dedo", layout="wide", page_icon="🩴")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- FUNÇÃO DE DATA/HORA (FUSO -3) ---
def get_data_hora():
    return (datetime.now() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")

# --- CARREGAMENTO DE DADOS ---
@st.cache_data(ttl=0)
def carregar_dados():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        def ler_aba(nome, colunas):
            try:
                df = conn.read(spreadsheet=URL_PLANILHA, worksheet=nome, ttl=0).dropna(how='all')
                if df is None or df.empty: return pd.DataFrame(columns=colunas)
                df.columns = df.columns.str.strip()
                for col in colunas:
                    if col not in df.columns:
                        df[col] = 0 if col in TAMANHOS_PADRAO else ""
                return df
            except: return pd.DataFrame(columns=colunas)
        
        df_e = ler_aba("Estoque", ["Modelo"] + TAMANHOS_PADRAO)
        df_p = ler_aba("Pedidos", ["Data", "Cliente", "Resumo do Pedido"])
        df_c = ler_aba("Clientes", ["Nome", "Loja", "Telefone", "Cidade"])
        df_a = ler_aba("Aquisicoes", ["Data", "Resumo da Carga"]) # Nova aba de histórico
        return conn, df_e, df_p, df_c, df_a
    except Exception as e:
        st.error(f"Erro ao conectar: {e}")
        return None, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

conn, df_estoque, df_pedidos, df_clientes, df_aquisicoes = carregar_dados()

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚠️ Alertas de Estoque")
    if df_estoque.empty:
        st.info("Nenhum item cadastrado.")
    else:
        avisos_criticos, avisos_atencao = [], []
        for _, row in df_estoque.iterrows():
            modelo = row['Modelo']
            for tam in TAMANHOS_PADRAO:
                try:
                    qtd = int(row[tam])
                    if qtd < 3: avisos_criticos.append(f"🔴 **{modelo}** ({tam}) - Qtd: {qtd}")
                    elif qtd < 5: avisos_atencao.append(f"🟡 **{modelo}** ({tam}) - Qtd: {qtd}")
                except: continue
        if not avisos_criticos and not avisos_atencao: st.success("✅ Estoque em dia!")
        if avisos_criticos:
            st.markdown("### 🚨 Crítico (< 3)")
            for a in avisos_criticos: st.markdown(a)
        if avisos_atencao:
            st.markdown("### ⚠️ Atenção (< 5)")
            for a in avisos_atencao: st.markdown(a)

def atualizar_planilha(aba, dataframe):
    df_limpo = dataframe.astype(str)
    df_limpo = df_limpo.loc[:, ~df_limpo.columns.str.contains('^Unnamed')]
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_limpo)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- INTERFACE PRINCIPAL ---
st.title("🩴 Xinelo de Dedo")

tab1, tab_cad, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Estoque & Aquisição", "✨ Cadastrar Modelo", "🛒 Nova Venda", "👥 Clientes", "📜 Histórico Vendas", "📦 Histórico Aquisições"
])

# --- ABA 1: ESTOQUE E AQUISIÇÃO ---
with tab1:
    if 'carrinho_entrada' not in st.session_state: st.session_state.carrinho_entrada = []
    col_aq, col_list = st.columns([1.2, 2])
    
    with col_aq:
        st.subheader("📦 Entrada de Mercadoria")
        if not df_estoque.empty:
            c_aq1, c_aq2 = st.columns(2)
            mod_aq = c_aq1.selectbox("Modelo", df_estoque['Modelo'].unique(), key="aq_mod")
            tam_aq = c_aq2.selectbox("Tamanho", TAMANHOS_PADRAO, key="aq_tam")
            qtd_aq = st.number_input("Quantidade", min_value=1, step=1, key="aq_qtd")
            
            if st.button("➕ Adicionar à Carga"):
                st.session_state.carrinho_entrada.append({"Modelo": mod_aq, "Tamanho": tam_aq, "Qtd": qtd_aq})
                st.toast(f"{mod_aq} adicionado!")

            if st.session_state.carrinho_entrada:
                st.write("---")
                st.table(pd.DataFrame(st.session_state.carrinho_entrada))
                
                col_btn1, col_btn2 = st.columns(2)
                if col_btn1.button("🗑️ Limpar"):
                    st.session_state.carrinho_entrada = []; st.rerun()
                
                if col_btn2.button("✅ Confirmar Carga", type="primary"):
                    resumo_entrada = []
                    for item in st.session_state.carrinho_entrada:
                        idx = df_estoque.index[df_estoque['Modelo'] == item['Modelo']][0]
                        df_estoque.at[idx, item['Tamanho']] = int(df_estoque.at[idx, item['Tamanho']]) + item['Qtd']
                        resumo_entrada.append(f"{item['Modelo']}({item['Tamanho']}x{item['Qtd']})")
                    
                    # Registrar Histórico de Aquisição
                    nova_aq = pd.DataFrame([{"Data": get_data_hora(), "Resumo da Carga": " | ".join(resumo_entrada)}])
                    df_aquisicoes = pd.concat([df_aquisicoes, nova_aq], ignore_index=True)
                    
                    atualizar_planilha("Estoque", df_estoque)
                    atualizar_planilha("Aquisicoes", df_aquisicoes)
                    st.session_state.carrinho_entrada = []
                    st.success("Estoque e Histórico atualizados!")
                    st.rerun()
        else: st.info("Cadastre modelos primeiro.")

    with col_list:
        st.subheader("📋 Inventário Atual")
        st.dataframe(df_estoque, hide_index=True, use_container_width=True)

# --- ABA 2: CADASTRAR MODELO ---
with tab_cad:
    st.subheader("✨ Cadastro de Novos Produtos")
    with st.form("form_novo_modelo", clear_on_submit=True):
        nome_mod = st.text_input("Nome/Cor do Novo Modelo")
        cols_t = st.columns(5)
        inputs_n = {t: cols_t[i % 5].number_input(f"T {t}", min_value=0, step=1, key=f"n_{t}") for i, t in enumerate(TAMANHOS_PADRAO)}
        if st.form_submit_button("Finalizar Cadastro"):
            if nome_mod:
                if nome_mod in df_estoque['Modelo'].values: st.error("Modelo já existe!")
                else:
                    ni = {"Modelo": nome_mod}; ni.update(inputs_n)
                    df_estoque = pd.concat([df_estoque, pd.DataFrame([ni])], ignore_index=True)
                    atualizar_planilha("Estoque", df_estoque); st.rerun()

# --- ABA 3: VENDAS ---
with tab2:
    if 'carrinho' not in st.session_state: st.session_state.carrinho = []
    if df_clientes.empty or df_estoque.empty: st.warning("Cadastre Clientes e Modelos primeiro.")
    else:
        c1, c2 = st.columns([1, 1])
        with c1:
            v_cli = st.selectbox("Cliente", df_clientes['Nome'].unique())
            v_mod = st.selectbox("Modelo", df_estoque['Modelo'].unique())
            v_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="v_tam")
            estoque_v = int(df_estoque.loc[df_estoque['Modelo'] == v_mod, v_tam].values[0])
            st.caption(f"Estoque: {estoque_v}")
            v_qtd = st.number_input("Qtd", min_value=1, max_value=max(1, estoque_v))
            if st.button("➕ Adicionar Carrinho"):
                if estoque_v >= v_qtd: st.session_state.carrinho.append({"Modelo": v_mod, "Tamanho": v_tam, "Qtd": v_qtd})
                else: st.error("Sem estoque!")
        with c2:
            if st.session_state.carrinho:
                st.table(pd.DataFrame(st.session_state.carrinho))
                if st.button("🚀 FINALIZAR VENDA"):
                    res = []
                    for it in st.session_state.carrinho:
                        idx = df_estoque.index[df_estoque['Modelo'] == it['Modelo']][0]
                        df_estoque.at[idx, it['Tamanho']] = int(df_estoque.at[idx, it['Tamanho']]) - it['Qtd']
                        res.append(f"{it['Modelo']}({it['Tamanho']}x{it['Qtd']})")
                    
                    np = pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cli, "Resumo do Pedido": " | ".join(res)}])
                    df_pedidos = pd.concat([df_pedidos, np], ignore_index=True)
                    atualizar_planilha("Estoque", df_estoque); atualizar_planilha("Pedidos", df_pedidos)
                    st.session_state.carrinho = []; st.rerun()

# --- ABA 4: CLIENTES ---
with tab3:
    with st.expander("👤 Novo Cliente"):
        with st.form("f_cli", clear_on_submit=True):
            cn, cl, ct, cc = st.text_input("Nome"), st.text_input("Loja"), st.text_input("Tel"), st.text_input("Cidade")
            if st.form_submit_button("Salvar"):
                nc = pd.DataFrame([{"Nome": cn, "Loja": cl, "Telefone": ct, "Cidade": cc}])
                df_clientes = pd.concat([df_clientes, nc], ignore_index=True)
                atualizar_planilha("Clientes", df_clientes); st.rerun()
    st.dataframe(df_clientes, use_container_width=True, hide_index=True)

# --- ABA 5: HISTÓRICO VENDAS ---
with tab4:
    st.subheader("📜 Vendas")
    st.dataframe(df_pedidos.iloc[::-1], use_container_width=True, hide_index=True)

# --- ABA 6: HISTÓRICO AQUISIÇÕES ---
with tab5:
    st.subheader("📦 Entradas de Mercadoria")
    st.dataframe(df_aquisicoes.iloc[::-1], use_container_width=True, hide_index=True)
