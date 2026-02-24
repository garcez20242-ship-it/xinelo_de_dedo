import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import io
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Xinelo de Dedo v4.4", layout="wide", page_icon="🩴")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- FUNÇÕES AUXILIARES ---
def get_data_hora():
    return (datetime.now() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")

def limpar_valor(valor):
    try:
        if pd.isna(valor) or str(valor).strip() == "": return 0.0
        v = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
        return float(v)
    except: return 0.0

def gerar_recibo(dados_venda):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(190, 10, "RECIBO DE VENDA - XINELO DE DEDO", ln=True, align="C")
        pdf.ln(5)
        pdf.set_font("Arial", "", 12)
        pdf.cell(190, 8, f"Data/Hora: {dados_venda['Data']}", ln=True)
        pdf.cell(190, 8, f"Cliente: {dados_venda['Cliente']}", ln=True)
        pdf.cell(190, 8, f"Status: {dados_venda['Status Pagto']}", ln=True)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(190, 8, "Itens do Pedido:", ln=True)
        resumo_limpo = str(dados_venda['Resumo']).replace(" | ", "\n")
        pdf.set_font("Arial", "", 11)
        pdf.multi_cell(190, 8, resumo_limpo)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(190, 10, f"VALOR TOTAL: R$ {limpar_valor(dados_venda['Valor Total']):.2f}", ln=True, align="R")
        return pdf.output(dest='S').encode('latin-1')
    except: return b""

# --- CONEXÃO E CACHE (BLINDAGEM COTA 429) ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=20) # Reduz drasticamente as requisições ao Google
def buscar_dados_planilha():
    def ler(aba, colunas):
        try:
            df = conn.read(spreadsheet=URL_PLANILHA, worksheet=aba, ttl="0s")
            if df is None or df.empty: return pd.DataFrame(columns=colunas)
            df = df.dropna(how='all').loc[:, ~df.columns.str.contains('^Unnamed')]
            df.columns = df.columns.str.strip()
            return df
        except: return pd.DataFrame(columns=colunas)
    
    return {
        "est": ler("Estoque", ["Modelo"] + TAMANHOS_PADRAO),
        "ped": ler("Pedidos", ["Data", "Cliente", "Resumo", "Valor Total", "Status Pagto", "Forma"]),
        "cli": ler("Clientes", ["Nome", "Loja", "Cidade", "Telefone"]),
        "ins": ler("Insumos", ["Data", "Descricao", "Valor"]),
        "lem": ler("Lembretes", ["Nome", "Data", "Valor"]),
        "his": ler("Historico_Precos", ["Data", "Modelo", "Preco_Unit"]),
        "aqui": ler("Aquisicoes", ["Data", "Resumo", "Valor Total"])
    }

# Carregar do Cache
data = buscar_dados_planilha()
df_estoque, df_pedidos, df_clientes = data["est"], data["ped"], data["cli"]
df_insumos, df_lembretes, df_hist_precos, df_aquisicoes = data["ins"], data["lem"], data["his"], data["aqui"]

def salvar(aba, df):
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df.astype(str).replace('nan', ''))
        st.cache_data.clear() # Limpa o cache após salvar para atualizar a visão
        st.success("✅ Salvo!")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        if "429" in str(e):
            st.error("🚨 Limite do Google atingido. Aguarde 30 segundos e tente novamente.")
        else:
            st.error(f"Erro: {e}")

# --- SIDEBAR ---
with st.sidebar:
    st.header("📊 Resumo Rápido")
    if not df_pedidos.empty:
        fiado = df_pedidos[df_pedidos['Status Pagto'] == "Pendente"]
        if not fiado.empty:
            st.warning(f"Total a Receber: R$ {fiado['Valor Total'].apply(limpar_valor).sum():.2f}")
    
    if not df_estoque.empty:
        st.divider()
        st.subheader("⚠️ Estoque Baixo")
        for _, r in df_estoque.iterrows():
            baixos = [f"{t}" for t in TAMANHOS_PADRAO if (int(float(r[t])) if r[t]!="" else 0) <= 2]
            if baixos: st.caption(f"{r['Modelo']}: {', '.join(baixos)}")

# --- TABS ---
t_est, t_mod, t_ven, t_ins, t_cli, t_ext, t_lem, t_pre = st.tabs(["📊 Estoque", "✨ Novo Modelo", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato", "📅 Lembretes", "📈 Preços"])

with t_est:
    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader("➕ Entrada")
        if not df_estoque.empty:
            m = st.selectbox("Modelo", sorted(df_estoque['Modelo'].unique()), key="m_e")
            t = st.selectbox("Tam", TAMANHOS_PADRAO, key="t_e")
            q = st.number_input("Qtd", min_value=1, key="q_e")
            if st.button("Adicionar Entrada"):
                df_atu = df_estoque.copy()
                idx = df_atu.index[df_atu['Modelo'] == m][0]
                df_atu.at[idx, t] = int(float(df_atu.at[idx, t])) + q
                salvar("Estoque", df_atu)
    with c2:
        st.subheader("📋 Inventário")
        st.dataframe(df_estoque.sort_values("Modelo"), hide_index=True)
        # Lixeira Estoque
        if not df_estoque.empty:
            rem = st.selectbox("Remover Modelo do Sistema:", ["-"] + list(df_estoque['Modelo']))
            if rem != "-" and st.button("🗑️ Excluir Definitivamente"):
                salvar("Estoque", df_estoque[df_estoque['Modelo'] != rem])

with t_mod:
    with st.form("n_m"):
        st.subheader("Novo Modelo")
        nome = st.text_input("Nome do Modelo")
        if st.form_submit_button("Cadastrar"):
            if nome:
                novo = {"Modelo": nome}; novo.update({t: 0 for t in TAMANHOS_PADRAO})
                salvar("Estoque", pd.concat([df_estoque, pd.DataFrame([novo])], ignore_index=True))

with t_ven:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🛒 Carrinho")
        cli = st.selectbox("Cliente", sorted(df_clientes['Nome'].unique()) if not df_clientes.empty else ["Avulso"])
        mod = st.selectbox("Produto", sorted(df_estoque['Modelo'].unique()))
        tam = st.selectbox("Tamanho ", TAMANHOS_PADRAO)
        pre = st.number_input("Preço Venda", min_value=0.0)
        qtd = st.number_input("Qtd ", min_value=1)
        if st.button("🛒 Adicionar Item"):
            if 'cart' not in st.session_state: st.session_state.cart = []
            st.session_state.cart.append({"Mod": mod, "Tam": tam, "Qtd": qtd, "Pre": pre})
            st.rerun()
    with c2:
        if 'cart' in st.session_state and st.session_state.cart:
            total = 0
            resumo = []
            for i, it in enumerate(st.session_state.cart):
                st.write(f"{it['Mod']} {it['Tam']} x{it['Qtd']} - R$ {it['Pre']*it['Qtd']:.2f}")
                total += it['Pre']*it['Qtd']
                resumo.append(f"{it['Mod']}({it['Tam']}x{it['Qtd']})")
            st.write(f"**Total: R$ {total:.2f}**")
            st_p = st.radio("Status", ["Pago", "Pendente"])
            if st.button("Finalizar Venda"):
                df_e = df_estoque.copy()
                for it in st.session_state.cart:
                    idx = df_e.index[df_e['Modelo'] == it['Mod']][0]
                    df_e.at[idx, it['Tam']] = int(float(df_e.at[idx, it['Tam']])) - it['Qtd']
                salvar("Estoque", df_e)
                nova_v = {"Data": get_data_hora(), "Cliente": cli, "Resumo": " | ".join(resumo), "Valor Total": total, "Status Pagto": st_p, "Forma": "N/A"}
                salvar("Pedidos", pd.concat([df_pedidos, pd.DataFrame([nova_v])], ignore_index=True))
                st.session_state.cart = []; st.rerun()

with t_ext:
    st.subheader("🧾 Histórico de Movimentações")
    if not df_pedidos.empty:
        for idx, r in df_pedidos.sort_index(ascending=False).iterrows():
            col1, col2, col3 = st.columns([0.1, 0.1, 0.8])
            if col1.button("🗑️", key=f"del_v_{idx}"):
                salvar("Pedidos", df_pedidos.drop(idx))
            if r['Status Pagto'] == "Pendente":
                if col2.button("✅", key=f"pay_{idx}"):
                    df_p = df_pedidos.copy()
                    df_p.at[idx, 'Status Pagto'] = "Pago"
                    salvar("Pedidos", df_p)
            col3.write(f"**{r['Data']}** | {r['Cliente']} | {r['Resumo']} | R$ {r['Valor Total']} ({r['Status Pagto']})")
            st.download_button("📄 PDF", gerar_recibo(r), f"recibo_{idx}.pdf", key=f"pdf_{idx}")

# --- OUTRAS TABS SEGUEM O MESMO PADRÃO DE 'salvar' ---
with t_ins:
    with st.form("ins"):
        desc = st.text_input("Gasto")
        val = st.number_input("Valor R$")
        if st.form_submit_button("Salvar Insumo"):
            salvar("Insumos", pd.concat([df_insumos, pd.DataFrame([{"Data": get_data_hora(), "Descricao": desc, "Valor": val}])], ignore_index=True))

with t_cli:
    with st.form("cli"):
        n = st.text_input("Nome Cliente")
        if st.form_submit_button("Salvar Cliente"):
            salvar("Clientes", pd.concat([df_clientes, pd.DataFrame([{"Nome": n}])], ignore_index=True))
    st.dataframe(df_clientes, hide_index=True)
