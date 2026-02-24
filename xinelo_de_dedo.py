import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Sandálias Nuvem", layout="wide", page_icon="👡")

# Configurações de Dados
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- CARREGAMENTO DE DADOS ---
@st.cache_data(ttl=0)
def carregar_dados():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        def ler_aba(nome, colunas):
            try:
                df = conn.read(spreadsheet=URL_PLANILHA, worksheet=nome, ttl=0).dropna(how='all')
                if df is None or df.empty:
                    return pd.DataFrame(columns=colunas)
                # Limpeza de nomes de colunas
                df.columns = df.columns.str.strip()
                # Garantir que todas as colunas necessárias existam
                for col in colunas:
                    if col not in df.columns:
                        df[col] = 0 if col in TAMANHOS_PADRAO else ""
                return df
            except:
                return pd.DataFrame(columns=colunas)

        df_e = ler_aba("Estoque", ["Modelo"] + TAMANHOS_PADRAO)
        df_p = ler_aba("Pedidos", ["Data", "Cliente", "Resumo do Pedido"])
        df_c = ler_aba("Clientes", ["Nome", "Loja", "Telefone", "Cidade"])
        
        return conn, df_e, df_p, df_c
    except Exception as e:
        st.error(f"Erro ao conectar com a Planilha: {e}")
        return None, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

conn, df_estoque, df_pedidos, df_clientes = carregar_dados()

def atualizar_planilha(aba, dataframe):
    # Converte tudo para string para evitar erros de serialização no GSheets
    df_limpo = dataframe.astype(str)
    # Remove colunas fantasmas do Pandas
    df_limpo = df_limpo.loc[:, ~df_limpo.columns.str.contains('^Unnamed')]
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_limpo)
        st.cache_data.clear() # Força a limpeza do cache para leitura imediata
    except Exception as e:
        st.error(f"Erro ao salvar dados: {e}")

# --- INTERFACE PRINCIPAL ---
st.title("🩴 Xinelo de Dedo")

tab1, tab2, tab3, tab4 = st.tabs(["📊 Estoque", "🛒 Nova Venda", "👥 Clientes", "📜 Histórico"])

# --- ABA 1: ESTOQUE ---
with tab1:
    col_cad, col_list = st.columns([1, 2])
    
    with col_cad:
        st.subheader("✨ Novo Modelo")
        with st.form("form_modelo", clear_on_submit=True):
            nome_mod = st.text_input("Nome do Modelo")
            st.write("Quantidades iniciais:")
            inputs_qtd = {}
            for t in TAMANHOS_PADRAO:
                inputs_qtd[t] = st.number_input(f"Tamanho {t}", min_value=0, step=1)
            
            if st.form_submit_button("Cadastrar no Estoque"):
                if nome_mod:
                    novo_item = {"Modelo": nome_mod}
                    novo_item.update(inputs_qtd)
                    df_estoque = pd.concat([df_estoque, pd.DataFrame([novo_item])], ignore_index=True)
                    atualizar_planilha("Estoque", df_estoque)
                    st.success(f"{nome_mod} adicionado!")
                    st.rerun()
                else:
                    st.error("O nome do modelo é obrigatório.")

    with col_list:
        st.subheader("📦 Inventário Atual")
        if df_estoque.empty:
            st.info("O estoque está vazio.")
        else:
            # Filtro de busca
            busca = st.text_input("Filtrar modelo...", "")
            df_filtrado = df_estoque[df_estoque['Modelo'].str.contains(busca, case=False)]
            
            # Exibição em formato amigável
            st.dataframe(df_filtrado, hide_index=True, use_container_width=True)
            
            if st.toggle("🔓 Ativar Modo de Exclusão"):
                mod_apagar = st.selectbox("Selecionar modelo para remover", df_estoque['Modelo'].tolist())
                if st.button("🗑️ Confirmar Exclusão Definitiva"):
                    df_estoque = df_estoque[df_estoque['Modelo'] != mod_apagar]
                    atualizar_planilha("Estoque", df_estoque)
                    st.rerun()

# --- ABA 2: VENDAS ---
with tab2:
    st.subheader("🛒 Realizar Pedido")
    
    if 'carrinho' not in st.session_state:
        st.session_state.carrinho = []

    if df_clientes.empty or df_estoque.empty:
        st.warning("É necessário ter pelo menos um Cliente e um Modelo no Estoque para vender.")
    else:
        c1, c2 = st.columns([1, 1])
        
        with c1:
            v_cliente = st.selectbox("Escolha o Cliente", df_clientes['Nome'].unique())
            v_modelo = st.selectbox("Escolha o Modelo", df_estoque['Modelo'].unique())
            v_tamanho = st.selectbox("Escolha o Tamanho", TAMANHOS_PADRAO)
            
            # Checar estoque disponível
            estoque_atual = int(df_estoque.loc[df_estoque['Modelo'] == v_modelo, v_tamanho].values[0])
            st.caption(f"Disponível no estoque: {estoque_atual} unidades")
            
            v_qtd = st.number_input("Quantidade", min_value=1, max_value=estoque_atual if estoque_atual > 0 else 1)
            
            if st.button("➕ Adicionar ao Carrinho"):
                if estoque_atual >= v_qtd:
                    st.session_state.carrinho.append({
                        "Modelo": v_modelo,
                        "Tamanho": v_tamanho,
                        "Qtd": v_qtd
                    })
                    st.toast("Item adicionado!")
                else:
                    st.error("Estoque insuficiente!")

        with c2:
            st.write("📋 Resumo do Carrinho")
            if st.session_state.carrinho:
                df_car = pd.DataFrame(st.session_state.carrinho)
                st.table(df_car)
                
                if st.button("🗑️ Limpar Carrinho"):
                    st.session_state.carrinho = []
                    st.rerun()
                
                if st.button("✅ FINALIZAR VENDA E BAIXAR ESTOQUE"):
                    resumo_texto = []
                    for item in st.session_state.carrinho:
                        # Baixa no estoque
                        idx = df_estoque.index[df_estoque['Modelo'] == item['Modelo']][0]
                        valor_atual = int(df_estoque.at[idx, item['Tamanho']])
                        df_estoque.at[idx, item['Tamanho']] = valor_atual - item['Qtd']
                        resumo_texto.append(f"{item['Modelo']} (T:{item['Tamanho']} Qtd:{item['Qtd']})")
                    
                    # Registrar pedido
                    novo_pedido = {
                        "Data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "Cliente": v_cliente,
                        "Resumo do Pedido": " | ".join(resumo_texto)
                    }
                    df_pedidos = pd.concat([df_pedidos, pd.DataFrame([novo_pedido])], ignore_index=True)
                    
                    # Salvar tudo
                    atualizar_planilha("Estoque", df_estoque)
                    atualizar_planilha("Pedidos", df_pedidos)
                    st.session_state.carrinho = []
                    st.success("Venda realizada com sucesso!")
                    st.balloons()
                    st.rerun()

# --- ABA 3: CLIENTES ---
with tab3:
    with st.expander("👤 Cadastrar Novo Cliente"):
        with st.form("form_cliente", clear_on_submit=True):
            c_nome = st.text_input("Nome do Cliente / Razão Social")
            c_loja = st.text_input("Nome da Loja (opcional)")
            c_tel = st.text_input("WhatsApp / Telefone")
            c_cid = st.text_input("Cidade/UF")
            
            if st.form_submit_button("Salvar Cliente"):
                if c_nome:
                    novo_cli = {"Nome": c_nome, "Loja": c_loja, "Telefone": c_tel, "Cidade": c_cid}
                    df_clientes = pd.concat([df_clientes, pd.DataFrame([novo_cli])], ignore_index=True)
                    atualizar_planilha("Clientes", df_clientes)
                    st.success("Cliente cadastrado!")
                    st.rerun()

    st.subheader("👥 Clientes Cadastrados")
    st.dataframe(df_clientes, use_container_width=True, hide_index=True)

# --- ABA 4: HISTÓRICO ---
with tab4:
    st.subheader("📜 Histórico de Vendas")
    if df_pedidos.empty:
        st.info("Nenhuma venda registrada.")
    else:
        # Ordem do mais recente para o mais antigo
        df_hist = df_pedidos.iloc[::-1]
        st.dataframe(df_hist, use_container_width=True, hide_index=True)
        
        if st.button("📥 Baixar Histórico (CSV)"):
            csv = df_hist.to_csv(index=False).encode('utf-8')
            st.download_button("Clique para baixar", csv, "historico_vendas.csv", "text/csv")
