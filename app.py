import streamlit as st
import sqlite3
import hashlib
import jdatetime 
from datetime import timedelta
import pandas as pd

# ==========================================
# ۱. تنظیمات دیتابیس (معماری چند لایه)
# ==========================================
conn = sqlite3.connect('users.db', check_same_thread=False)
c = conn.cursor()

def create_tables():
    c.execute('CREATE TABLE IF NOT EXISTS users(username TEXT, password TEXT)')
    # جدول جدید برای ذخیره مشخصات هر سپرده
    c.execute('CREATE TABLE IF NOT EXISTS deposits(username TEXT, deposit_name TEXT, principal REAL, rate REAL, start_date TEXT, end_date TEXT)')
    # جدول تراکنش‌ها که حالا به نام سپرده هم متصل است
    c.execute('CREATE TABLE IF NOT EXISTS transactions_multi(username TEXT, deposit_name TEXT, tx_date TEXT, type TEXT, amount REAL)')
    conn.commit()

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def parse_shamsi_date(date_str):
    try:
        parts = date_str.replace("-", "/").split("/")
        return jdatetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
    except:
        return None

# ==========================================
# ۲. مدیریت حافظه موقت (Session State)
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ""

st.set_page_config(page_title="سامانه جامع سود بانکی", page_icon="🏦", layout="wide")

# ==========================================
# ۳. سیستم ورود و ثبت‌نام
# ==========================================
if not st.session_state.logged_in:
    st.title("سامانه جامع مدیریت و شبیه‌سازی سود بانکی 👤")
    st.write("وارد حساب خود شوید تا سپرده‌های مختلف خود را مدیریت کنید.")
    st.divider()
    
    create_tables() 
    
    menu = ["ورود به حساب", "ثبت نام"]
    choice = st.sidebar.selectbox("منوی کاربری", menu)
    
    if choice == "ثبت نام":
        st.subheader("ساخت اکانت جدید")
        new_user = st.text_input("نام کاربری")
        new_password = st.text_input("رمز عبور", type='password')
        
        if st.button("ثبت نام"):
            if new_user == "" or new_password == "":
                st.warning("لطفاً تمامی فیلدها را پر کنید.")
            else:
                c.execute('SELECT * FROM users WHERE username =?', (new_user,))
                if c.fetchone():
                    st.error("این نام کاربری از قبل وجود دارد!")
                else:
                    c.execute('INSERT INTO users(username, password) VALUES (?,?)', (new_user, hash_password(new_password)))
                    conn.commit()
                    st.success("اکانت شما ساخته شد! حالا وارد شوید.")

    elif choice == "ورود به حساب":
        st.subheader("ورود به سامانه")
        username = st.text_input("نام کاربری")
        password = st.text_input("رمز عبور", type='password')
        
        if st.button("ورود"):
            c.execute('SELECT * FROM users WHERE username =? AND password = ?', (username, hash_password(password)))
            if c.fetchone():
                st.session_state.logged_in = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("نام کاربری یا رمز عبور اشتباه است.")

# ==========================================
# ۴. پنل اصلی (داشبورد چند سپرده‌ای)
# ==========================================
if st.session_state.logged_in:
    
    # --- منوی کناری: مدیریت سپرده‌ها ---
    st.sidebar.success(f"کاربر فعال: {st.session_state.username}")
    if st.sidebar.button("خروج از حساب"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.rerun()

    st.sidebar.divider()
    st.sidebar.subheader("🗂️ لیست سپرده‌های شما")
    
    # خواندن لیست سپرده‌های این کاربر از دیتابیس
    c.execute('SELECT deposit_name, principal, rate, start_date, end_date FROM deposits WHERE username = ?', (st.session_state.username,))
    all_deposits = c.fetchall()
    deposit_names = [row[0] for row in all_deposits]
    
    # منوی کشویی برای انتخاب سپرده یا ایجاد سپرده جدید
    options = ["➕ ایجاد سپرده جدید"] + deposit_names
    selected_option = st.sidebar.selectbox("سپرده فعال را انتخاب کنید:", options)

    # ==========================================
    # حالت الف: کاربر می‌خواهد سپرده جدید بسازد
    # ==========================================
    if selected_option == "➕ ایجاد سپرده جدید":
        st.title("ایجاد سپرده جدید 🏦")
        st.write("اطلاعات اولیه سپرده خود را وارد کنید.")
        st.divider()
        
        c1, c2 = st.columns(2)
        with c1:
            new_dep_name = st.text_input("عنوان سپرده (مثلاً: حساب سامان)")
            new_principal = st.number_input("مبلغ اولیه (تومان):", min_value=0, value=10000000, step=1000000)
            new_rate = st.number_input("نرخ سود سالانه (درصد):", min_value=0.0, value=20.0, step=0.5)
        with c2:
            new_start_date = st.text_input("تاریخ شروع (مثال: 1403/01/01)", value="1403/01/01")
            new_end_date = st.text_input("تاریخ پایان (مثال: 1403/06/31)", value="1403/06/31")
            
        if st.button("✅ ذخیره سپرده جدید"):
            if new_dep_name == "":
                st.error("لطفاً یک نام برای سپرده انتخاب کنید.")
            elif new_dep_name in deposit_names:
                st.error("سپرده‌ای با این نام قبلاً ساخته‌اید! نام دیگری انتخاب کنید.")
            else:
                c.execute('INSERT INTO deposits(username, deposit_name, principal, rate, start_date, end_date) VALUES (?, ?, ?, ?, ?, ?)', 
                          (st.session_state.username, new_dep_name, new_principal, new_rate, new_start_date, new_end_date))
                conn.commit()
                st.success("سپرده با موفقیت ایجاد شد!")
                st.rerun()

    # ==========================================
    # حالت ب: کاربر یک سپرده از پیش ساخته شده را انتخاب کرده
    # ==========================================
    else:
        # استخراج اطلاعات سپرده انتخاب شده
        current_dep = next(d for d in all_deposits if d[0] == selected_option)
        dep_name, principal, rate, start_date_str, end_date_str = current_dep[0], current_dep[1], current_dep[2], current_dep[3], current_dep[4]
        
        start_date = parse_shamsi_date(start_date_str)
        end_date = parse_shamsi_date(end_date_str)

        st.title(f"مدیریت سپرده: {dep_name} 📊")
        st.info(f"مبلغ اولیه: **{principal:,.0f}** تومان | نرخ سود: **{rate}** درصد | از **{start_date_str}** تا **{end_date_str}**")
        
        # امکان حذف سپرده
        if st.button("❌ حذف این سپرده (و تمام تراکنش‌هایش)"):
            c.execute('DELETE FROM deposits WHERE username = ? AND deposit_name = ?', (st.session_state.username, dep_name))
            c.execute('DELETE FROM transactions_multi WHERE username = ? AND deposit_name = ?', (st.session_state.username, dep_name))
            conn.commit()
            st.rerun()

        st.divider()
        
        if not start_date or not end_date or start_date > end_date:
            st.error("خطا در تاریخ‌های این سپرده. لطفاً آن را حذف و دوباره ایجاد کنید.")
        else:
            total_days = (end_date - start_date).days

            # --- بخش ثبت تراکنش برای این سپرده ---
            st.subheader("ثبت تراکنش جدید")
            c1, c2, c3, c4 = st.columns([1.5, 1.5, 2, 1])
            with c1:
                tx_date_str = st.text_input("تاریخ تراکنش:", value=start_date_str)
            with c2:
                tx_type = st.selectbox("نوع تراکنش", ["واریز", "برداشت"])
            with c3:
                tx_amount = st.number_input("مبلغ تراکنش (تومان):", min_value=0, value=1000000, step=500000)
            with c4:
                st.write("") 
                st.write("")
                if st.button("➕ افزودن تراکنش"):
                    tx_date = parse_shamsi_date(tx_date_str)
                    if not tx_date:
                        st.error("فرمت تاریخ اشتباه است.")
                    elif tx_date < start_date or tx_date > end_date:
                        st.error("تاریخ تراکنش باید بین تاریخ شروع و پایان این سپرده باشد!")
                    else:
                        c.execute('INSERT INTO transactions_multi(username, deposit_name, tx_date, type, amount) VALUES (?, ?, ?, ?, ?)', 
                                  (st.session_state.username, dep_name, str(tx_date), tx_type, tx_amount))
                        conn.commit()
                        st.success("ثبت شد!")
                        st.rerun()

            # --- نمایش تراکنش‌های این سپرده ---
            c.execute('SELECT tx_date, type, amount FROM transactions_multi WHERE username = ? AND deposit_name = ?', (st.session_state.username, dep_name))
            tx_data = c.fetchall()
            transactions = [{"تاریخ": row[0], "نوع": row[1], "مبلغ": row[2]} for row in tx_data]

            if len(transactions) > 0:
                st.write("**لیست تراکنش‌های ثبت شده:**")
                df = pd.DataFrame(transactions)
                st.dataframe(df, use_container_width=True)
                
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 دانلود گزارش این سپرده (Excel)",
                    data=csv,
                    file_name=f'{dep_name}_Report.csv',
                    mime='text/csv',
                )

            st.divider()

            # --- موتور محاسبه نهایی ---
            if st.button("🚀 محاسبه نهایی سود"):
                current_balance = principal
                total_profit = 0
                daily_rate = rate / 36500 

                for i in range(total_days + 1):
                    current_loop_date = str(start_date + timedelta(days=i))
                    
                    for tx in transactions:
                        if tx["تاریخ"] == current_loop_date:
                            if tx["نوع"] == "واریز":
                                current_balance += tx["مبلغ"]
                            elif tx["نوع"] == "برداشت":
                                current_balance -= tx["مبلغ"]
                    
                    if current_balance < 0:
                        current_balance = 0
                        
                    daily_profit = current_balance * daily_rate
                    total_profit += daily_profit

                final_amount = current_balance + total_profit
                
                st.success(f"مجموع سود تعلق گرفته به '{dep_name}': **{total_profit:,.0f}** تومان")
                st.info(f"موجودی نهایی در تاریخ {end_date_str}: **{final_amount:,.0f}** تومان")