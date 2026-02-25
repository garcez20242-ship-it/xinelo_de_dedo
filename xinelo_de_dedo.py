import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import time

# --- 1. CONFIGURAÇÃO DE AMBIENTE ---
st.set_page_config(page_title="Gestão Master v8.2", layout="wide", page_icon="🩴")

# CSS para melhorar a visualização dos alertas na sidebar
st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #f0f2f6; }
    .stAlert { margin-bottom: 8px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONSTANTES E VARIÁVEIS DE ESTADO ---
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- 3. FUNÇÕES TÉCNICAS (SEM RESUMOS) ---

def get_data_hora():
    """Gera timestamp para registro de logs e pedidos"""
    return (datetime.now() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")

def converter_para_numero(valor):
    """Converte qualquer entrada do Google Sheets para float/int com segurança"""
    try:
        if pd.isna(valor) or str(valor).strip() == "" or str(valor).lower() == "nan":
            return 0.0
        # Remove símbolos de moeda e corrige separadores
        limpo = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
        return float(limpo)
    except:
        return 0.0

def salvar_dados_no_google(aba, dataframe):
    """Função mestre de salvamento com barreira de sincronização"""
    try:
        # Limpeza pré-salvamento: garante que dados vazios não virem 'nan' no Sheets
        df_para_salvar = dataframe.astype(str).replace(['nan', 'None', '<NA>'], '')
        
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_para_salvar)
        
        # Limpa o cache global para forçar a leitura do dado novo
        st.cache_data.clear()
        
        # O SEGREDO ANTI-RESET: Aguarda a API do Google confirmar a escrita
        with st.spinner(f"Sincronizando aba {aba}..."):
            time.sleep(2.5) 
        return True
    except Exception as e:
        st.error(f"Erro crítico de conexão: {e}")
        return False

# --- 4. CONEXÃO E CARREGAMENTO ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=10)
def carregar_banco_completo():
    """Lê todas as abas e aplica a ordem alfabética no carregamento"""
    config_abas = {
        "Estoque": ["Modelo"] + TAMANHOS_PADRAO,
        "Pedidos": ["Data", "Cliente", "Resumo", "Valor Total", "Status Pagto"],
        "Clientes": ["Nome", "Loja", "Cidade", "Telefone"],
        "Insumos": ["Data", "Descricao", "Valor"],
        "Lembretes": ["Data", "Nome", "Vencimento", "Valor"]
    }
    resultado = {}
    
    for aba, colunas in config_abas.items():
        try:
            df = conn.read(spreadsheet=URL_PLANILHA, worksheet=aba, ttl="0s")
            if df is not None and not df.empty:
                # Remove colunas e linhas totalmente vazias
                df = df.dropna(how='all').loc[:, ~df.columns.str.contains('^Unnamed')]
                df.columns = [str(c).strip() for c in df.columns]
                
                # Garante que as colunas obrigatórias existam
                for c in colunas:
                    if c not in df.columns: df[c] = ""
                
                # ORDENAÇÃO ALFABÉTICA (A-Z)
                if aba == "Estoque":
                    df = df.sort_values(by="Modelo", key=lambda x: x.str.lower())
                if aba == "Clientes":
                    df = df.sort_values(by="Nome", key=lambda x: x.str.lower())
                
                resultado[aba] = df
            else:
                resultado[aba] = pd.DataFrame(columns=colunas)
        except:
            resultado[aba] = pd.DataFrame(columns=colunas)
            
    return resultado

# Executa o carregamento
db = carregar_banco_completo()
df_est, df_ped, df_cli, df_ins, df_lem = db["Estoque"], db["Pedidos"], db["Clientes"], db["Insumos"], db["Lembretes"]

# --- 5. BARRA LATERAL (FULL) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3050/3050222.png", width=80)
    st.title("Controle Central")
    
    if st.button("🔄 Sincronizar Agora", key="btn_sync_global", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.divider()
    
    # Lembretes de Pagamento
    st.subheader("📌 Lembretes Ativos")
    if not df_lem.empty:
        for i, r in df_lem.iterrows():
            st.warning(f"**{r['Nome']}**\n📅 {r['Vencimento']}\n💰 R$ {r['Valor']}")
    
    st.divider()
    
    # Alertas de Estoque Baixo (Minimizado)
    with st.expander("🚨 Avisos de Estoque"):
        alertas = []
        for _, row in df_est.iterrows():
            for t in TAMANHOS_PADRAO:
                qtd = converter_para_numero(row[t])
                if 0 < qtd < 5:
                    alertas.append(f"{row['Modelo']} ({t}): {int(qtd)} par(es)")
        
        if alertas:
            for a in alertas: st.write(f"• {a}")
        else:
            st.write("Todos os itens abastecidos.")

    # Clientes com Pendências (Minimizado)
    with st.expander("⚠️ Pendências Financeiras"):
        if not df_ped.empty:
            pendentes = df_ped[df_ped['Status Pagto'].str.lower().isin(['pendente', 'metade'])]
            if not pendentes.empty:
                for _, r in pendentes.iterrows():
                    st.error(f"**{r['Cliente']}**\nValor: R$ {r['Valor Total']}")
            else:
                st.write("Nenhuma pendência encontrada.")

# --- 6. INTERFACE PRINCIPAL ---
tabs = st.tabs(["📊 Estoque", "✨ Cadastrar Modelo", "🛒 Nova Venda", "👥 Clientes", "🧾 Histórico"])

with tabs[0]: # ABA ESTOQUE
    st.subheader("Inventário Consolidado (A-Z)")
    search = st.text_input("Filtrar modelo...", key="search_est").lower()
    
    df_f = df_est[df_est['Modelo'].str.lower().str.contains(search)] if search else df_est
    st.dataframe(df_f, hide_index=True, use_container_width=True)
    
    with st.expander("📦 Registrar Entrada de Lote"):
        if 'lote_cache' not in st.session_state: st.session_state.lote_cache = []
        
        c1, c2, c3 = st.columns(3)
        mod_lista = sorted(df_est['Modelo'].unique(), key=str.lower) if not df_est.empty else []
        m_e = c1.selectbox("Modelo", mod_lista, key="sel_m_e")
        t_e = c2.selectbox("Tamanho", TAMANHOS_PADRAO, key="sel_t_e")
        q_e = c3.number_input("Qtd", min_value=1, key="num_q_e")
        
        if st.button("Adicionar ao Lote", key="btn_add_lote"):
            st.session_state.lote_cache.append({"Modelo": m_e, "Tam": t_e, "Qtd": q_e})
            st.rerun()
            
        if st.session_state.lote_cache:
            st.table(st.session_state.lote_cache)
            val_compra = st.number_input("Custo Total da Compra (R$)", min_value=0.0, key="val_compra_lote")
            if st.button("Confirmar Entrada no Estoque", type="primary", key="btn_save_lote"):
                df_novo_est = df_est.copy()
                for item in st.session_state.lote_cache:
                    idx = df_novo_est.index[df_novo_est['Modelo'] == item['Modelo']][0]
                    atual = converter_para_numero(df_novo_est.at[idx, item['Tam']])
                    df_novo_est.at[idx, item['Tam']] = int(atual + item['Qtd'])
                
                if salvar_dados_no_google("Estoque", df_novo_est):
                    # Gera log no extrato
                    log = pd.DataFrame([{"Data": get_data_hora(), "Cliente": "FORNECEDOR", "Resumo": "Entrada de Lote", "Valor Total": val_compra, "Status Pagto": "Pago"}])
                    salvar_dados_no_google("Pedidos", pd.concat([df_ped, log], ignore_index=True))
                    st.session_state.lote_cache = []
                    st.success("Estoque sincronizado com sucesso!")
                    st.rerun()

with tabs[1]: # ABA CADASTRO
    st.subheader("Adicionar Novo Chinelo")
    with st.form("form_novo_chinelo", clear_on_submit=True):
        nome_chinelo = st.text_input("Nome do Modelo")
        if st.form_submit_button("Finalizar Cadastro"):
            if nome_chinelo and nome_chinelo not in df_est['Modelo'].values:
                nova_linha = {"Modelo": nome_chinelo}
                nova_linha.update({t: 0 for t in TAMANHOS_PADRAO})
                if salvar_dados_no_google("Estoque", pd.concat([df_est, pd.DataFrame([nova_linha])], ignore_index=True)):
                    st.success(f"Modelo {nome_chinelo} adicionado!")
                    st.rerun()
            else:
                st.error("Nome inválido ou modelo já existe.")

with tabs[2]: # ABA VENDAS
    st.subheader("Registrar Pedido")
    c_v1, c_v2 = st.columns(2)
    
    with c_v1:
        # Puxa listas ordenadas
        c_lista = sorted(df_cli['Nome'].unique(), key=str.lower) if not df_cli.empty else []
        m_lista = sorted(df_est['Modelo'].unique(), key=str.lower) if not df_est.empty else []
        
        v_cli = st.selectbox("Cliente", c_lista + ["Consumidor Avulso"], key="v_sel_cli")
        v_mod = st.selectbox("Modelo", m_lista, key="v_sel_mod")
        v_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="v_sel_tam")
        v_pre = st.number_input("Preço Unitário (R$)", min_value=0.0, key="v_num_pre")
        v_qtd = st.number_input("Qtd", min_value=1, key="v_num_qtd")
        v_status = st.selectbox("Pagamento", ["Pago", "Pendente", "Metade"], key="v_sel_stat")
        
        if st.button("Adicionar ao Carrinho", key="v_btn_add"):
            if 'cart_v8' not in st.session_state: st.session_state.cart_v8 = []
            st.session_state.cart_v8.append({"Mod": v_mod, "Tam": v_tam, "Qtd": v_qtd, "Pre": v_pre})
            st.rerun()

    with c_v2:
        if 'cart_v8' in st.session_state and st.session_state.cart_v8:
            st.write("🛒 **Carrinho de Venda**")
            total_venda = 0
            resumo_venda = []
            for it in st.session_state.cart_v8:
                st.write(f"• {it['Mod']} ({it['Tam']}) x{it['Qtd']}")
                total_venda += (it['Pre'] * it['Qtd'])
                resumo_venda.append(f"{it['Mod']}({it['Tam']}x{it['Qtd']})")
            
            st.write(f"--- \n**Total: R$ {total_venda:.2f}**")
            
            if st.button("Finalizar Venda", type="primary", key="v_btn_fin"):
                df_e_atu = df_est.copy()
                for it in st.session_state.cart_v8:
                    idx = df_e_atu.index[df_e_atu['Modelo'] == it['Mod']][0]
                    atu = converter_para_numero(df_e_atu.at[idx, it['Tam']])
                    df_e_atu.at[idx, it['Tam']] = int(atu - it['Qtd'])
                
                if salvar_dados_no_google("Estoque", df_e_atu):
                    v_log = pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cli, "Resumo": " | ".join(resumo_venda), "Valor Total": total_venda, "Status Pagto": v_status}])
                    salvar_dados_no_google("Pedidos", pd.concat([df_ped, v_log], ignore_index=True))
                    st.session_state.cart_v8 = []
                    st.success("Venda registrada!")
                    st.rerun()

with tabs[4]: # ABA EXTRATO
    st.subheader("Histórico de Movimentações")
    if not df_ped.empty:
        # Exibe do mais novo para o mais antigo
        for idx, row in df_ped.iloc[::-1].iterrows():
            with st.container(border=True):
                col_ex1, col_ex2 = st.columns([0.8, 0.2])
                col_ex1.write(f"📅 **{row['Data']}** | 👤 {row['Cliente']} | 💰 **R$ {converter_para_numero(row['Valor Total']):.2f}**")
                col_ex1.caption(f"Conteúdo: {row['Resumo']} | Status: {row['Status Pagto']}")
                if col_ex2.button("Excluir", key=f"del_ped_{idx}"):
                    if salvar_dados_no_google("Pedidos", df_ped.drop(idx)):
                        st.rerun()
