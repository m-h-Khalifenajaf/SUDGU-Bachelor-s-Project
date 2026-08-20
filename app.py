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
    font-family: 'Vazirmatn', Tahoma, Arial, sans-serif !important;
}

.stApp { direction: rtl; }
div, span, label, input, th, td { text-align: right !important; }
input { direction: rtl !important; }
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
[data-testid="stAppDeployButton"] { display: none !important; }
[data-testid="stSidebar"] { overflow-x: hidden !important; }

[data-testid="stDataFrame"] { direction: ltr !important; }

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
# ۱. تنظیمات دیتابیس و توابع کمکی
# ==========================================
conn = sqlite3.connect('users.db', check_same_thread=False, timeout=15)
c = conn.cursor()

def create_tables():
    c.execute('CREATE TABLE IF NOT EXISTS users(username TEXT, password TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS deposits(username TEXT, deposit_name TEXT, principal REAL, rate REAL, start_date TEXT, end_date TEXT, interest_type TEXT)')
    
    try:
        c.execute('ALTER TABLE deposits ADD COLUMN pay_day INTEGER DEFAULT 1')
    except sqlite3.OperationalError:
        pass 
        
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

def format_date_display(date_str):
    if not date_str: return ""
    clean_date = str(date_str).replace("-", "/")
    return f"\u200E{clean_date}\u200E"

def is_pay_day(date_obj, p_day):
    if date_obj.day == p_day:
        return True
    tomorrow = date_obj + timedelta(days=1)
    if tomorrow.day == 1 and p_day > date_obj.day:
        return True
    return False

# ==============================================================
# موتور مرکزی شبیه‌سازی بانکی 
# ==============================================================
def simulate_account(principal, rate, start_date, interest_type, pay_day, txs, calc_date=None):
    if not txs:
        last_tx_date = start_date
    else:
        sorted_txs = sorted(txs, key=lambda x: x["تاریخ"].replace("-", "/"))
        last_tx_date_str = sorted_txs[-1]["تاریخ"].replace("-", "/")
        last_tx_date = parse_shamsi_date(last_tx_date_str)
        if not last_tx_date: last_tx_date = start_date
        
    end_date = calc_date if calc_date else last_tx_date
    if end_date < start_date:
        end_date = start_date

    total_days = (end_date - start_date).days
    daily_rate = rate / 36500.0

    current_balance = float(principal)
    total_paid_profit = 0.0
    accumulated_profit = 0.0
    
    monthly_min_so_far = current_balance
    month_days_count = 0

    for i in range(total_days + 1):
        current_date = start_date + timedelta(days=i)
        current_date_str = str(current_date).replace("-", "/")

        if is_pay_day(current_date, pay_day) and i != 0:
            if interest_type == "روزشمار":
                current_balance += accumulated_profit
                total_paid_profit += accumulated_profit
                accumulated_profit = 0.0
            elif interest_type == "ماه‌شمار":
                profit = monthly_min_so_far * daily_rate * month_days_count
                current_balance += profit
                total_paid_profit += profit
                monthly_min_so_far = current_balance
                month_days_count = 0

        today_txs = [t for t in txs if t["تاریخ"].replace("-", "/") == current_date_str]
        today_txs.sort(key=lambda x: 0 if x["نوع"] == "واریز" else 1)

        running_min = current_balance
        for tx in today_txs:
            if tx["نوع"] == "واریز":
                current_balance += float(tx["مبلغ"])
            else:
                current_balance -= float(tx["مبلغ"])
            
            if current_balance < running_min:
                running_min = current_balance

        if current_balance < 0:
            return False, 0, 0, 0, 0

        if interest_type == "روزشمار":
            accumulated_profit += running_min * daily_rate
        elif interest_type == "ماه‌شمار":
            if month_days_count == 0:
                monthly_min_so_far = running_min
            elif running_min < monthly_min_so_far:
                monthly_min_so_far = running_min
            month_days_count += 1

    pending_profit = 0.0
    if interest_type == "روزشمار":
        pending_profit = accumulated_profit
    elif interest_type == "ماه‌شمار":
        pending_profit = monthly_min_so_far * daily_rate * month_days_count
    
    valid_txs_net = sum([float(t["مبلغ"]) if t["نوع"] == "واریز" else -float(t["مبلغ"]) for t in txs if t["تاریخ"].replace("-", "/") <= str(end_date).replace("-", "/")])
    pure_principal = float(principal) + valid_txs_net

    return True, pure_principal, total_paid_profit, pending_profit, current_balance


# ==========================================
# ۲. مدیریت حافظه موقت (Session State)
# ==========================================
for key in ['logged_in', 'username']:
    if key not in st.session_state:
        st.session_state[key] = False if key == 'logged_in' else ""

if 'auth_mode' not in st.session_state: st.session_state.auth_mode = 'login'
if 'active_tab' not in st.session_state: st.session_state.active_tab = "➕ ایجاد سپرده جدید"

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
                clean_user, clean_pass = new_user.strip(), new_password.strip()
                if not clean_user or not clean_pass:
                    st.warning("لطفاً نام کاربری و رمز عبور معتبر وارد کنید.")
                else:
                    c.execute('SELECT * FROM users WHERE username =?', (clean_user,))
                    if c.fetchone():
                        st.error("این نام کاربری وجود دارد!")
                    else:
                        c.execute('INSERT INTO users(username, password) VALUES (?,?)', (clean_user, hash_password(clean_pass)))
                        conn.commit()
                        st.success("حساب ساخته شد! وارد شوید.")
                        st.session_state.auth_mode = 'login'
                        st.rerun()
            st.write("---")
            if st.button("ورود به حساب کاربری", type="secondary"):
                st.session_state.auth_mode = 'login'
                st.rerun()

        elif st.session_state.auth_mode == 'login':
            st.subheader("ورود به سامانه")
            username = st.text_input("نام کاربری")
            password = st.text_input("رمز عبور", type='password')
            if st.button("ورود", use_container_width=True, type="primary"):
                clean_user, clean_pass = username.strip(), password.strip()
                c.execute('SELECT * FROM users WHERE username =? AND password = ?', (clean_user, hash_password(clean_pass)))
                if c.fetchone():
                    st.session_state.logged_in = True
                    st.session_state.username = clean_user
                    st.session_state.active_tab = "➕ ایجاد سپرده جدید"
                    st.rerun()
                else:
                    st.error("نام کاربری یا رمز عبور اشتباه است.")
            st.write("---")
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

    c.execute('SELECT deposit_name, principal, rate, start_date, interest_type, pay_day FROM deposits WHERE username = ?', (st.session_state.username,))
    all_deposits = c.fetchall()
    deposit_names = [row[0] for row in all_deposits]
    
    options = ["➕ ایجاد سپرده جدید"] + deposit_names
    if st.session_state.active_tab not in options:
        st.session_state.active_tab = "➕ ایجاد سپرده جدید"
    
    st.sidebar.subheader("🗂️ لیست سپرده‌ها")
    
    current_index = options.index(st.session_state.active_tab)
    selected_option = st.sidebar.radio("", options, index=current_index, label_visibility="collapsed")
    
    if selected_option != st.session_state.active_tab:
        st.session_state.active_tab = selected_option
        st.rerun()

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
            new_start_date = st.text_input("تاریخ افتتاح حساب (مثال: 1403/01/01)", value=str(jdatetime.date.today()).replace("-", "/"))
            new_pay_day = st.number_input("روز واریز سود (در ماه):", min_value=1, max_value=31, value=1)
            
        if st.button("✅ ذخیره سپرده جدید"):
            clean_dep_name = new_dep_name.strip()
            valid_start = parse_shamsi_date(new_start_date)
            
            if clean_dep_name == "": st.error("لطفاً یک نام برای سپرده انتخاب کنید.")
            elif clean_dep_name in deposit_names: st.error("سپرده‌ای با این نام قبلاً ساخته‌اید!")
            elif not valid_start: st.error("فرمت تاریخ اشتباه است.")
            else:
                c.execute('INSERT INTO deposits(username, deposit_name, principal, rate, start_date, end_date, interest_type, pay_day) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', 
                          (st.session_state.username, clean_dep_name, new_principal, new_rate, str(valid_start), "", new_interest_type, new_pay_day))
                conn.commit()
                st.session_state.active_tab = clean_dep_name
                st.rerun()

    else:
        current_dep = next(d for d in all_deposits if d[0] == selected_option)
        dep_name, principal, rate, start_date_str, interest_type, pay_day = current_dep[0], current_dep[1], current_dep[2], current_dep[3], current_dep[4], current_dep[5]
        start_date = parse_shamsi_date(start_date_str)

        disp_start = format_date_display(start_date_str)

        st.title(f"سپرده: {dep_name} 📊")
        st.info(f"مبلغ اولیه: **{principal:,.0f}** ریال | نرخ سود: **{rate}** درصد ({interest_type}) | تاریخ افتتاح: **{disp_start}** | روز واریز سود: **{pay_day}ام هر ماه**")
        
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
                    edit_pay_day = st.number_input("روز واریز سود:", min_value=1, max_value=31, value=int(pay_day), key="ep_pay_day")
                with e2:
                    edit_rate = st.number_input("نرخ سود (درصد):", min_value=0.0, value=float(rate), step=0.5, key="ep_rate")
                    edit_int_type = st.selectbox("نوع سود:", ["روزشمار", "ماه‌شمار"], index=0 if interest_type=="روزشمار" else 1, key="ep_type")
                with e3:
                    edit_start = st.text_input("تاریخ افتتاح حساب:", value=start_date_str.replace("-", "/"), key="ep_start")
                
                if st.button("💾 ذخیره تغییرات سپرده", use_container_width=True):
                    valid_start = parse_shamsi_date(edit_start)
                    if not valid_start:
                        st.error("فرمت تاریخ اشتباه است.")
                    else:
                        is_valid = True
                        for t in transactions:
                            if parse_shamsi_date(t['تاریخ']) < valid_start:
                                st.error(f"تراکنشِ {t['تاریخ'].replace('-', '/')} قبل از تاریخ افتتاحِ جدید قرار می‌گیرد! امکان ویرایش وجود ندارد.")
                                is_valid = False; break
                        
                        if is_valid:
                            is_bal_valid, _, _, _, _ = simulate_account(edit_principal, edit_rate, valid_start, edit_int_type, edit_pay_day, transactions)
                            if not is_bal_valid:
                                st.error("کاهش مبلغ، باعث منفی شدنِ «موجودی قابل برداشت» می‌شود! (سودهای واریز نشده قابل برداشت نیستند).")
                                is_valid = False
                                
                        if is_valid:
                            c.execute('UPDATE deposits SET principal=?, rate=?, start_date=?, interest_type=?, pay_day=? WHERE username=? AND deposit_name=?', 
                                      (edit_principal, edit_rate, str(valid_start), edit_int_type, edit_pay_day, st.session_state.username, dep_name))
                            conn.commit()
                            st.success("بروزرسانی شد.")
                            st.rerun()

        with col_del:
            with st.expander("❌ حذف کامل این سپرده"):
                st.warning("⚠️ آیا از حذف این سپرده مطمئن هستید؟")
                if st.button("بله، مطمئنم. حذف کن!", type="primary"):
                    c.execute('DELETE FROM deposits WHERE username = ? AND deposit_name = ?', (st.session_state.username, dep_name))
                    c.execute('DELETE FROM transactions_multi WHERE username = ? AND deposit_name = ?', (st.session_state.username, dep_name))
                    conn.commit()
                    st.session_state.active_tab = "➕ ایجاد سپرده جدید"
                    st.rerun()

        st.divider()
        
        if not start_date:
            st.error("خطا در تاریخ افتتاح این سپرده.")
        else:
            st.subheader("➕ ثبت تراکنش جدید")
            st.caption("⚠️ **نکته:** در صورتی که چند تراکنش در یک روز تقویمی دارید، لطفاً آن‌ها را دقیقاً به ترتیبِ وقوع وارد کنید.")
            
            c1, c2, c3, c4 = st.columns([1.5, 1.5, 2, 1])
            with c1: tx_date_str = st.text_input("تاریخ تراکنش:", value=start_date_str.replace("-", "/"))
            with c2: tx_type = st.selectbox("نوع تراکنش", ["واریز", "برداشت"])
            with c3:
                tx_amount = st.number_input("مبلغ تراکنش (ریال):", min_value=0, value=10000000, step=5000000, format="%d")
                st.markdown(f"<div class='amount-format'>معادل: {tx_amount / 10:,.0f} تومان</div>", unsafe_allow_html=True)
            with c4:
                st.write(""); st.write("")
                if st.button("➕ افزودن"):
                    tx_date = parse_shamsi_date(tx_date_str)
                    if not tx_date: st.error("فرمت تاریخ اشتباه است.")
                    elif tx_date < start_date: st.error("تاریخ تراکنش نمی‌تواند قبل از افتتاح حساب باشد!")
                    else:
                        temp_txs = transactions.copy()
                        temp_txs.append({"تاریخ": str(tx_date).replace("-", "/"), "نوع": tx_type, "مبلغ": tx_amount})
                        
                        is_valid, _, _, _, _ = simulate_account(principal, rate, start_date, interest_type, pay_day, temp_txs)
                        
                        if not is_valid: 
                            st.error("موجودی قطعی و قابل برداشت شما کافی نیست! (دقت کنید سودهای ماه‌های اخیر تا زمان رسیدنِ «روز واریز»، به موجودی اضافه نمی‌شوند).")
                        else:
                            c.execute('INSERT INTO transactions_multi(username, deposit_name, tx_date, type, amount) VALUES (?, ?, ?, ?, ?)', 
                                      (st.session_state.username, dep_name, str(tx_date), tx_type, tx_amount))
                            conn.commit()
                            st.success("ثبت شد!")
                            st.rerun()

            if len(transactions) > 0:
                st.divider()
                st.subheader("📋 لیست تراکنش‌های ثبت شده")
                st.info("💡 **راهنمای استفاده:** برای ویرایش، روی سلول‌ها دوبار کلیک کنید. برای حذف یک ردیف، با رفتنِ موس روی ستون ردیف‌ها تیکِ کنار آن را بزنید و آیکون سطل زباله (🗑️) را از گوشه بالا کلیک کنید.")
                
                df_for_editor = pd.DataFrame({
                    "مبلغ (ریال)": [int(t["مبلغ"]) for t in transactions],
                    "نوع": [t["نوع"] for t in transactions],
                    "تاریخ": [t["تاریخ"].replace("-", "/") for t in transactions],
                    "ردیف": [i + 1 for i in range(len(transactions))]
                })
                
                edited_df = st.data_editor(
                    df_for_editor,
                    num_rows="dynamic",
                    use_container_width=True,
                    hide_index=True,
                    column_order=("مبلغ (ریال)", "نوع", "تاریخ", "ردیف"),
                    column_config={
                        "ردیف": st.column_config.NumberColumn("ردیف", disabled=True),
                        "تاریخ": st.column_config.TextColumn("تاریخ", required=True),
                        "نوع": st.column_config.SelectboxColumn("نوع", options=["واریز", "برداشت"], required=True),
                        "مبلغ (ریال)": st.column_config.NumberColumn("مبلغ (ریال)", min_value=0, step=500000, format="%,d", required=True)
                    }
                )
                
                if st.button("💾 ذخیره تغییرات", type="primary", use_container_width=True):
                    is_valid = True
                    temp_txs = []
                    
                    for index, row in edited_df.iterrows():
                        v_date_str = str(row["تاریخ"]).strip()
                        v_type = str(row["نوع"]).strip()
                        
                        if pd.isna(row["مبلغ (ریال)"]):
                            st.error("خطا: مبلغ نمی‌تواند خالی باشد!")
                            is_valid = False; break
                            
                        v_amount = float(row["مبلغ (ریال)"])
                        v_date = parse_shamsi_date(v_date_str)
                        
                        if not v_date:
                            st.error(f"فرمت تاریخ در یکی از ردیف‌ها اشتباه است: {v_date_str}")
                            is_valid = False; break
                        elif v_date < start_date:
                            st.error(f"تاریخ {v_date_str} قبل از افتتاح حساب است!")
                            is_valid = False; break
                            
                        temp_txs.append({"تاریخ": str(v_date).replace("-", "/"), "نوع": v_type, "مبلغ": v_amount})
                        
                    if is_valid:
                        is_bal_valid, _, _, _, _ = simulate_account(principal, rate, start_date, interest_type, pay_day, temp_txs)
                        if not is_bal_valid:
                            st.error("تغییرات باعث منفی شدن «موجودی قابل برداشت» می‌شود! (سودهای در جریان و واریز نشده قابل برداشت نیستند).")
                            is_valid = False
                                
                    if is_valid:
                        c.execute('DELETE FROM transactions_multi WHERE username = ? AND deposit_name = ?', (st.session_state.username, dep_name))
                        for t in temp_txs:
                            c.execute('INSERT INTO transactions_multi(username, deposit_name, tx_date, type, amount) VALUES (?, ?, ?, ?, ?)', 
                                      (st.session_state.username, dep_name, t["تاریخ"].replace("/", "-"), t["نوع"], t["مبلغ"]))
                        conn.commit()
                        st.success("✅ تغییرات جدول با موفقیت در دیتابیس ذخیره شد!")
                        st.rerun()
                
                df_download = edited_df.drop(columns=["ردیف"])
                df_download["معادل (تومان)"] = df_download["مبلغ (ریال)"] / 10
                df_download = df_download[["تاریخ", "نوع", "مبلغ (ریال)", "معادل (تومان)"]]
                csv = df_download.to_csv(index=False).encode('utf-8-sig')
                
                st.download_button("📥 دانلود فایل اکسل تراکنش‌ها", data=csv, file_name=f'{dep_name}_Report.csv', mime='text/csv')

            st.divider()

            # ==========================================
            # بخش پویای محاسبه سود (نمایش تفکیک شده و حرفه‌ای)
            # ==========================================
            st.subheader("🧮 شبیه‌سازی و محاسبه سود")
            
            calc_col1, calc_col2, calc_col3 = st.columns([1.5, 1.5, 3])
            with calc_col1:
                today_shamsi = str(jdatetime.date.today()).replace("-", "/")
                calc_date_str = st.text_input("محاسبه وضعیت حساب تا تاریخ:", value=today_shamsi)
            
            with calc_col2:
                st.write("") 
                st.write("")
                calc_btn = st.button("🚀 استعلام و محاسبه نهایی", use_container_width=True)
            
            if calc_btn:
                calc_date = parse_shamsi_date(calc_date_str)
                
                if not calc_date:
                    st.error("فرمت تاریخ اشتباه است.")
                elif calc_date < start_date:
                    st.error("تاریخ محاسبه نمی‌تواند قبل از افتتاح حساب باشد!")
                else:
                    valid_txs = [tx for tx in transactions if tx["تاریخ"].replace("-", "/") <= str(calc_date).replace("-", "/")]
                    
                    is_valid, final_principal, paid_profit, pending_profit, available_balance = simulate_account(
                        principal, rate, start_date, interest_type, pay_day, valid_txs, calc_date
                    )
                    
                    disp_calc = format_date_display(str(calc_date))
                    
                    res_col1, res_col2 = st.columns([2, 1])
                    with res_col1:
                        st.info(f"💼 **اصل پول (مجموع واریز و برداشت‌ها بدون سود):** {final_principal:,.0f} ریال (معادل {final_principal / 10:,.0f} تومان)")
                        
                        st.success(f"✅ **مجموع سودهای واریز شده و قطعی ({interest_type}):** {paid_profit:,.0f} ریال (معادل {paid_profit / 10:,.0f} تومان)")
                        
                        st.markdown(f"""
                        <div style="background-color: #2E86C1; padding: 15px; border-radius: 8px; margin-top: 15px; margin-bottom: 15px;">
                            <h5 style="color: white; margin:0;">💰 موجودی نهایی و قابل برداشت در تاریخ {disp_calc} :</h5>
                            <h4 style="color: #F1C40F; margin: 10px 0 0 0;">{available_balance:,.0f} ریال (معادل {available_balance / 10:,.0f} تومان)</h4>
                        </div>
                        """, unsafe_allow_html=True)

    st.sidebar.divider()
    if st.sidebar.button("🚪 خروج از حساب", use_container_width=True):
        st.session_state.logged_in, st.session_state.username = False, ""
        st.session_state.active_tab = "➕ ایجاد سپرده جدید"
        st.rerun()
