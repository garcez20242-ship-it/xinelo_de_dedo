import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestão Xinelo v6.0", layout="wide", page_icon="🩴")
st.title("🩴 Gestão Xinelo de Dedo v6.0")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- FUNÇÕES ---
def get_data_hora():
    return (datetime.now() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")

def limpar_valor(valor):
    try:
        if pd.isna(valor) or str(valor).strip() == "": return 0.0
        v = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
        return float(v)
    except: return 0.0

def gerar_recibo(r):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(190, 10, "RECIBO DE VENDA", ln=True, align="C")
        pdf.set_font("Arial", "", 12)
        pdf.cell(190, 10, f"Data: {r['Data']} | Cliente: {r['Cliente']}", ln=True)
        pdf.multi_cell(190, 8, f"Resumo: {r['Resumo']}")
        pdf.cell(190, 10, f"Total: R$ {limpar_valor(r['Valor Total']):.2f}", ln=True, align="R")
        return pdf.output(dest='S').encode('latin-1')
    except: return b""

# --- CONEXÃO E LEITURA ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=5)
def carregar_dados():
    def ler(aba, cols):
        try:
            df = conn.read(spreadsheet=URL_PLANILHA, worksheet=aba, ttl="0s")
            if df is not None and not df.empty:
                df = df.dropna(how='all').loc[:, ~df.columns.str.contains('^Unnamed')]
                return df
            return pd.DataFrame(columns=cols)
        except: return pd.DataFrame(columns=cols)
    
    return {
        "est": ler("Estoque", ["Modelo"] + TAMANHOS_PADRAO),
        "ped": ler("Pedidos", ["Data", "Cliente", "Resumo", "Valor Total", "Status Pagto"]),
        "cli": ler("Clientes", ["Nome", "Loja", "Cidade", "Telefone"]),
        "ins": ler("Insumos", ["Data", "Descricao", "Valor"]),
        "lem": ler("Lembretes", ["Data", "Nome", "Valor"]),
        "aqui": ler("Aquisicoes", ["Data", "Resumo", "Valor Total"])
    }

dados = carregar_dados()
df_estoque = dados["est"].sort_values("Modelo") if not dados["est"].empty else dados["est"]
df_pedidos = dados["ped"]
df_clientes = dados["cli"].sort_values("Nome") if not dados["cli"].empty else dados["cli"]
df_insumos = dados["ins"]
df_lembretes = dados["lem"]

def salvar_blindado(aba, df_novo, df_antigo):
    if len(df_antigo) > 1 and len(df_novo) <= 1:
        st.error("🚨 SEGURANÇA: Erro de leitura detectado. Salvamento cancelado para não apagar a planilha.")
        return False
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_novo.astype(str).replace('nan', ''))
        st.cache_data.clear()
        st.success("✅ Atualizado!")
        time.sleep(1)
        st.rerun()
    except Exception as e: st.error(f"Erro: {e}")

# --- BARRA LATERAL (RESTAURADA) ---
with st.sidebar:
    st.header("🔄 Sistema")
    if st.button("Forçar Atualização Geral"):
        st.cache_data.clear()
        st.rerun()
    
    st.divider()
    st.header("💳 Lembrete de Pagamento")
    if not df_pedidos.empty:
        # Filtra vendas pendentes
        pendentes = df_pedidos[df_pedidos['Status Pagto'].str.contains("Pendente", case=False, na=False)]
        if not pendentes.empty:
            total_fiado = pendentes['Valor Total'].apply(limpar_valor).sum()
            st.warning(f"**Total Pendente: R$ {total_fiado:.2f}**")
            # Lista por cliente
            resumo_pend = pendentes.groupby('Cliente')['Valor Total'].apply(lambda x: x.apply(limpar_valor).sum())
            for cliente, valor in resumo_pend.items():
                st.caption(f"👤 {cliente}: R$ {valor:.2f}")
        else:
            st.success("Não há pagamentos pendentes.")

# --- ABAS ---
tabs = st.tabs(["📊 Estoque", "✨ Novo Modelo", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato", "📅 Lembretes"])

# [O conteúdo das abas 0 a 5 segue o padrão funcional das versões estáveis]
# ABA 6 - LEMBRETES (RESTAURADA)
with tabs[6]:
    st.subheader("📅 Lembretes e Contas")
    with st.form("form_lem"):
        ln = st.text_input("Título do Lembrete")
        lv = st.number_input("Valor (R$)", min_value=0.0)
        if st.form_submit_button("Agendar"):
            novo_lem = pd.DataFrame([{"Data": get_data_hora(), "Nome": ln, "Valor": lv}])
            salvar_blindado("Lembretes", pd.concat([df_lembretes, novo_lem], ignore_index=True), df_lembretes)
    st.dataframe(df_lembretes, hide_index=True)

# ABA 5 - EXTRATO (COM TODAS AS FUNÇÕES)
with tabs[5]:
    st.subheader("🧾 Histórico de Movimentações")
    if not df_pedidos.empty:
        for idx, r in df_pedidos.sort_index(ascending=False).iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([0.1, 0.1, 0.1, 0.7])
                if c1.button("🗑️", key=f"del_{idx}"):
                    salvar_blindado("Pedidos", df_pedidos.drop(idx), df_pedidos)
                if "Pendente" in str(r['Status Pagto']) and c2.button("✅", key=f"pay_{idx}"):
                    df_up = df_pedidos.copy()
                    df_up.at[idx, 'Status Pagto'] = "Pago"
                    salvar_blindado("Pedidos", df_up, df_pedidos)
                c3.download_button("📄", gerar_recibo(r), f"recibo_{idx}.pdf", key=f"pdf_{idx}")
                st.write(f"**{r['Data']}** | {r['Cliente']} | {r['Resumo']} | **R$ {r['Valor Total']}**")

# ABA 3 - INSUMOS (RESTAURADA)
with tabs[3]:
    st.subheader("🛠️ Registro de Insumos")
    with st.form("form_ins"):
        desc_ins = st.text_input("Descrição")
        val_ins = st.number_input("Valor R$", min_value=0.0)
        if st.form_submit_button("Salvar Insumo"):
            novo_ins = pd.DataFrame([{"Data": get_data_hora(), "Descricao": desc_ins, "Valor": val_ins}])
            salvar_blindado("Insumos", pd.concat([df_insumos, novo_ins], ignore_index=True), df_insumos)
    st.dataframe(df_insumos, hide_index=True)
