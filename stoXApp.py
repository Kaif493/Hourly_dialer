import streamlit as st
import pandas as pd
from io import BytesIO
from xlsxwriter import Workbook
import re

# -------------------
# Helper: Export to multi-sheet Excel
# -------------------
def to_excel_multisheet(client_balance, ledger_summary, script_report):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        client_balance.to_excel(writer, index=False, sheet_name="Client Ledger Balance")
        ledger_summary.to_excel(writer, index=False, sheet_name="Deposit & Withdrawal")
        script_report.to_excel(writer, index=False, sheet_name="Script Wise Report")
    processed_data = output.getvalue()
    return processed_data

# -------------------
# Extract script name from narration
# -------------------
def extract_script(narration):
    if pd.isna(narration):
        return None
    match = re.search(r"for\s+([^\s]+)", str(narration))  # flexible to capture scripts
    return match.group(1) if match else None

# -------------------
# Load Data
# -------------------
uploaded_file = st.file_uploader("Upload Ledger CSV", type=["csv"])
if uploaded_file:
    df = pd.read_csv(uploaded_file)

    # Ensure datetime
    df["CreatedAt"] = pd.to_datetime(df["CreatedAt"], errors="coerce")
    df["Date"] = df["CreatedAt"].dt.date  # for daily aggregation

    # -------------------
    # Report 1: Client Ledger Balance (overall)
    # -------------------
    df_sorted = df.sort_values(["ClientID", "CreatedAt"])
    client_balance = df_sorted.groupby("ClientID").agg(
        Last_Activity=("CreatedAt", "max"),
        Balance=("Balance", "last")
    ).reset_index()

    # -------------------
    # Report 2: Ledger Summary (daily, multi-ledger-type)
    # -------------------
    pivot = df.pivot_table(
        index=["ClientID", "Date"],
        columns="LedgerType",
        values=["Debit", "Credit"],
        aggfunc="sum",
        fill_value=0
    ).reset_index()

    # Flatten multi-level columns
    pivot.columns = ["_".join(filter(None, col)).strip() for col in pivot.columns.values]

    # Add last activity per day
    last_activity = df.groupby(["ClientID", "Date"])["CreatedAt"].max().reset_index()
    ledger_summary = pivot.merge(last_activity, on=["ClientID", "Date"])

    # -------------------
    # Report 3: Script Wise Report
    # -------------------
    df["Script"] = df["Narration"].apply(extract_script)
    script_report = df.dropna(subset=["Script"]).groupby("Script").agg(
        Total_Debit=("Debit", "sum"),
        Total_Credit=("Credit", "sum"),
        Transactions=("Script", "count")
    ).reset_index()

    # -------------------
    # Show Reports in UI
    # -------------------
    st.subheader("📊 Client Ledger Balance")
    st.dataframe(client_balance)

    st.subheader("📑 Ledger Summary (Daily, Multi-LedgerType)")
    st.dataframe(ledger_summary)

    st.subheader("📄 Script Wise Report")
    st.dataframe(script_report)

    # -------------------
    # Download Multi-Sheet Excel
    # -------------------
    st.download_button(
        label="📥 Download Full Excel Report",
        data=to_excel_multisheet(client_balance, ledger_summary, script_report),
        file_name="ledger_reports.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

