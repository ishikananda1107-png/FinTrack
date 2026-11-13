
from datetime import date
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from database import (
    register_user,
    authenticate_user,
    add_expense,
    get_expenses,
    get_total_expenses,
    get_monthly_expenses,
    delete_expense,
)
from expense_model import predict_category


st.set_page_config(
    page_title="FinTrack",
    page_icon="💰",
    layout="wide"
)

# Use the database file beside this app.py file.
DB_FILE = Path(__file__).resolve().parent / "fintrack.db"


def money(value):
    return f"₹{float(value):,.2f}"


# -------------------- SALARY DATABASE --------------------

def init_salary_table():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_salary (
                user_id INTEGER PRIMARY KEY,
                salary REAL NOT NULL DEFAULT 0
            )
        """)


def get_saved_salary(user_id):
    init_salary_table()

    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute(
            "SELECT salary FROM user_salary WHERE user_id = ?",
            (user_id,)
        ).fetchone()

    return float(row[0]) if row else 0.0


def save_salary(user_id, salary):
    init_salary_table()

    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            INSERT INTO user_salary (user_id, salary)
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET salary = excluded.salary
        """, (user_id, float(salary)))


# -------------------- LOGIN AND REGISTER --------------------

def show_authentication():
    st.title("💰 FinTrack")
    st.subheader("Personal Finance Tracking and Analysis System")
    st.write("Register a local account or log in to manage your expenses.")

    login_tab, register_tab = st.tabs(["Login", "Register"])

    with login_tab:
        with st.form("login_form"):
            username = st.text_input(
                "Username",
                key="login_username"
            )
            password = st.text_input(
                "Password",
                type="password",
                key="login_password"
            )
            login_clicked = st.form_submit_button(
                "Login",
                use_container_width=True
            )

        if login_clicked:
            user = authenticate_user(username, password)

            if user:
                st.session_state["user"] = user
                st.rerun()
            else:
                st.error("Invalid username or password.")

    with register_tab:
        with st.form("register_form"):
            new_username = st.text_input(
                "Choose a username",
                key="register_username"
            )
            new_password = st.text_input(
                "Choose a password (minimum 8 characters)",
                type="password",
                key="register_password"
            )
            confirm_password = st.text_input(
                "Confirm password",
                type="password",
                key="confirm_password"
            )
            register_clicked = st.form_submit_button(
                "Create account",
                use_container_width=True
            )

        if register_clicked:
            if new_password != confirm_password:
                st.error("Passwords do not match.")
            else:
                success, message = register_user(
                    new_username,
                    new_password
                )

                if success:
                    st.success(message)
                else:
                    st.error(message)


# -------------------- DASHBOARD --------------------

def show_dashboard(user):
    user_id = user["id"]

    with st.sidebar:
        st.title("💰 FinTrack")
        st.write(f"Logged in as **{user['username']}**")
        st.caption("Your expenses are stored separately from other users.")

        if st.button("Logout", use_container_width=True):
            st.session_state.pop("user", None)
            st.rerun()

        st.divider()
        st.caption("AI categories are predictions and may need correction.")

    st.title("Personal Finance Dashboard")
    st.write(f"Welcome, {user['username']}!")

    today = date.today()
    current_month = today.strftime("%Y-%m")

    # Load the salary saved for this account.
    saved_salary = get_saved_salary(user_id)

    with st.form(f"salary_form_{user_id}"):
        monthly_income = st.number_input(
            "Enter Your Monthly Salary (₹)",
            min_value=0.0,
            value=float(saved_salary),
            step=500.0,
            key=f"monthly_salary_{user_id}"
        )

        save_salary_clicked = st.form_submit_button("Save Salary")

    if save_salary_clicked:
        save_salary(user_id, monthly_income)
        st.success("Salary saved successfully!")
        st.rerun()

    # Always use the saved salary for calculations.
    monthly_income = get_saved_salary(user_id)

    expenses = get_expenses(user_id)
    total_expenses = get_total_expenses(user_id)
    month_expenses = get_monthly_expenses(
        user_id,
        current_month
    )

    remaining_balance = monthly_income - month_expenses

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Monthly Income", money(monthly_income))
    col2.metric("This Month's Expenses", money(month_expenses))
    col3.metric("All-Time Expenses", money(total_expenses))
    col4.metric("Monthly Balance", money(remaining_balance))

    st.divider()

    # -------------------- ADD EXPENSE --------------------

    st.subheader("➕ Add an Expense")

    with st.form("expense_form", clear_on_submit=True):
        description = st.text_input(
            "Expense description",
            placeholder="Example: Jeans, Pizza, Metro"
        )

        amount = st.number_input(
            "Amount (₹)",
            min_value=0.0,
            value=100.0,
            step=10.0
        )

        expense_date = st.date_input(
            "Expense date",
            value=today,
            max_value=today
        )

        submitted = st.form_submit_button(
            "Save Expense",
            use_container_width=True
        )

        if submitted:
            if not description.strip():
                st.error("Please enter an expense description.")
            elif amount <= 0:
                st.error("Amount must be greater than zero.")
            else:
                predicted_category = predict_category(description)

                st.session_state["pending_expense"] = {
                    "description": description.strip(),
                    "amount": float(amount),
                    "date": expense_date.isoformat(),
                    "category": predicted_category,
                    "user_id": user_id,
                }

    # Confirm the predicted category before saving.
    pending = st.session_state.get("pending_expense")

    if pending and pending.get("user_id") == user_id:
        st.info(
            f"AI predicted category: **{pending['category']}**. "
            "Check it before saving."
        )

        categories = [
            "Food",
            "Shopping",
            "Transport",
            "Bills",
            "Healthcare",
            "Entertainment",
            "Travel",
            "Education",
            "Income",
            "Other",
        ]

        if pending["category"] not in categories:
            categories.append(pending["category"])

        default_index = categories.index(pending["category"])

        selected_category = st.selectbox(
            "Confirm or change category",
            options=categories,
            index=default_index,
            key=f"confirmed_category_{user_id}"
        )

        save_col, cancel_col = st.columns(2)

        with save_col:
            if st.button("Confirm and Save", use_container_width=True):
                add_expense(
                    user_id=user_id,
                    description=pending["description"],
                    amount=pending["amount"],
                    category=selected_category,
                    expense_date=pending["date"],
                )

                st.session_state.pop("pending_expense", None)
                st.success("Expense saved successfully.")
                st.rerun()

        with cancel_col:
            if st.button("Cancel", use_container_width=True):
                st.session_state.pop("pending_expense", None)
                st.rerun()

    st.divider()

    # -------------------- EXPENSE HISTORY --------------------

    st.subheader("📋 Expense History")

    expenses = get_expenses(user_id)

    if expenses:
        expense_df = pd.DataFrame(expenses)
        expense_df = expense_df.rename(columns={
            "id": "ID",
            "description": "Description",
            "amount": "Amount (₹)",
            "category": "Category",
            "date": "Date",
        })

        st.dataframe(
            expense_df,
            use_container_width=True,
            hide_index=True
        )

        delete_options = {
            (
                f"ID {row['id']} — {row['description']} "
                f"({money(row['amount'])}, {row['date']})"
            ): row["id"]
            for row in expenses
        }

        selected_expense = st.selectbox(
            "Select an expense to delete",
            options=list(delete_options.keys()),
            key=f"delete_expense_selection_{user_id}"
        )

        if st.button("Delete Selected Expense"):
            deleted = delete_expense(
                user_id,
                delete_options[selected_expense]
            )

            if deleted:
                st.success("Expense deleted.")
            else:
                st.warning("Expense could not be found.")

            st.rerun()
    else:
        st.info("No expenses yet. Add your first expense above.")

    st.divider()

    # -------------------- ANALYTICS --------------------

    st.subheader("📊 Expense Analytics")

    expenses = get_expenses(user_id)

    if expenses:
        df = pd.DataFrame(expenses)
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["amount", "date", "category"])

        if not df.empty:
            pie_col, bar_col = st.columns(2)

            with pie_col:
                st.markdown("#### Spending by Category")

                category_totals = (
                    df.groupby("category", as_index=False)["amount"]
                    .sum()
                    .sort_values("amount", ascending=False)
                )

                pie_fig = px.pie(
                    category_totals,
                    names="category",
                    values="amount",
                    hole=0.35,
                    title="Expense Distribution"
                )

                st.plotly_chart(
                    pie_fig,
                    use_container_width=True
                )

            

            # Simple insight based on recorded categories.
            st.markdown("#### 🤖 Spending Insight")

            highest_category = category_totals.iloc[0]

            st.write(
                f"Your highest recorded spending category is "
                f"**{highest_category['category']}**, at "
                f"**{money(highest_category['amount'])}**."
            )

            st.caption(
                "AI predicts expense categories. The charts and this "
                "insight summarize the stored expense data; they are "
                "not generated by a separate AI model."
            )
    else:
        st.info("Add expenses to see your pie chart and monthly bar chart.")

    st.divider()

    st.caption(
        "FinTrack | Local SQLite database | TF-IDF + LinearSVC "
        "expense categorization"
    )


# -------------------- MAIN --------------------

def main():
    if "user" not in st.session_state:
        show_authentication()
    else:
        show_dashboard(st.session_state["user"])


if __name__ == "__main__":
    main()
