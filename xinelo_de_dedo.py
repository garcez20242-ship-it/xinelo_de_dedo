import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import time

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestão Master v8.3", layout="wide", page_icon="🩴")

# --- 2. CONSTANTES ---
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- 3. FUNÇÕES DE SUPORTE ---
def get_data_hora():
    return (datetime.now() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")

def converter_para_numero(valor):
    try:
        if pd.isna(valor) or str(valor).strip() == "" or str(valor).lower() == "nan":
            return 0.0
        limpo = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
        return float(limpo)
    except:
        return 0.0

# --- 4. CONEXÃO E CARREGAMENTO SEM FILTROS AGRESSIVOS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def carregar_banco_dados():
    # Nomes das abas exatamente como devem estar no Google Sheets
    config = {
        "Estoque": ["Modelo"] + TAMANHOS_PADRAO,
        "Pedidos": ["Data", "Cliente", "Resumo", "Valor Total", "Status Pagto"],
        "Clientes": ["Nome", "Loja", "Cidade", "Telefone"],
        "Insumos": ["Data", "Descricao", "Valor"],
        "Lembretes": ["Data", "Nome", "Vencimento", "Valor"]
    }
    banco = {}
    
    for aba, colunas in config.items():
        try:
            # ttl=0 garante que ele busque o dado mais recente do Google
            df = conn.read(spreadsheet=URL_PLANILHA, worksheet=aba, ttl="0s")
            
            if df is not None:
                # Remove apenas colunas totalmente vazias (Unnamed)
                df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
                # Garante que as colunas existam
                for c in colunas:
                    if c not in df.columns: df[c] = ""
                
                # Ordenação A-Z para tabelas de apoio
                if aba == "Estoque":
                    df = df.sort_values(by="Modelo", key=lambda x: x.str.lower())
                if aba == "Clientes":
                    df = df.sort_values(by="Nome", key=lambda x: x.str.lower())
                
                banco[aba] = df
            else:
                banco[aba] = pd.DataFrame(columns=colunas)
        except Exception as e:
            st.error(f"Erro ao ler aba {aba}: {e}")
            banco[aba] = pd.DataFrame(columns=colunas)
            
    return banco

def salvar_seguro(aba, df):
    try:
        # Converte para string para evitar erros de serialização
        df_save = df.astype(str).replace(['nan', 'None'], '')
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_save)
        st.cache_data.clear()
        time.sleep(2)
        return True
    except Exception as e:
        st.error(f"Falha ao salvar: {e}")
        return False

# Inicializa o banco
db = carregar_banco_dados()
df_est = db["Estoque"]
df_ped = db["Pedidos"]
df_cli = db["Clientes"]
df_ins = db["Insumos"]
df_lem = db["Lembretes"]

# --- 5. BARRA LATERAL (FIXADA) ---
with st.sidebar:
    st.header("⚙️ Painel de Controle")
    if st.button("🔄 Forçar Atualização", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.divider()
    
    # LEMBRETES (Recuperados)
    st.subheader("📅 Lembretes/Contas")
    if not df_lem.empty:
        # Filtra apenas linhas que possuem nome preenchido
        lem_ativos = df_lem[df_lem['Nome'] != ""]
        if not lem_ativos.empty:
            for i, r in lem_ativos.iterrows():
                st.info(f"**{r['Nome']}**\nVencto: {r['Vencimento']}\nValor: R$ {r['Valor']}")
        else:
            st.write("Nenhum lembrete com nome.")
    else:
        st.write("Lista de lembretes vazia.")

    st.divider()
    
    with st.expander("🚨 Alertas de Estoque"):
        avisos = []
        for _, row in df_est.iterrows():
            for t in TAMANHOS_PADRAO:
                q = converter_para_numero(row[t])
                if 0 < q < 5: avisos.append(f"{row['Modelo']} ({t}): {int(q)} unid.")
        if avisos:
            for a in avisos: st.warning(a)
        else: st.write("Estoque abastecido.")

# --- 6. INTERFACE PRINCIPAL ---
tabs = st.tabs(["📊 Estoque", "✨ Cadastro", "🛒 Vendas", "👥 Clientes", "🧾 Histórico (Pedidos)"])

with tabs[0]: # ESTOQUE
    st.subheader("📦 Inventário Atual (Ordem A-Z)")
    st.dataframe(df_est, hide_index=True, use_container_width=True)

with tabs[1]: # CADASTRO
    st.subheader("✨ Novo Modelo")
    with st.form("f_novo"):
        n_m = st.text_input("Nome do Chinelo")
        if st.form_submit_button("Salvar"):
            if n_m and n_m not in df_est['Modelo'].values:
                nova_l = {"Modelo": n_m}
                nova_l.update({t: 0 for t in TAMANHOS_PADRAO})
                if salvar_seguro("Estoque", pd.concat([df_est, pd.DataFrame([nova_l])], ignore_index=True)):
                    st.success("Salvo!"); st.rerun()

with tabs[2]: # VENDAS
    st.subheader("🛒 Registrar Venda")
    col1, col2 = st.columns(2)
    with col1:
        c_l = sorted(df_cli['Nome'].unique()) if not df_cli.empty else []
        m_l = sorted(df_est['Modelo'].unique()) if not df_est.empty else []
        v_cli = st.selectbox("Cliente", c_l + ["Avulso"])
        v_mod = st.selectbox("Modelo", m_l)
        v_tam = st.selectbox("Tam", TAMANHOS_PADRAO)
        v_pre = st.number_input("Preço Unitário", min_value=0.0)
        v_qtd = st.number_input("Quantidade", min_value=1)
        v_st = st.selectbox("Status", ["Pago", "Pendente", "Metade"])
        if st.button("Adicionar"):
            if 'cart' not in st.session_state: st.session_state.cart = []
            st.session_state.cart.append({"Mod": v_mod, "Tam": v_tam, "Qtd": v_qtd, "Pre": v_pre})
            st.rerun()
    with col2:
        if 'cart' in st.session_state and st.session_state.cart:
            total, res = 0, []
            for i in st.session_state.cart:
                st.write(f"• {i['Mod']} ({i['Tam']}) x{i['Qtd']}")
                total += (i['Pre'] * i['Qtd'])
                res.append(f"{i['Mod']}({i['Tam']}x{i['Qtd']})")
            if st.button("Finalizar Venda", type="primary"):
                df_e_atu = df_est.copy()
                idx = df_e_atu.index[df_e_atu['Modelo'] == st.session_state.cart[0]['Mod']][0]
                # Baixa estoque
                for i in st.session_state.cart:
                    atu = converter_para_numero(df_e_atu.at[idx, i['Tam']])
                    df_e_atu.at[idx, i['Tam']] = int(atu - i['Qtd'])
                if salvar_seguro("Estoque", df_e_atu):
                    log = pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cli, "Resumo": " | ".join(res), "Valor Total": total, "Status Pagto": v_st}])
                    salvar_seguro("Pedidos", pd.concat([df_ped, log], ignore_index=True))
                    st.session_state.cart = []
                    st.success("Venda Concluída!"); st.rerun()

with tabs[4]: # HISTÓRICO (PEDIDOS)
    st.subheader("🧾 Histórico de Vendas e Entradas")
    if not df_ped.empty:
        # Limpeza para garantir que linhas vazias do Google Sheets não apareçam como cards brancos
        df_ped_limpo = df_ped.dropna(subset=['Data', 'Cliente', 'Resumo'], how='all')
        
        if not df_ped_limpo.empty:
            for idx, r in df_ped_limpo.iloc[::-1].iterrows():
                # Só mostra se houver conteúdo básico
                if str(r['Cliente']).strip() != "":
                    with st.container(border=True):
                        c1, c2 = st.columns([0.8, 0.2])
                        c1.write(f"📅 **{r['Data']}** | 👤 {r['Cliente']}")
                        c1.write(f"📝 {r['Resumo']}")
                        c1.write(f"💰 **R$ {converter_para_numero(r['Valor Total']):.2f}** | Status: {r['Status Pagto']}")
                        if c2.button("Excluir", key=f"del_{idx}"):
                            if salvar_seguro("Pedidos", df_ped.drop(idx)):
                                st.rerun()
        else:
            st.info("O histórico está vazio na planilha.")
    else:
        st.info("Nenhum dado encontrado na aba 'Pedidos'.")

# ABA LEMBRETES (Para você gerenciar os que sumiram)
with tabs[3]: # Reaproveitando aba de clientes para mostrar a tabela de lembretes
    st.divider()
    st.subheader("📅 Gerenciar Todos os Lembretes")
    with st.form("f_lem"):
        ln = st.text_input("Nome da Conta/Lembrete")
        lv = st.text_input("Data Vencimento")
        lq = st.number_input("Valor R$")
        if st.form_submit_button("Adicionar Lembrete"):
            novo_l = pd.DataFrame([{"Data": get_data_hora(), "Nome": ln, "Vencimento": lv, "Valor": lq}])
            if salvar_seguro("Lembretes", pd.concat([df_lem, novo_l], ignore_index=True)):
                st.rerun()
    st.dataframe(df_lem, use_container_width=True)
