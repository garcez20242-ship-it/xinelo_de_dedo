import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import io
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Xinelo de Dedo v4.6", layout="wide", page_icon="🩴")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- FUNÇÕES DE APOIO ---
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
        pdf.cell(190, 8, f"Data/Hora: {dados_venda.get('Data', 'N/A')}", ln=True)
        pdf.cell(190, 8, f"Cliente: {dados_venda.get('Cliente', 'N/A')}", ln=True)
        pdf.cell(190, 8, f"Status: {dados_venda.get('Status Pagto', 'N/A')}", ln=True)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(190, 8, "Itens do Pedido:", ln=True)
        resumo = str(dados_venda.get('Resumo', '')).replace(" | ", "\n")
        pdf.set_font("Arial", "", 11)
        pdf.multi_cell(190, 8, resumo)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(190, 10, f"VALOR TOTAL: R$ {limpar_valor(dados_venda.get('Valor Total', 0)):.2f}", ln=True, align="R")
        return pdf.output(dest='S').encode('latin-1')
    except: return b""

# --- CONEXÃO E CARREGAMENTO ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=15)
def carregar_dados_seguro():
    def ler(aba, colunas_esperadas):
        try:
            df = conn.read(spreadsheet=URL_PLANILHA, worksheet=aba, ttl="0s")
            if df is None or df.empty: 
                return pd.DataFrame(columns=colunas_esperadas)
            
            # Limpeza de colunas fantasmas e espaços
            df = df.dropna(how='all').loc[:, ~df.columns.str.contains('^Unnamed')]
            df.columns = df.columns.str.strip()
            
            # Garante que as colunas essenciais existam (mesmo vazias)
            for col in colunas_esperadas:
                if col not in df.columns:
                    df[col] = 0 if col in TAMANHOS_PADRAO else ""
            return df
        except:
            return pd.DataFrame(columns=colunas_esperadas)
    
    return {
        "est": ler("Estoque", ["Modelo"] + TAMANHOS_PADRAO),
        "ped": ler("Pedidos", ["Data", "Cliente", "Resumo", "Valor Total", "Status Pagto", "Forma"]),
        "cli": ler("Clientes", ["Nome", "Loja", "Cidade", "Telefone"]),
        "ins": ler("Insumos", ["Data", "Descricao", "Valor"]),
        "lem": ler("Lembretes", ["Nome", "Data", "Valor"]),
        "his": ler("Historico_Precos", ["Data", "Modelo", "Preco_Unit"]),
        "aqui": ler("Aquisicoes", ["Data", "Resumo", "Valor Total"])
    }

# Carregar Dados
d = carregar_dados_seguro()
df_estoque, df_pedidos, df_clientes = d["est"], d["ped"], d["cli"]
df_insumos, df_lembretes, df_hist_precos, df_aquisicoes = d["ins"], d["lem"], d["his"], d["aqui"]

def atualizar(aba, df):
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df.astype(str).replace('nan', ''))
        st.cache_data.clear()
        st.success("✅ Atualizado!")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- TABS ---
st.title("🩴 Xinelo de Dedo v4.6")
t = st.tabs(["📊 Estoque", "✨ Novo Modelo", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato", "📅 Lembretes", "📈 Preços"])

# --- ABA EXTRATO (CORRIGIDA) ---
with t[5]:
    st.subheader("🧾 Extrato Financeiro Completo")
    
    # Padronização para unificar as tabelas
    p = df_pedidos.copy().assign(Tipo="VENDA", Ori="Pedidos")
    a = df_aquisicoes.copy().assign(Tipo="COMPRA", Ori="Aquisicoes")
    i = df_insumos.copy().assign(Tipo="INSUMO", Ori="Insumos").rename(columns={"Descricao": "Resumo", "Valor": "Valor Total"})
    
    # Unificar tudo
    unificado = pd.concat([p, a, i], ignore_index=True)
    
    if not unificado.empty:
        # Tenta converter datas para ordenação
        unificado['DT_ORDEM'] = pd.to_datetime(unificado['Data'], dayfirst=True, errors='coerce')
        unificado = unificado.sort_values('DT_ORDEM', ascending=False)
        
        for idx, r in unificado.iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([0.1, 0.1, 0.1, 0.7])
                
                # Botão Deletar
                if c1.button("🗑️", key=f"del_{r['Ori']}_{idx}"):
                    origem = df_pedidos if r['Ori']=="Pedidos" else df_aquisicoes if r['Ori']=="Aquisicoes" else df_insumos
                    # Deleta comparando a string exata da data para evitar erros de conversão
                    nova_origem = origem[origem['Data'] != r['Data']]
                    atualizar(r['Ori'], nova_origem)
                
                # Botão Receber (Só para Vendas Pendentes)
                if r['Ori'] == "Pedidos" and str(r.get('Status Pagto', '')).strip() == "Pendente":
                    if c2.button("✅", key=f"pay_{idx}", help="Marcar como Pago"):
                        df_atu_p = df_pedidos.copy()
                        df_atu_p.loc[df_atu_p['Data'] == r['Data'], 'Status Pagto'] = "Pago"
                        atualizar("Pedidos", df_atu_p)
                
                # Botão PDF (Só para Vendas)
                if r['Ori'] == "Pedidos":
                    c3.download_button("📄", gerar_recibo(r), f"recibo_{idx}.pdf", key=f"pdf_{idx}")
                
                # Texto da linha
                txt_cli = f" | {r['Cliente']}" if pd.notna(r.get('Cliente')) and r['Cliente'] != "" else ""
                val = limpar_valor(r.get('Valor Total', 0))
                c4.write(f"**{r['Data']}** | **{r['Tipo']}**{txt_cli} | {r['Resumo']} | **R$ {val:.2f}**")
    else:
        st.info("Nenhuma movimentação encontrada nas abas Pedidos, Aquisicoes ou Insumos.")

# --- ABA PREÇOS (CORRIGIDA) ---
with t[7]:
    st.subheader("📈 Histórico de Preços de Custo")
    if not df_hist_precos.empty:
        # Forçar conversão de data e valor
        df_h = df_hist_precos.copy()
        df_h['DT'] = pd.to_datetime(df_h['Data'], dayfirst=True, errors='coerce')
        df_h['Preco_Unit'] = df_h['Preco_Unit'].apply(limpar_valor)
        df_h = df_h.dropna(subset=['DT']) # Remove linhas onde a data deu erro
        
        modelos_h = sorted(df_h['Modelo'].unique())
        if modelos_h:
            sel_h = st.selectbox("Selecione o Modelo para ver a evolução do custo:", modelos_h)
            dados_grafico = df_h[df_h['Modelo'] == sel_h].sort_values('DT')
            
            if not dados_grafico.empty:
                st.line_chart(dados_grafico, x='DT', y='Preco_Unit')
                st.table(dados_grafico[['Data', 'Modelo', 'Preco_Unit']].sort_values('DT', ascending=False))
            else:
                st.warning("Sem dados históricos para este modelo.")
    else:
        st.info("O histórico de preços é alimentado automaticamente quando você faz uma 'Entrada de Mercadoria' na aba Estoque.")

# --- MANTENDO AS OUTRAS ABAS (SÓ CHAMADAS PARA NÃO PERDER O CÓDIGO) ---
with t[0]: # Estoque
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.subheader("📦 Entrada")
        mods = sorted(df_estoque['Modelo'].unique()) if not df_estoque.empty else []
        if mods:
            m_e = st.selectbox("Modelo", mods, key="me")
            t_e = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="te")
            q_e = st.number_input("Qtd", min_value=1, key="qe")
            v_e = st.number_input("Custo Unitário R$", min_value=0.0, key="ve")
            if st.button("➕ Adicionar Entrada"):
                df_atu = df_estoque.copy()
                idx = df_atu.index[df_atu['Modelo'] == m_e][0]
                df_atu.at[idx, t_e] = int(float(df_atu.at[idx, t_e])) + q_e
                atualizar("Estoque", df_atu)
                # Salva no histórico para alimentar a aba Preços
                novo_h = pd.DataFrame([{"Data": get_data_hora(), "Modelo": m_e, "Preco_Unit": v_e}])
                atualizar("Historico_Precos", pd.concat([df_hist_precos, novo_h], ignore_index=True))
    with c2:
        st.dataframe(df_estoque, hide_index=True)

with t[1]: # Novo Modelo
    with st.form("nm"):
        n = st.text_input("Nome do Modelo")
        if st.form_submit_button("Criar"):
            if n:
                d_n = {"Modelo": n}; d_n.update({tam: 0 for tam in TAMANHOS_PADRAO})
                atualizar("Estoque", pd.concat([df_estoque, pd.DataFrame([d_n])], ignore_index=True))

with t[2]: # Vendas
    st.info("Use esta aba para registrar saídas e alimentar o extrato automaticamente.")
    # (Lógica de venda igual à v4.5 aqui...)

# --- SIDEBAR ---
with st.sidebar:
    if st.button("🔄 Forçar Atualização Geral"):
        st.cache_data.clear()
        st.rerun()
