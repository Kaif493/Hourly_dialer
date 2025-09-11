import streamlit as st
import pandas as pd
from io import BytesIO
import re

# -------------------
# Helper: Export to multi-sheet Excel with totals (openpyxl only)
# -------------------
def to_excel_multisheet(client_balance, ledger_summary, script_report, ledger_type_report, deposit_withdraw_df, other_ledger_df):
    output = BytesIO()
    
    # Add totals rows
    client_balance_totals = pd.DataFrame([{
        'ClientID': 'Total',
        'Last_Activity': '',
        'Balance': client_balance['Balance'].sum()
    }])
    client_balance_with_total = pd.concat([client_balance, client_balance_totals], ignore_index=True)

    ledger_summary_totals = ledger_summary.copy()
    total_row = pd.DataFrame(ledger_summary[ledger_summary.select_dtypes(include='number').columns].sum()).T
    total_row['ClientID'] = 'Total'
    total_row['Date'] = ''
    ledger_summary_with_total = pd.concat([ledger_summary, total_row], ignore_index=True)

    script_report_totals = pd.DataFrame([{
        'Script': 'Total',
        'Total_Debit': script_report['Total_Debit'].sum(),
        'Total_Credit': script_report['Total_Credit'].sum(),
        'Transactions': script_report['Transactions'].sum(),
        'P&L': script_report['P&L'].sum()
    }])
    script_report_with_total = pd.concat([script_report, script_report_totals], ignore_index=True)
    
    # Use openpyxl only
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        client_balance_with_total.to_excel(writer, index=False, sheet_name="Client Ledger Balance")
        ledger_summary_with_total.to_excel(writer, index=False, sheet_name="Deposit & Withdrawal")
        script_report_with_total.to_excel(writer, index=False, sheet_name="Script Wise Report")
        ledger_type_report.to_excel(writer, index=False, sheet_name="Ledger Type Wise Report")
        deposit_withdraw_df.to_excel(writer, index=False, sheet_name="Deposit & Withdraw Report")
        other_ledger_df.to_excel(writer, index=False, sheet_name="Other Ledger Types")
    
    return output.getvalue()

# -------------------
# Helper: Extract script name from narration
# -------------------
def extract_script(narration):
    if pd.isna(narration):
        return None
    match = re.search(r"for\s+([^\s]+)", str(narration))
    return match.group(1) if match else None

# -------------------
# Streamlit UI
# -------------------
st.title("📊 Ledger Summary Dashboard")

# File uploader
uploaded_file = st.file_uploader("Upload Ledger CSV/XLSX", type=["csv", "xlsx"])
if uploaded_file:
    if uploaded_file.name.endswith(".xlsx"):
        df = pd.read_excel(uploaded_file)
    else:
        df = pd.read_csv(uploaded_file)

    df["CreatedAt"] = pd.to_datetime(df["CreatedAt"], errors="coerce")
    df["Date"] = df["CreatedAt"].dt.date

    # -------------------
    # Sidebar Filters
    # -------------------
    st.sidebar.header("Filters")
    
    # Client filter
    client_options = ["All"] + df["ClientID"].dropna().unique().tolist()
    client_filter = st.sidebar.selectbox("Select Client", client_options)
    if client_filter != "All":
        df = df[df["ClientID"] == client_filter]

    # Date range filter
    min_date, max_date = df["Date"].min(), df["Date"].max()
    date_range = st.sidebar.date_input("Select Date Range", [min_date, max_date])
    if len(date_range) == 2:
        start_date, end_date = date_range
        df = df[(df["Date"] >= start_date) & (df["Date"] <= end_date)]

    # -------------------
    # Report 1: Client Ledger Balance
    # -------------------
    df_sorted = df.sort_values(["ClientID", "CreatedAt"])
    client_balance = df_sorted.groupby("ClientID").agg(
        Last_Activity=("CreatedAt", "max"),
        Balance=("Balance", "last")
    ).reset_index()

    # -------------------
    # Report 2: Ledger Summary
    # -------------------
    pivot = df.pivot_table(
        index=["ClientID", "Date"],
        columns="LedgerType",
        values=["Debit", "Credit"],
        aggfunc="sum",
        fill_value=0
    ).reset_index()
    pivot.columns = ["_".join(filter(None, col)).strip() for col in pivot.columns.values]
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
    script_report["P&L"] = script_report["Total_Credit"] - script_report["Total_Debit"]

    # Profit & Loss filter
    st.sidebar.subheader("Profit / Loss Filter")
    pl_filter = st.sidebar.radio("Show:", ["All", "Profit Only", "Loss Only"])
    if pl_filter == "Profit Only":
        script_report = script_report[script_report["P&L"] > 0]
    elif pl_filter == "Loss Only":
        script_report = script_report[script_report["P&L"] < 0]

    # -------------------
    # Report 4: Ledger Type Wise Report
    # -------------------
    ledger_type_report = df.groupby("LedgerType").agg(
        Total_Debit=("Debit", "sum"),
        Total_Credit=("Credit", "sum")
    ).reset_index()
    ledger_type_report["Net"] = ledger_type_report["Total_Credit"] - ledger_type_report["Total_Debit"]
    ledger_type_summary = pd.DataFrame([{
        "LedgerType": "Grand Summary:",
        "Total_Debit": ledger_type_report["Total_Debit"].sum(),
        "Total_Credit": ledger_type_report["Total_Credit"].sum(),
        "Net": ledger_type_report["Net"].sum()
    }])
    ledger_type_report = pd.concat([ledger_type_report, ledger_type_summary], ignore_index=True)

    # -------------------
    # Report 5: Deposit & Withdraw Report (Adjusted)
    # -------------------
    withdraw_total = df[df["LedgerType"].str.upper() == "WITHDRAW"]["Debit"].sum()
    cancelled_total = df[df["LedgerType"].str.upper() == "WITHDRAWAL CANCELLED"]["Debit"].sum()
    adjusted_withdraw = withdraw_total - cancelled_total

    deposit_withdraw_df = pd.DataFrame([
        {"LedgerType": "DEPOSIT",
         "Total_Debit": df[df["LedgerType"].str.upper() == "DEPOSIT"]["Debit"].sum(),
         "Total_Credit": df[df["LedgerType"].str.upper() == "DEPOSIT"]["Credit"].sum()},
        {"LedgerType": "WITHDRAW",
         "Total_Debit": adjusted_withdraw,
         "Total_Credit": 0}
    ])
    deposit_withdraw_df["Net"] = deposit_withdraw_df["Total_Credit"] - deposit_withdraw_df["Total_Debit"]

    dep_with_summary = pd.DataFrame([{
        "LedgerType": "Grand Summary:",
        "Total_Debit": deposit_withdraw_df["Total_Debit"].sum(),
        "Total_Credit": deposit_withdraw_df["Total_Credit"].sum(),
        "Net": deposit_withdraw_df["Net"].sum()
    }])
    deposit_withdraw_df = pd.concat([deposit_withdraw_df, dep_with_summary], ignore_index=True)

    # -------------------
    # Report 6: Other Ledger Types Report
    # -------------------
    other_ledger_df = df[~df["LedgerType"].str.upper().isin(["DEPOSIT", "WITHDRAW", "WITHDRAWAL CANCELLED"])] \
        .groupby("LedgerType").agg(
            Total_Debit=("Debit", "sum"),
            Total_Credit=("Credit", "sum")
        ).reset_index()
    other_ledger_df["Net"] = other_ledger_df["Total_Credit"] - other_ledger_df["Total_Debit"]

    # Add Grand Summary row
    other_summary = pd.DataFrame([{
        "LedgerType": "Grand Summary:",
        "Total_Debit": other_ledger_df["Total_Debit"].sum(),
        "Total_Credit": other_ledger_df["Total_Credit"].sum(),
        "Net": other_ledger_df["Net"].sum()
    }])
    other_ledger_df = pd.concat([other_ledger_df, other_summary], ignore_index=True)

    # -------------------
    # Show Reports
    # -------------------
    st.subheader("📊 Client Ledger Balance")
    st.dataframe(client_balance)

    st.subheader("📑 Ledger Summary (Daily, Multi-LedgerType)")
    st.dataframe(ledger_summary)

    st.subheader("📄 Script Wise Report")
    st.dataframe(script_report)

    st.subheader("📘 Ledger Type Wise Report")
    st.dataframe(ledger_type_report)

    st.subheader("🏦 Deposit & Withdraw Report (Adjusted)")
    st.dataframe(deposit_withdraw_df)

    st.subheader("📒 Other Ledger Types Report")
    st.dataframe(other_ledger_df)

    # -------------------
    # Download Excel
    # -------------------
    excel_data = to_excel_multisheet(client_balance, ledger_summary, script_report, ledger_type_report, deposit_withdraw_df, other_ledger_df)
    st.download_button(
        label="📥 Download Excel Report (Filtered + Totals)",
        data=excel_data,
        file_name="ledger_reports.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
