import streamlit as st
import sqlite3
import hashlib
import jdatetime 
from datetime import timedelta
import pandas as pd

# ==========================================
# تنظیمات صفحه
# ==========================================
st.set_page_config(page_title="سودگو (SUDGU)", page_icon="🏦", layout="wide")

# ==========================================
# ۰. تزریق CSS
# ==========================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@100;300;400;700;900&display=swap');

html, body, div, p, h1, h2, h3, h4, h5, h6, label, input, button, table, th, td, a {
    font-family: 'Vazirmatn', sans-serif !important;
}

.stIcon, .material-symbols-rounded, [data-baseweb="icon"], svg {
    font-family: 'Material Symbols Rounded' !important;
    direction: ltr !important;
}

.stApp {
    direction: rtl;
}

div, span, label, input, th, td {
    text-align: right !important;
}

input {
    direction: rtl !important;
}

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

[data-testid="stAppDeployButton"] {
    display: none !important;
}

[data-testid="stSidebar"] {
    overflow-x: hidden !important;
}
[data-testid="stSidebar"][aria-expanded="false"] .stSidebarContent {
    display: none !important;
}

.amount-format {
    color: #2E86C1;
    font-weight: bold;
    font-size: 14px;
    margin-top: -10px;
    margin-bottom: 15px;
}

.edit-amount-format {
    color: #2E86C1;
    font-size: 12px;
    margin-top: 5px;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# ۱. تنظیمات دیتابیس
# ==========================================
conn = sqlite3.connect('users.db', check_same_thread=False)
c = conn.cursor()

def create_tables():
    c.execute('CREATE TABLE IF NOT EXISTS users(username TEXT, password TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS deposits(username TEXT, deposit_name TEXT, principal REAL, rate REAL, start_date TEXT, end_date TEXT, interest_type TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS transactions_multi(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, deposit_name TEXT, tx_date TEXT, type TEXT, amount REAL)')
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
if 'edit_tx_id' not in st.session_state:
    st.session_state.edit_tx_id = None
if 'del_tx_id' not in st.session_state:
    st.session_state.del_tx_id = None
if 'auth_mode' not in st.session_state:
    st.session_state.auth_mode = 'login' 

# ==========================================
# ۳. سیستم ورود و ثبت‌نام
# ==========================================
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<h1 style='text-align: center; color: #2E86C1;'>سودگو (SUDGU) 🏦</h1>", unsafe_allow_html=True)
        st.markdown("<h4 style='text-align: center; color: gray;'>سامانه جامع شبیه‌سازی سود بانکی</h4>", unsafe_allow_html=True)
        st.divider()
        
        create_tables() 
        
        if st.session_state.auth_mode == 'signup':
            st.subheader("ساخت حساب کاربری جدید")
            new_user = st.text_input("نام کاربری")
            new_password = st.text_input("رمز عبور", type='password')
            
            if st.button("ثبت نام", use_container_width=True):
                clean_user = new_user.strip()
                clean_pass = new_password.strip()
                
                if clean_user == "" or clean_pass == "":
                    st.warning("لطفاً نام کاربری و رمز عبور معتبر وارد کنید (استفاده از فاصله خالی مجاز نیست).")
                else:
                    c.execute('SELECT * FROM users WHERE username =?', (clean_user,))
                    if c.fetchone():
                        st.error("این نام کاربری از قبل وجود دارد! نام دیگری انتخاب کنید.")
                    else:
                        c.execute('INSERT INTO users(username, password) VALUES (?,?)', (clean_user, hash_password(clean_pass)))
                        conn.commit()
                        st.success("حساب شما ساخته شد! حالا می‌توانید وارد شوید.")
                        st.session_state.auth_mode = 'login'
                        st.rerun()
            
            st.write("---")
            st.write("قبلاً ثبت نام کرده‌اید؟")
            if st.button("ورود به حساب کاربری", type="secondary"):
                st.session_state.auth_mode = 'login'
                st.rerun()

        elif st.session_state.auth_mode == 'login':
            st.subheader("ورود به سامانه")
            username = st.text_input("نام کاربری")
            password = st.text_input("رمز عبور", type='password')
            
            if st.button("ورود", use_container_width=True, type="primary"):
                clean_user = username.strip()
                clean_pass = password.strip()
                
                c.execute('SELECT * FROM users WHERE username =? AND password = ?', (clean_user, hash_password(clean_pass)))
                if c.fetchone():
                    st.session_state.logged_in = True
                    st.session_state.username = clean_user
                    st.rerun()
                else:
                    st.error("نام کاربری یا رمز عبور اشتباه است.")
            
            st.write("---")
            st.write("حساب کاربری ندارید؟")
            if st.button("ثبت نام در سامانه", type="secondary"):
                st.session_state.auth_mode = 'signup'
                st.rerun()

# ==========================================
# ۴. پنل اصلی (داشبورد)
# ==========================================
if st.session_state.logged_in:
    
    st.sidebar.markdown("<h1 style='text-align: center; color: #2E86C1; margin-bottom: 0;'>سودگو (SUDGU)</h1>", unsafe_allow_html=True)
    st.sidebar.markdown(f"<p style='text-align: center; color: #666;'>خوش آمدید، <b>{st.session_state.username}</b></p>", unsafe_allow_html=True)
    st.sidebar.divider()

    c.execute('SELECT deposit_name, principal, rate, start_date, end_date, interest_type FROM deposits WHERE username = ?', (st.session_state.username,))
    all_deposits = c.fetchall()
    deposit_names = [row[0] for row in all_deposits]
    
    options = ["➕ ایجاد سپرده جدید"] + deposit_names
    
    st.sidebar.subheader("🗂️ لیست سپرده‌ها")
    selected_option = st.sidebar.radio("", options, label_visibility="collapsed")

    # --- ایجاد سپرده جدید ---
    if selected_option == "➕ ایجاد سپرده جدید":
        st.title("ایجاد سپرده جدید 🏦")
        st.divider()
        
        c1, c2, c3 = st.columns(3)
        with c1:
            new_dep_name = st.text_input("عنوان سپرده (مثلاً: حساب سامان)")
            new_principal = st.number_input("مبلغ اولیه (ریال):", min_value=0, value=100000000, step=10000000, format="%d")
            st.markdown(f"<div class='amount-format'>معادل: {new_principal / 10:,.0f} تومان</div>", unsafe_allow_html=True)
            
        with c2:
            new_rate = st.number_input("نرخ سود سالانه (درصد):", min_value=0.0, value=20.0, step=0.5)
            new_interest_type = st.selectbox("نوع محاسبه سود:", ["روزشمار", "ماه‌شمار"])
        with c3:
            new_start_date = st.text_input("تاریخ شروع (مثال: 1403/01/01)", value="1403/01/01")
            new_end_date = st.text_input("تاریخ پایان (مثال: 1403/06/31)", value="1403/06/31")
            
        if st.button("✅ ذخیره سپرده جدید"):
            clean_dep_name = new_dep_name.strip()
            # اعتبارسنجی اولیه تاریخ‌ها قبل از ذخیره در دیتابیس
            valid_start = parse_shamsi_date(new_start_date)
            valid_end = parse_shamsi_date(new_end_date)
            
            if clean_dep_name == "":
                st.error("لطفاً یک نام برای سپرده انتخاب کنید.")
            elif clean_dep_name in deposit_names:
                st.error("سپرده‌ای با این نام قبلاً ساخته‌اید!")
            elif not valid_start or not valid_end:
                st.error("فرمت تاریخ اشتباه است. لطفاً تاریخ را به شکل صحیح (مثال: 1403/01/01) وارد کنید.")
            elif valid_start > valid_end:
                st.error("خطای منطقی: تاریخ شروع نمی‌تواند بزرگتر از تاریخ پایان باشد!")
            else:
                # تبدیل تاریخ به استرینگ استاندارد برای یکپارچگی داده‌ها (YYYY-MM-DD)
                c.execute('INSERT INTO deposits(username, deposit_name, principal, rate, start_date, end_date, interest_type) VALUES (?, ?, ?, ?, ?, ?, ?)', 
                          (st.session_state.username, clean_dep_name, new_principal, new_rate, str(valid_start), str(valid_end), new_interest_type))
                conn.commit()
                st.success("سپرده ایجاد شد!")
                st.rerun()

    # --- مدیریت سپرده فعال ---
    else:
        current_dep = next(d for d in all_deposits if d[0] == selected_option)
        dep_name, principal, rate, start_date_str, end_date_str, interest_type = current_dep[0], current_dep[1], current_dep[2], current_dep[3], current_dep[4], current_dep[5]
        
        start_date = parse_shamsi_date(start_date_str)
        end_date = parse_shamsi_date(end_date_str)

        st.title(f"سپرده: {dep_name} 📊")
        st.info(f"مبلغ اولیه: **{principal:,.0f}** ریال | نرخ سود: **{rate}** درصد ({interest_type}) | از **{start_date_str}** تا **{end_date_str}**")
        
        c.execute('SELECT id, tx_date, type, amount FROM transactions_multi WHERE username = ? AND deposit_name = ? ORDER BY tx_date ASC', (st.session_state.username, dep_name))
        tx_data = c.fetchall()
        transactions = [{"id": row[0], "تاریخ": row[1], "نوع": row[2], "مبلغ": row[3]} for row in tx_data]

        col_edit, col_del = st.columns(2)
        
        with col_edit:
            with st.expander("✏️ ویرایش مشخصات پایه سپرده"):
                e1, e2, e3 = st.columns(3)
                with e1:
                    edit_principal = st.number_input("مبلغ اولیه (ریال):", min_value=0, value=int(principal), step=10000000, format="%d", key="ep_prin")
                    st.markdown(f"<div class='edit-amount-format'>معادل: {edit_principal / 10:,.0f} تومان</div>", unsafe_allow_html=True)
                with e2:
                    edit_rate = st.number_input("نرخ سود (درصد):", min_value=0.0, value=float(rate), step=0.5, key="ep_rate")
                    edit_int_type = st.selectbox("نوع سود:", ["روزشمار", "ماه‌شمار"], index=0 if interest_type=="روزشمار" else 1, key="ep_type")
                with e3:
                    edit_start = st.text_input("تاریخ شروع:", value=start_date_str, key="ep_start")
                    edit_end = st.text_input("تاریخ پایان:", value=end_date_str, key="ep_end")
                
                if st.button("💾 ذخیره تغییرات سپرده", use_container_width=True):
                    valid_start = parse_shamsi_date(edit_start)
                    valid_end = parse_shamsi_date(edit_end)
                    if not valid_start or not valid_end or valid_start > valid_end:
                        st.error("فرمت یا بازه تاریخ اشتباه است.")
                    else:
                        is_valid = True
                        sim_balance = edit_principal
                        
                        for t in transactions:
                            t_date = parse_shamsi_date(t['تاریخ'])
                            if t_date < valid_start or t_date > valid_end:
                                st.error(f"خطا: با این تغییرات، تراکنشِ تاریخ {t['تاریخ']} خارج از بازه زمانی سپرده قرار می‌گیرد!")
                                is_valid = False
                                break
                            
                            if t['نوع'] == "واریز":
                                sim_balance += float(t['مبلغ'])
                            else:
                                sim_balance -= float(t['مبلغ'])
                            
                            if sim_balance < 0:
                                st.error("خطا: کاهش مبلغ اولیه باعث می‌شود موجودی حساب در طول دوره منفی شود!")
                                is_valid = False
                                break
                                
                        if is_valid:
                            # ذخیره تاریخ ویرایش شده با فرمت استاندارد
                            c.execute('UPDATE deposits SET principal=?, rate=?, start_date=?, end_date=?, interest_type=? WHERE username=? AND deposit_name=?', 
                                      (edit_principal, edit_rate, str(valid_start), str(valid_end), edit_int_type, st.session_state.username, dep_name))
                            conn.commit()
                            st.success("مشخصات سپرده با موفقیت بروزرسانی شد.")
                            st.rerun()

        with col_del:
            with st.expander("❌ حذف کامل این سپرده"):
                st.warning("⚠️ آیا از حذف این سپرده و تمامی تراکنش‌های آن مطمئن هستید؟ این عمل غیرقابل بازگشت است.")
                if st.button("بله، مطمئنم. حذف کن!", type="primary"):
                    c.execute('DELETE FROM deposits WHERE username = ? AND deposit_name = ?', (st.session_state.username, dep_name))
                    c.execute('DELETE FROM transactions_multi WHERE username = ? AND deposit_name = ?', (st.session_state.username, dep_name))
                    conn.commit()
                    st.rerun()

        st.divider()
        
        if not start_date or not end_date or start_date > end_date:
            st.error("خطا در تاریخ‌های این سپرده.")
        else:
            total_days = (end_date - start_date).days

            st.subheader("ثبت تراکنش جدید")
            c1, c2, c3, c4 = st.columns([1.5, 1.5, 2, 1])
            with c1:
                tx_date_str = st.text_input("تاریخ تراکنش:", value=start_date_str)
            with c2:
                tx_type = st.selectbox("نوع تراکنش", ["واریز", "برداشت"])
            with c3:
                tx_amount = st.number_input("مبلغ تراکنش (ریال):", min_value=0, value=10000000, step=5000000, format="%d")
                st.markdown(f"<div class='amount-format'>معادل: {tx_amount / 10:,.0f} تومان</div>", unsafe_allow_html=True)
            with c4:
                st.write("") 
                st.write("")
                if st.button("➕ افزودن"):
                    tx_date = parse_shamsi_date(tx_date_str)
                    if not tx_date:
                        st.error("فرمت تاریخ اشتباه است.")
                    elif tx_date < start_date or tx_date > end_date:
                        st.error("تاریخ باید بین تاریخ شروع و پایان سپرده باشد!")
                    else:
                        temp_txs = transactions.copy()
                        temp_txs.append({"تاریخ": str(tx_date), "نوع": tx_type, "مبلغ": tx_amount})
                        temp_txs.sort(key=lambda x: x["تاریخ"])
                        
                        sim_balance = principal
                        is_valid = True
                        for t in temp_txs:
                            if t["نوع"] == "واریز":
                                sim_balance += t["مبلغ"]
                            elif t["نوع"] == "برداشت":
                                sim_balance -= t["مبلغ"]
                            if sim_balance < 0:
                                is_valid = False
                                break
                        
                        if not is_valid:
                            st.error("❌ موجودی کافی نیست! این تراکنش باعث منفی شدن حساب می‌شود.")
                        else:
                            # ذخیره تاریخ تراکنش با فرمت استاندارد
                            c.execute('INSERT INTO transactions_multi(username, deposit_name, tx_date, type, amount) VALUES (?, ?, ?, ?, ?)', 
                                      (st.session_state.username, dep_name, str(tx_date), tx_type, tx_amount))
                            conn.commit()
                            st.success("تراکنش ثبت شد!")
                            st.rerun()

            if len(transactions) > 0:
                st.subheader("📋 لیست تراکنش‌های ثبت شده")
                
                header_cols = st.columns([1, 2, 2, 2, 2])
                header_cols[0].write("**ردیف**")
                header_cols[1].write("**تاریخ**")
                header_cols[2].write("**نوع تراکنش**")
                header_cols[3].write("**مبلغ (ریال)**")
                header_cols[4].write("**عملیات**")
                st.divider()

                for idx, tx in enumerate(transactions):
                    row_cols = st.columns([1, 2, 2, 2, 2])
                    row_cols[0].write(idx + 1)
                    
                    if st.session_state.edit_tx_id == tx['id']:
                        new_date = row_cols[1].text_input("تاریخ", value=tx['تاریخ'], key=f"d_{tx['id']}", label_visibility="collapsed")
                        new_type = row_cols[2].selectbox("نوع", ["واریز", "برداشت"], index=0 if tx['نوع']=="واریز" else 1, key=f"t_{tx['id']}", label_visibility="collapsed")
                        
                        new_amount = row_cols[3].number_input("مبلغ", min_value=0, value=int(tx['مبلغ']), step=5000000, key=f"a_{tx['id']}", label_visibility="collapsed", format="%d")
                        row_cols[3].markdown(f"<div class='edit-amount-format'>({new_amount / 10:,.0f} تومان)</div>", unsafe_allow_html=True)
                        
                        action_cols = row_cols[4].columns(2)
                        if action_cols[0].button("💾", key=f"save_{tx['id']}", help="ذخیره"):
                            valid_date = parse_shamsi_date(new_date)
                            if not valid_date:
                                st.error("فرمت تاریخ اشتباه است.")
                            elif valid_date < start_date or valid_date > end_date:
                                st.error("تاریخ باید در بازه سپرده باشد.")
                            else:
                                temp_txs = [t for t in transactions if t['id'] != tx['id']]
                                temp_txs.append({"تاریخ": str(valid_date), "نوع": new_type, "مبلغ": new_amount})
                                temp_txs.sort(key=lambda x: x["تاریخ"])
                                
                                sim_balance = principal
                                is_valid = True
                                for t in temp_txs:
                                    if t["نوع"] == "واریز":
                                        sim_balance += t["مبلغ"]
                                    elif t["نوع"] == "برداشت":
                                        sim_balance -= t["مبلغ"]
                                    if sim_balance < 0:
                                        is_valid = False
                                        break
                                        
                                if not is_valid:
                                    st.error("تغییرات لغو شد! این ویرایش باعث منفی شدن حساب می‌شود.")
                                else:
                                    # استفاده از فرمت استاندارد هنگام ویرایش
                                    c.execute('UPDATE transactions_multi SET tx_date = ?, type = ?, amount = ? WHERE id = ?', 
                                              (str(valid_date), new_type, new_amount, tx['id']))
                                    conn.commit()
                                    st.session_state.edit_tx_id = None
                                    st.rerun()
                                    
                        if action_cols[1].button("❌", key=f"cancel_{tx['id']}", help="انصراف"):
                            st.session_state.edit_tx_id = None
                            st.rerun()
                            
                    else:
                        row_cols[1].write(tx['تاریخ'])
                        if tx['نوع'] == "واریز":
                            row_cols[2].success("🟢 واریز")
                        else:
                            row_cols[2].error("🔴 برداشت")
                            
                        row_cols[3].write(f"{tx['مبلغ']:,.0f}")
                        
                        action_cols = row_cols[4].columns(2)
                        
                        if st.session_state.del_tx_id == tx['id']:
                            if action_cols[0].button("✔️", key=f"yes_del_{tx['id']}", help="تایید حذف"):
                                c.execute('DELETE FROM transactions_multi WHERE id = ?', (tx['id'],))
                                conn.commit()
                                st.session_state.del_tx_id = None
                                st.rerun()
                            if action_cols[1].button("❌", key=f"no_del_{tx['id']}", help="انصراف"):
                                st.session_state.del_tx_id = None
                                st.rerun()
                        else:
                            if action_cols[0].button("✏️", key=f"edit_{tx['id']}", help="ویرایش"):
                                st.session_state.edit_tx_id = tx['id']
                                st.session_state.del_tx_id = None
                                st.rerun()
                            if action_cols[1].button("🗑️", key=f"del_{tx['id']}", help="حذف"):
                                st.session_state.del_tx_id = tx['id']
                                st.session_state.edit_tx_id = None
                                st.rerun()
                            
                st.divider()
                
                # --- اضافه شدن مجدد دکمه دانلود گزارش اکسل ---
                df = pd.DataFrame([{"تاریخ": t["تاریخ"], "نوع": t["نوع"], "مبلغ (ریال)": t["مبلغ"], "معادل (تومان)": t["مبلغ"]/10} for t in transactions])
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 دانلود فایل اکسل تراکنش‌ها",
                    data=csv,
                    file_name=f'{dep_name}_Report.csv',
                    mime='text/csv',
                )

            st.divider()

            if st.button("🚀 محاسبه نهایی سود"):
                current_balance = principal
                total_profit = 0

                if interest_type == "روزشمار":
                    daily_rate = rate / 36500 
                    for i in range(total_days + 1):
                        current_loop_date = str(start_date + timedelta(days=i))
                        for tx in transactions:
                            if tx["تاریخ"] == current_loop_date:
                                if tx["نوع"] == "واریز":
                                    current_balance += tx["مبلغ"]
                                elif tx["نوع"] == "برداشت":
                                    current_balance -= tx["مبلغ"]
                        total_profit += current_balance * daily_rate

                elif interest_type == "ماه‌شمار":
                    monthly_min = {}
                    month_days_count = {}
                    
                    for i in range(total_days + 1):
                        current_loop_date = start_date + timedelta(days=i)
                        current_loop_date_str = str(current_loop_date)
                        ym_key = current_loop_date_str.rsplit("-", 1)[0] 
                        
                        for tx in transactions:
                            if tx["تاریخ"] == current_loop_date_str:
                                if tx["نوع"] == "واریز":
                                    current_balance += tx["مبلغ"]
                                elif tx["نوع"] == "برداشت":
                                    current_balance -= tx["مبلغ"]

                        if ym_key not in monthly_min:
                            monthly_min[ym_key] = current_balance
                            month_days_count[ym_key] = 0
                        else:
                            if current_balance < monthly_min[ym_key]:
                                monthly_min[ym_key] = current_balance
                        
                        month_days_count[ym_key] += 1
                        
                    for ym_key, min_bal in monthly_min.items():
                        m_profit = min_bal * (rate / 36500) * month_days_count[ym_key]
                        total_profit += m_profit

                final_amount = principal + sum([tx["مبلغ"] if tx["نوع"]=="واریز" else -tx["مبلغ"] for tx in transactions]) + total_profit
                
                st.success(f"مجموع سود تعلق گرفته ({interest_type}): **{total_profit:,.0f}** ریال (معادل **{total_profit / 10:,.0f}** تومان)")
                st.info(f"موجودی نهایی در تاریخ {end_date_str} (همراه با سود): **{final_amount:,.0f}** ریال (معادل **{final_amount / 10:,.0f}** تومان)")

    st.sidebar.divider()
    if st.sidebar.button("🚪 خروج از حساب", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.edit_tx_id = None
        st.session_state.del_tx_id = None
        st.rerun()
