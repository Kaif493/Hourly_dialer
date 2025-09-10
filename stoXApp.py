import streamlit as st
import pandas as pd

st.title("📊 Ledger Summary Dashboard")

# File uploader
uploaded_file = st.file_uploader("Upload your Ledger file", type=["xlsx", "csv"])

if uploaded_file:
    # Read file
    if uploaded_file.name.endswith(".xlsx"):
        df = pd.read_excel(uploaded_file)
    else:
        df = pd.read_csv(uploaded_file)
    
    st.write("### Raw Data Preview")
    st.dataframe(df.head())

    # Ensure datetime
    df["CreatedAt"] = pd.to_datetime(df["CreatedAt"], errors="coerce")
    df["Date"] = df["CreatedAt"].dt.date  # extract date only

    # Aggregation logic
    result = df.groupby(["ClientID", "Date"]).agg(
        total_deposit=("Credit", lambda x: x[df.loc[x.index, "LedgerType"] == "DEPOSIT"].sum()),
        total_withdrawal=("Debit", lambda x: x[df.loc[x.index, "LedgerType"] == "WITHDRAW"].sum()),
        total_mtm_update=("Credit", lambda x: x[df.loc[x.index, "LedgerType"] == "MTM-UPDATE"].sum()),
        total_withdraw_cancelled=("Credit", lambda x: x[df.loc[x.index, "LedgerType"] == "WITHDRAW CANCELLED"].sum()),
        total_NBP=("Credit", lambda x: x[df.loc[x.index, "LedgerType"] == "NEGATIVE BALANCE PROTECTION"].sum()),
        total_brokrage=("Debit", lambda x: x[df.loc[x.index, "LedgerType"] == "BROKERAGE"].sum()),
        Bill_dr=("Debit", lambda x: x[df.loc[x.index, "LedgerType"] == "BILL"].sum()),
        Bill_cr=("Credit", lambda x: x[df.loc[x.index, "LedgerType"] == "BILL"].sum()),
        last_activity=("CreatedAt", "max")
    ).reset_index()

    st.write("### Aggregated Ledger Summary")
    st.dataframe(result)

    # Filters
    client_filter = st.selectbox("Select Client", ["All"] + result["ClientID"].unique().tolist())
    if client_filter != "All":
        result = result[result["ClientID"] == client_filter]

    st.write("### Filtered Data")
    st.dataframe(result)

    # Download option
    st.download_button(
        label="📥 Download Result as CSV",
        data=result.to_csv(index=False),
        file_name="ledger_summary.csv",
        mime="text/csv"
    )
