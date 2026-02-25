import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import time

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestão Master v8.6", layout="wide", page_icon="🩴")

# --- 2. CONSTANTES ---
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- 3. FUNÇÕES TÉCNICAS INTEGRAIS (NÃO SIMPLIFICADAS) ---

def get_data_hora():
    """Gera timestamp para registro de logs e pedidos"""
    return (datetime.now() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")

def converter_para_numero(valor):
    """Converte qualquer entrada do Google Sheets para float com segurança"""
    try:
        if pd.isna(valor) or str(valor).strip() == "" or str(valor).lower() == "nan":
            return 0.0
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
        
        # BARREIRA DE SINCRONIZAÇÃO ANTI-RESET
        with st.spinner(f"Gravando dados em {aba}..."):
            time.sleep(2.5) 
        return True
    except Exception as e:
        st.error(f"Erro crítico de conexão: {e}")
        return False

# --- 4. CONEXÃO E CARREGAMENTO BLINDADO ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=10)
def carregar_banco_completo():
    """Lê todas as abas, trata erros de tipo e aplica ordem alfabética"""
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
            if df is not None:
                df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
                df.columns = [str(c).strip() for c in df.columns]
                for c in colunas:
                    if c not in df.columns: df[c] = ""
                
                # ORDENAÇÃO ALFABÉTICA (Protegida)
                if aba == "Estoque" and not df.empty:
                    df["Modelo"] = df["Modelo"].astype(str)
                    df = df.sort_values(by="Modelo", key=lambda x: x.str.lower())
                if aba == "Clientes" and not df.empty:
                    df["Nome"] = df["Nome"].astype(str)
                    df = df.sort_values(by="Nome", key=lambda x: x.str.lower())
                
                resultado[aba] = df
            else:
                resultado[aba] = pd.DataFrame(columns=colunas)
        except Exception:
            resultado[aba] = pd.DataFrame(columns=colunas)
    return resultado

# Inicialização
db = carregar_banco_completo()
df_est, df_ped, df_cli, df_ins, df_lem = db["Estoque"], db["Pedidos"], db["Clientes"], db["Insumos"], db["Lembretes"]

# --- 5. BARRA LATERAL ---
with st.sidebar:
    st.title("⚙️ Gestão Master v8.6")
    if st.button("🔄 Sincronizar Agora", key="btn_sync_v86", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.divider()
    
    st.subheader("📅 Lembretes Ativos")
    if not df_lem.empty:
        lem_validos = df_lem[df_lem['Nome'].astype(str).str.strip() != ""]
        for i, r in lem_validos.iterrows():
            st.warning(f"**{r['Nome']}**\n📅 {r['Vencimento']}\n💰 R$ {r['Valor']}")
    
    st.divider()
    
    with st.expander("🚨 Avisos de Estoque"):
        alertas = []
        for _, row in df_est.iterrows():
            for t in TAMANHOS_PADRAO:
                qtd = converter_para_numero(row[t])
                if qtd < 5: # Detecta de 0 até 4 unidades
                    alertas.append(f"{row['Modelo']} ({t}): {int(qtd)} unid.")
        if alertas:
            for a in alertas: st.error(a)
        else: st.success("Estoque abastecido.")

    with st.expander("⚠️ Pendências de Clientes"):
        if not df_ped.empty:
            pendentes = df_ped[df_ped['Status Pagto'].astype(str).str.lower().isin(['pendente', 'metade'])]
            for _, r in pendentes.iterrows():
                st.error(f"**{r['Cliente']}**\nValor: R$ {r['Valor Total']}")

# --- 6. INTERFACE PRINCIPAL ---
tabs = st.tabs(["📊 Estoque", "🛒 Vendas", "👥 Clientes", "🧾 Histórico", "📅 Lembretes"])

with tabs[0]: # ABA ESTOQUE
    st.subheader("Inventário Consolidado (A-Z)")
    search = st.text_input("Filtrar modelo...", key="search_est_86").lower()
    df_f = df_est[df_est['Modelo'].astype(str).str.lower().str.contains(search)] if search else df_est
    st.dataframe(df_f, hide_index=True, use_container_width=True)
    
    with st.expander("✨ Cadastrar Novo Modelo"):
        with st.form("form_novo_v86"):
            novo_n = st.text_input("Nome do Modelo")
            if st.form_submit_button("Confirmar Cadastro"):
                if novo_n and novo_n not in df_est['Modelo'].values:
                    nova_l = {"Modelo": novo_n}
                    nova_l.update({t: 0 for t in TAMANHOS_PADRAO})
                    if salvar_dados_no_google("Estoque", pd.concat([df_est, pd.DataFrame([nova_l])], ignore_index=True)):
                        st.success("Modelo Adicionado!"); st.rerun()

with tabs[1]: # ABA VENDAS
    st.subheader("Registrar Venda e Baixar Estoque")
    c_v1, c_v2 = st.columns(2)
    with c_v1:
        cli_lista = sorted(df_cli['Nome'].astype(str).unique(), key=str.lower) if not df_cli.empty else []
        mod_lista = sorted(df_est['Modelo'].astype(str).unique(), key=str.lower) if not df_est.empty else []
        v_cli = st.selectbox("Cliente", cli_lista + ["Consumidor Avulso"], key="v_sel_cli_86")
        v_mod = st.selectbox("Modelo", mod_lista, key="v_sel_mod_86")
        v_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="v_sel_tam_86")
        v_pre = st.number_input("Preço Unitário (R$)", min_value=0.0, key="v_num_pre_86")
        v_qtd = st.number_input("Qtd", min_value=1, key="v_num_qtd_86")
        v_st = st.selectbox("Status", ["Pago", "Pendente", "Metade"], key="v_sel_st_86")
        if st.button("Adicionar ao Carrinho", key="v_btn_add_86"):
            if 'cart_v86' not in st.session_state: st.session_state.cart_v86 = []
            st.session_state.cart_v86.append({"Mod": v_mod, "Tam": v_tam, "Qtd": v_qtd, "Pre": v_pre})
            st.rerun()
    with c_v2:
        if 'cart_v86' in st.session_state and st.session_state.cart_v86:
            total_venda, resumo_venda = 0.0, []
            for it in st.session_state.cart_v86:
                st.write(f"• {it['Mod']} ({it['Tam']}) x{it['Qtd']}")
                total_venda += (it['Pre'] * it['Qtd'])
                resumo_venda.append(f"{it['Mod']}({it['Tam']}x{it['Qtd']})")
            if st.button("Finalizar e Atualizar Estoque", type="primary", key="v_btn_fin_86"):
                df_est_atu = df_est.copy()
                for it in st.session_state.cart_v86:
                    idx = df_est_atu.index[df_est_atu['Modelo'].astype(str) == str(it['Mod'])][0]
                    val_atual = converter_para_numero(df_est_atu.at[idx, it['Tam']])
                    df_est_atu.at[idx, it['Tam']] = int(val_atual - it['Qtd'])
                if salvar_dados_no_google("Estoque", df_est_atu):
                    log_v = pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cli, "Resumo": " | ".join(resumo_venda), "Valor Total": total_venda, "Status Pagto": v_st}])
                    salvar_dados_no_google("Pedidos", pd.concat([df_ped, log_v], ignore_index=True))
                    st.session_state.cart_v86 = []
                    st.success("Venda Concluída!"); st.rerun()

with tabs[3]: # ABA HISTÓRICO
    st.subheader("Histórico de Movimentações")
    if not df_ped.empty:
        df_ped_show = df_ped[df_ped['Cliente'].astype(str).str.strip() != ""]
        for idx, r in df_ped_show.iloc[::-1].iterrows():
            with st.container(border=True):
                c_h1, c_h2 = st.columns([0.8, 0.2])
                c_h1.write(f"📅 **{r['Data']}** | 👤 {r['Cliente']} | 💰 **R$ {converter_para_numero(r['Valor Total']):.2f}**")
                c_h1.caption(f"Conteúdo: {r['Resumo']} | Status: {r['Status Pagto']}")
                if c_h2.button("Excluir", key=f"del_h_{idx}"):
                    if salvar_dados_no_google("Pedidos", df_ped.drop(idx)): st.rerun()

with tabs[4]: # ABA LEMBRETES
    st.subheader("Gerenciar Lembretes")
    with st.form("f_lem_86", clear_on_submit=True):
        l_nome = st.text_input("Título")
        l_venc = st.text_input("Vencimento (DD/MM)")
        l_valor = st.number_input("Valor R$", min_value=0.0)
        if st.form_submit_button("Agendar"):
            nova_l = pd.DataFrame([{"Data": get_data_hora(), "Nome": l_nome, "Vencimento": l_venc, "Valor": l_valor}])
            if salvar_dados_no_google("Lembretes", pd.concat([df_lem, nova_l], ignore_index=True)):
                st.rerun()
    st.dataframe(df_lem, use_container_width=True, hide_index=True)

with tabs[2]: # ABA CLIENTES
    st.subheader("Cadastro de Clientes")
    with st.form("f_cli_86", clear_on_submit=True):
        c_n = st.text_input("Nome/Loja")
        c_c = st.text_input("Cidade")
        c_t = st.text_input("Telefone")
        if st.form_submit_button("Salvar Cliente"):
            nova_c = pd.DataFrame([{"Nome": c_n, "Cidade": c_c, "Telefone": c_t}])
            if salvar_dados_no_google("Clientes", pd.concat([df_cli, nova_c], ignore_index=True)):
                st.success("Cliente salvo!"); st.rerun()
    st.dataframe(df_cli, use_container_width=True, hide_index=True)
