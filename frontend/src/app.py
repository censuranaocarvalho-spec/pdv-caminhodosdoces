import streamlit as st
import requests
import pandas as pd

CORE_ORDERS_URL = "http://core-orders:8001/api/v1/orders"
FINANCE_URL = "http://finance-ledger:8003/api/v1/ledger/entries"
INTEGRATIONS_URL = "http://integrations-hub:8002/api/v1/integrations/queue/logs"

st.set_page_config(page_title="Caminho dos Doces - PDV", page_icon="🧁", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap');

    :root {
        --lilas: #C5CEE6;
        --turquesa: #C2E5E9;
        --rosa-bebe: #F0BCCF;
        --chocolate: #7C4A3A;
        --fundo: #FFFBFC;
    }

    html, body, [data-testid="stAppViewContainer"], .main, .block-container {
        font-family: Poppins, Verdana, Geneva, sans-serif !important;
        color: var(--chocolate);
    }

    html, body, [data-testid="stAppViewContainer"] {
        background-color: var(--fundo) !important;
        overflow-y: auto !important;
        height: auto !important;
        max-height: none !important;
    }

    .main, .block-container, section.main > div {
        overflow-y: visible !important;
        background-color: var(--fundo);
    }

    h1, h2, h3, h4, p, label, span, div {
        font-family: Poppins, Verdana, Geneva, sans-serif !important;
    }

    h1, h2, h3 {
        color: var(--chocolate) !important;
    }

    [data-testid="stTabs"] button[aria-selected="true"] {
        color: var(--chocolate) !important;
        border-bottom-color: var(--rosa-bebe) !important;
    }

    .stButton>button {
        background-color: var(--chocolate);
        color: #ffffff;
        border-radius: 10px;
        font-weight: 600;
        font-family: Poppins, Verdana, Geneva, sans-serif !important;
        border: none;
        width: 100%;
        min-height: 44px;
    }
    .stButton>button:hover {
        background-color: #5E382C;
        color: white;
    }

    [data-testid="stExpander"] {
        background-color: #F7F8FC;
        border: 1px solid var(--lilas);
        border-radius: 12px;
    }

    div[data-baseweb="notification"] {
        border-radius: 10px;
    }

    @media (max-width: 900px) {
        .main .block-container {
            padding-left: 0.8rem;
            padding-right: 0.8rem;
            padding-top: 1rem;
        }
        [data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
            margin-bottom: 1rem;
        }
    }
    </style>
""", unsafe_allow_html=True)

st.title("🧁 Caminho dos Doces - Central Operacional PDV")

tab_pdv, tab_agenda, tab_finance, tab_hub = st.tabs([
    "🛒 Frente de Caixa & PDV", 
    "📅 Agenda & Encomendas", 
    "💰 Financeiro", 
    "🔌 Hub Integrado"
])

with tab_pdv:
    col_v1, col_v2 = st.columns(2, gap="medium")
    
    with col_v1:
        st.subheader("1 & 2. Cliente & Logística")
        name = st.text_input("Nome completo da Cliente")
        cpf = st.text_input("CPF na Nota (Opcional)", placeholder="123.456.789-00")
        phone = st.text_input("Telefone / WhatsApp", "(11) 9")
        referral = st.selectbox("Como conheceu", ["Instagram", "Indicação", "WhatsApp", "Google", "Outros"])
        
        event_date = st.date_input("Data do evento / entrega")
        event_time = st.text_input("Horário", "14:00")
        
        delivery_method = st.selectbox(
            "Forma de Recebimento / Entrega", 
            [
                "Retirada na Loja", 
                "Motoboy Próprio da Loja", 
                "Uber / 99 Entregas (Parceiro)", 
                "Entrega Particular (Cliente envia portador)"
            ]
        )
        delivery_fee = st.number_input("Taxa de Entrega (R$)", min_value=0.0, value=0.0)
        
        # --- Integração de Endereço via CEP ---
        st.markdown("##### 📍 Endereço de Entrega")
        cep_input = st.text_input("CEP (Opcional)", placeholder="00000-000")
        street_val, neighbor_val, city_val = "", "", ""
        
        if cep_input:
            cep_clean = "".join(filter(str.isdigit, cep_input))
            if len(cep_clean) == 8:
                try:
                    res_cep = requests.get(f"https://viacep.com.br/ws/{cep_clean}/json/", timeout=3)
                    if res_cep.status_code == 200 and "erro" not in res_cep.json():
                        cep_data = res_cep.json()
                        street_val = cep_data.get("logradouro", "")
                        neighbor_val = cep_data.get("bairro", "")
                        city_val = f"{cep_data.get('localidade', '')}/{cep_data.get('uf', '')}"
                        st.success(f"CEP localizado: {street_val}, {neighbor_val} - {city_val}")
                    else:
                        st.warning("CEP não localizado. Preencha o endereço manualmente.")
                except Exception:
                    st.warning("Não foi possível consultar o CEP automaticamente.")

        street = st.text_input("Rua / Logradouro", value=street_val)
        col_num, col_comp = st.columns([1, 2])
        with col_num:
            house_number = st.text_input("Número / Casa")
        with col_comp:
            complement = st.text_input("Complemento / Ponto de Ref.")
        
        neighborhood = st.text_input("Bairro", value=neighbor_val)
        city_uf = st.text_input("Cidade / UF", value=city_val)

        # Formatação do endereço completo
        full_address_parts = [p for p in [street, f"Nº {house_number}" if house_number else "", complement, neighborhood, city_uf] if p.strip()]
        full_address = ", ".join(full_address_parts) if full_address_parts else "Retirada na Loja"

        st.markdown("---")
        st.subheader("4. Conversa com a Cliente & Restrições")
        theme_colors_topper = st.text_input("Tema, Cores e Topper (Chat)")
        alteration_deadline = st.text_input("Data Limite para Alterações", "2026-10-20")
        allergies = st.text_input("Alergias / Restrições", "Nenhuma")
        extra_observations = st.text_area("Observações extras")

    with col_v2:
        st.subheader("3. Vitrine de Doces & Carrinho")
        produto = st.selectbox(
            "Selecionar Item do Catálogo",
            [
                ("DOCE-001", "Bolo de Chocolate Belga com Morango", 120.00),
                ("DOCE-002", "Brigadeiro Gourmet Artesanal (Un)", 6.00),
                ("DOCE-003", "Ovo de Páscoa Trufado de Colher", 85.00),
                ("DOCE-004", "Caixa Presente de Alfajor (6un)", 45.00)
            ],
            format_func=lambda x: f"{x[1]} — R$ {x[2]:.2f}"
        )
        qtd = st.number_input("Quantidade", min_value=1, value=1)

        if "cart" not in st.session_state:
            st.session_state.cart = []

        if st.button("➕ Adicionar ao Carrinho"):
            st.session_state.cart.append({
                "productId": produto[0],
                "productName": produto[1],
                "quantity": int(qtd),
                "unitPrice": float(produto[2])
            })
            st.success(f"Adicionado: {qtd}x {produto[1]}")

        if st.session_state.cart:
            st.markdown("#### 🛍️ Itens no Carrinho:")
            for item in st.session_state.cart:
                st.write(f"- {item['quantity']}x {item['productName']} (R$ {item['unitPrice']:.2f})")
            if st.button("🗑️ Limpar Carrinho"):
                st.session_state.cart = []
                st.rerun()

        st.markdown("---")
        st.subheader("5. Pagamento")
        pay_method = st.selectbox("Método de Pagamento", ["PIX (50% Entrada + 50% Entrega)", "DINHEIRO", "CREDITO"])
        installments = 1
        if pay_method == "CREDITO":
            installments = st.selectbox("Parcelamento (Máx 5x com juros)", [1, 2, 3, 4, 5])

        subtotal_cart = sum(i["quantity"] * i["unitPrice"] for i in st.session_state.cart) if st.session_state.cart else 0.0
        total_geral = subtotal_cart + delivery_fee
        sinal_val = total_geral * 0.5 if "PIX" in pay_method else total_geral

        st.info(f"💰 Subtotal: R$ {subtotal_cart:.2f} | 🚚 Entrega: R$ {delivery_fee:.2f}\n\n"
                f"📊 **Total Geral:** R$ {total_geral:.2f}\n\n"
                f"🔹 **Sinal Agora:** R$ {sinal_val:.2f}\n"
                f"🔸 **Restante na Entrega:** R$ {total_geral - sinal_val:.2f}")

        if st.button("🚀 Finalizar Venda & Emitir Ficha", type="primary"):
            if not st.session_state.cart:
                st.error("Adicione itens ao carrinho!")
            elif not name or not phone:
                st.error("Preencha o nome e o telefone!")
            else:
                mapped_method = "PIX" if "PIX" in pay_method else ("CREDITO" if pay_method == "CREDITO" else pay_method)
                payload = {
                    "customer": {
                        "name": name, 
                        "phone": phone, 
                        "channel": referral, 
                        "referral": referral, 
                        "address": full_address,
                        "cpf": cpf
                    },
                    "logistics": {
                        "event_date": str(event_date), 
                        "event_time": event_time, 
                        "delivery_method": delivery_method, 
                        "address": full_address
                    },
                    "items": st.session_state.cart,
                    "chat_restrictions": {
                        "theme_colors_topper": theme_colors_topper,
                        "alteration_deadline": alteration_deadline,
                        "allergies": allergies,
                        "extra_observations": extra_observations
                    },
                    "payment": {
                        "method": mapped_method,
                        "installments": installments,
                        "delivery_fee": delivery_fee
                    }
                }
                try:
                    res = requests.post(CORE_ORDERS_URL, json=payload)
                    if res.status_code in [200, 201]:
                        st.balloons()
                        st.success("Venda emitida com sucesso!")
                        st.session_state.cart = []
                    else:
                        st.error(f"Erro: {res.json().get('detail', res.text)}")
                except Exception as e:
                    st.error(f"Erro de conexão: {e}")

with tab_agenda:
    st.subheader("📅 Agenda & Ficha de Encomendas")
    if st.button("🔄 Atualizar Agenda"):
        st.rerun()

    try:
        res = requests.get(CORE_ORDERS_URL)
        if res.status_code == 200:
            orders = res.json()
            if orders:
                for o in orders:
                    cust = o.get("customer", {})
                    log = o.get("logistics", {})
                    chat = o.get("chat_restrictions", {})
                    items_str = ", ".join([f"{i.get('quantity', 1)}x {i.get('productName', 'Produto')}" for i in o.get("items", [])])
                    
                    sinal_val = o.get("sinalAmount", o.get("totalAmount", 0.0))
                    restante_val = o.get("restanteAmount", 0.0)
                    total_val = o.get("totalAmount", 0.0)
                    
                    with st.expander(f"📌 {o.get('orderId', 'ORD')} | {cust.get('name', 'Cliente')} | R$ {total_val:.2f}"):
                        st.markdown(f"""
                        **1. Cliente:** {cust.get('name')} | CPF: {cust.get('cpf') or 'Não informado'} | Tel: {cust.get('phone')}
                        **2. Logística:** {log.get('event_date')} às {log.get('event_time')} ({log.get('delivery_method')})
                        - **Endereço:** {log.get('address', 'Retirada na Loja')}
                        **3. Produtos:** {items_str}
                        **4. Chat & Tema:** {chat.get('theme_colors_topper')} | Alergias: {chat.get('allergies')}
                        **5. Pagamento:** {o.get('paymentMethod', 'A Definir')} | Sinal: R$ {sinal_val:.2f} | Restante: R$ {restante_val:.2f}
                        """)
                        
                        if st.button(f"📤 Enviar Cupom via WhatsApp ({cust.get('phone')})", key=f"wa_{o.get('orderId')}"):
                            try:
                                res_wa = requests.post(f"http://core-orders:8001/api/v1/orders/{o.get('orderId')}/send-whatsapp")
                                if res_wa.status_code == 200:
                                    st.success("Cupom enviado via WhatsApp com sucesso!")
                                else:
                                    st.error(f"Erro: {res_wa.json().get('detail', res_wa.text)}")
                            except Exception as e:
                                st.error(f"Erro de conexão: {e}")
            else:
                st.info("Nenhuma encomenda registada.")
    except Exception as e:
        st.error(f"Erro ao carregar agenda: {e}")

with tab_finance:
    st.subheader("💰 Livro Razão & Transações ACID")
    try:
        res = requests.get(FINANCE_URL)
        if res.status_code == 200:
            records = res.json()
            if records:
                st.dataframe(pd.DataFrame(records), use_container_width=True)
            else:
                st.info("Nenhum lançamento financeiro.")
    except Exception as e:
        st.info("Finance Ledger a aguardar requisições.")

with tab_hub:
    st.subheader("🔌 Hub de Integrações & Logs")
    if st.button("🔄 Atualizar Logs"):
        st.rerun()
    try:
        res = requests.get(INTEGRATIONS_URL)
        if res.status_code == 200:
            logs = res.json()
            if logs:
                for l in logs:
                    st.success(f"Tarefa: {l['taskId']} | {l['processedAt']}")
                    st.json(l['details'])
            else:
                st.info("Nenhuma mensagem na fila.")
    except Exception as e:
        st.info("Hub sem registos no momento.")
