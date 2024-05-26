import streamlit as st
import cv2
from pyzbar.pyzbar import decode
import numpy as np
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io

# SQLiteデータベースの作成とテーブルの作成
conn = sqlite3.connect('barcode_data.db')
c = conn.cursor()

# テーブルに新しいカラムdate2, date3, quantityを追加
# 複数回実行してしまうとエラーになるため、すでにカラムが存在するかチェックします
try:
    c.execute('ALTER TABLE barcode_table ADD COLUMN date2 TEXT')
except sqlite3.OperationalError:
    pass

try:
    c.execute('ALTER TABLE barcode_table ADD COLUMN date3 TEXT')
except sqlite3.OperationalError:
    pass

try:
    c.execute('ALTER TABLE barcode_table ADD COLUMN quantity INTEGER')
except sqlite3.OperationalError:
    pass

# テーブルに新しいカラムremovedを追加
try:
    c.execute('ALTER TABLE barcode_table ADD COLUMN removed INTEGER DEFAULT 0')
except sqlite3.OperationalError:
    pass

conn.commit()

# サイドバーでページを選択
page = st.sidebar.selectbox('ページを選択', [ '画像から読み取り', '登録された商品一覧', '即撤去'])

def calculate_date_difference(date1, days):
    if date1 and days:  # Ensure both date1 and days are provided
        date_format = "%Y-%m-%d"
        d1 = datetime.strptime(date1, date_format)
        delta = timedelta(days=int(days))
        new_date = d1 - delta
        return new_date.strftime(date_format)
    return date1  # Default to returning the original date1 if no valid input

if page == '画像から読み取り':
    st.title('画像＆バーコードを読み取り')

    # 画像アップロードを受け付ける
    uploaded_file = st.file_uploader("画像をアップロードしてください", type=['png', 'jpg', 'jpeg'])

    def read_barcode(image):
        decoded_objects = decode(image)
        for obj in decoded_objects:
            return obj.data.decode("utf-8"), obj.rect
        return None, None

    if uploaded_file is not None:
        file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
        image = cv2.imdecode(file_bytes, 1)

        # バーコードを読み取る
        barcode_data, rect = read_barcode(image)

        if barcode_data:
            # 読み取ったバーコード情報を枠で囲む
            if rect:
                cv2.rectangle(image, (rect.left, rect.top), (rect.left + rect.width, rect.top + rect.height), (255, 0, 0), 2)
            st.image(image, channels="BGR")

            # データベースから読み取ったバーコード情報の取得
            c.execute('SELECT product_name, date, date2, date3, quantity FROM barcode_table WHERE barcode = ?', (barcode_data,))
            row = c.fetchone()

            if row:
                product_name, date, date2, date3, quantity = row
                edited_data = st.text_input("商品の名前を編集", value=product_name)
                entered_date1 = st.date_input("日付1を編集", value=datetime.strptime(date, "%Y-%m-%d"))
                entered_date2 = st.selectbox("日付2（数値）を編集", list(range(1, 101)), index=int(date2)-1)
                entered_quantity = st.selectbox("個数を編集", list(range(1, 31)), index=quantity-1)
                calculated_date3 = calculate_date_difference(entered_date1.strftime("%Y-%m-%d"), entered_date2)

                # データの保存
                if st.button("データを保存"):
                    c.execute('UPDATE barcode_table SET product_name = ?, date = ?, date2 = ?, date3 = ?, quantity = ?, removed = 0 WHERE barcode = ?', 
                              (edited_data, entered_date1.strftime("%Y-%m-%d"), entered_date2, calculated_date3, entered_quantity, barcode_data))
                    conn.commit()
                    st.write("保存されたデータ:", edited_data, entered_date1, entered_date2, calculated_date3, entered_quantity)
                    st.success("データが保存されました。")

            else:
                st.write("このバーコードはデータベースに登録されていません。")
                new_product_name = st.text_input("新しい商品の名前を入力")
                new_date1 = st.date_input("日付1を入力", value=datetime.now())
                new_date2 = st.selectbox("日付2（数値）を入力", list(range(1, 101)), index=0)
                new_quantity = st.selectbox("個数を入力", list(range(1, 31)), index=0)
                calculated_date3 = calculate_date_difference(new_date1.strftime("%Y-%m-%d"), new_date2)

                if st.button("新しいデータを保存"):
                    c.execute('INSERT INTO barcode_table (barcode, product_name, date, date2, date3, quantity, removed) VALUES (?, ?, ?, ?, ?, ?, 0)', 
                              (barcode_data, new_product_name, new_date1.strftime("%Y-%m-%d"), new_date2, calculated_date3, new_quantity))
                    conn.commit()
                    st.write("保存されたデータ:", new_product_name, new_date1, new_date2, calculated_date3, new_quantity)
                    st.success("新しいデータが保存されました。")
        else:
            st.image(image, channels="BGR")
            st.write("バーコードが読み取れませんでした。")

elif page == '登録された商品一覧':
    st.title('登録された商品一覧')

    # データベースから全てのデータを取得し、DataFrameを作成
    c.execute('SELECT * FROM barcode_table')
    rows = c.fetchall()
    df = pd.DataFrame(rows, columns=["バーコード", "商品名", "日付1", "日付2", "日付3", "個数", "撤去済み"])

    df = df.sort_values(by=["日付3"])

    # ページネーション設定
    items_per_page = 10
    total_pages = (len(df) - 1) // items_per_page + 1

    if total_pages > 0:
        page_number = st.sidebar.number_input("ページ", min_value=1, max_value=total_pages, value=1)
    
        # 表示するアイテムの範囲を決定
        start_idx = (page_number - 1) * items_per_page
        end_idx = start_idx + items_per_page

        # テーブルのヘッダー作成
        st.write(f"### データ一覧 - ページ {page_number}/{total_pages}")
        cols = st.columns((3, 4, 1, 2, 1, 2))  # カラムの幅を指定
        headers = ["JANコード", "商品名", "個数", "賞味期限", "K-〇", "販売期限"]
        for col, header in zip(cols, headers):
            col.write(f"**{header}**")

        # 各データ行を表示
        current_time = datetime.now().strftime("%Y-%m-%d")
        for _, row in df.iloc[start_idx:end_idx].iterrows():
            barcode, product_name, date1, date2, date3, quantity, removed = row
            cols = st.columns((3, 4, 1, 2, 1, 2))  # カラムの幅を指〇定

            # 長いバーコードが折り返し表示されないようにする
            with cols[0]:
                st.write(f'<div style="white-space: nowrap;">{barcode}</div>', unsafe_allow_html=True)
            
            # 打消し線の表示
            if removed:
                cols[1].write(f'<div style="text-decoration: line-through;">{product_name}</div>', unsafe_allow_html=True)
                cols[2].write(f'<div style="text-decoration: line-through;">{quantity}</div>', unsafe_allow_html=True)
                cols[3].write(f'<div style="text-decoration: line-through;">{date1}</div>', unsafe_allow_html=True)
                cols[4].write(f'<div style="text-decoration: line-through;">{date2}</div>', unsafe_allow_html=True)
                cols[5].write(f'<div style="text-decoration: line-through;">{date3}</div>', unsafe_allow_html=True)
            else:
                cols[1].write(product_name)
                cols[2].write(quantity)
                cols[3].write(date1)
                cols[4].write(date2)
                cols[5].write(date3)

            # 削除ボタン
            if cols[5].button("削除", key=f"delete_{barcode}"):
                c.execute('DELETE FROM barcode_table WHERE barcode = ?', (barcode,))
                conn.commit()
                st.success(f"バーコード {barcode} のデータが削除されました。")
                st.experimental_rerun()
    else:
        st.write("保存されたデータはありません。")

elif page == '即撤去':
    st.title('即撤去 期限切れ商品')

    st.write("現在の日付:", datetime.now().strftime("%Y-%m-%d"))

    # データベースから全てのデータを取得し、DataFrameを作成
    c.execute('SELECT barcode, product_name, date, date3, quantity, removed FROM barcode_table')
    rows = c.fetchall()
    df = pd.DataFrame(rows, columns=["バーコード", "商品名", "日付1", "日付3", "個数", "撤去済み"])

    current_time = datetime.now()
    filtered_df = df[df['日付3'] <= current_time.strftime("%Y-%m-%d")]

    # ページネーション設定
    items_per_page = 10
    total_pages = (len(filtered_df) - 1) // items_per_page + 1

    if total_pages > 0:
        page_number = st.sidebar.number_input("ページ", min_value=1, max_value=total_pages, value=1)
        
        # テーブルのヘッダー作成
        st.write(f"### 即撤去 期限切れ商品 - ページ {page_number}/{total_pages}")
        cols = st.columns((4, 3, 3, 2, 2, 2))  # カラムの幅を指定
        headers = ["商品名", "賞味期限", "販売期限", "個数", "経過日数", "撤去"]
        for col, header in zip(cols, headers):
            col.write(f"**{header}**")

        # 表示するアイテムの範囲を決定
        start_idx = (page_number - 1) * items_per_page
        end_idx = start_idx + items_per_page

        # 各データ行を表示
        for _, row in filtered_df.iloc[start_idx:end_idx].iterrows():
            barcode, product_name, date1, date3, quantity, removed = row
            cols = st.columns((4, 3, 3, 2, 2, 2))  # カラムの幅を指定

            if removed:
                cols[0].write(f'<div style="text-decoration: line-through;">{product_name}</div>', unsafe_allow_html=True)
                cols[1].write(f'<div style="text-decoration: line-through;">{date1}</div>', unsafe_allow_html=True)
                cols[2].write(f'<div style="text-decoration: line-through;"><span style="color:red; font-weight:bold;">{date3}</span></div>', unsafe_allow_html=True)
                cols[3].write(f'<div style="text-decoration: line-through;">{quantity}</div>', unsafe_allow_html=True)
            else:
                cols[0].write(product_name)
                cols[1].write(date1)
                cols[2].write(f'<span style="color:red; font-weight:bold;">{date3}</sapn>', unsafe_allow_html=True)
                cols[3].write(quantity)

            # 経過日数を計算して赤文字太字で表示
            date_diff = (current_time - datetime.strptime(date3, '%Y-%m-%d')).days
            if date_diff > 0:
                cols[4].write(f'<span style="color:red; font-weight:bold;">{date_diff}日経過</span>', unsafe_allow_html=True)
            else:
                cols[4].write(f'<span style="color:red; font-weight:bold;">{abs(date_diff)}日未満</span>', unsafe_allow_html=True)

            # 撤去ボタン
            if not removed and cols[5].button("撤去", key=f"remove_{barcode}"):
                c.execute('UPDATE barcode_table SET removed = 1 WHERE barcode = ?', (barcode,))
                conn.commit()
                st.experimental_rerun()
    else:
        st.write("撤去すべきデータはありません。")

# データベースとの接続を閉じる
conn.close()
