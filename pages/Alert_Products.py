import streamlit as st
import sqlite3
from datetime import datetime
import pandas as pd

st.title('本日の撤去商品')

# 現在の日付を表示(yyyy/MM/dd) 及び曜日を表示
current_date = datetime.now().strftime("%Y/%m/%d")
current_weekday = datetime.now().strftime("%A")

st.write(f"現在の日付: {current_date} ")

# SQLiteデータベースに接続
conn = sqlite3.connect('barcode_data.db')
c = conn.cursor()

# データベースから全てのデータを取得し、DataFrameを作成
c.execute('SELECT * FROM barcode_table WHERE date3 = ?', (datetime.now().strftime("%Y-%m-%d"),))
rows = c.fetchall()
df = pd.DataFrame(rows, columns=["バーコード", "商品名", "日付1", "日付2", "日付3", "個数", "撤去済み"])

# "撤去済み"カラムを除外
df = df.drop(columns=["撤去済み"])

# データを表示
st.write("### データ一覧")
cols = st.columns((4, 2, 3, 3))  # カラムの幅を指定
headers = ["商品名", "個数", "賞味期限", "販売期限"]
for col, header in zip(cols, headers):
    col.write(f"**{header}**")

for _, row in df.iterrows():
    barcode, product_name, date1, date2, date3, quantity = row
    cols = st.columns((4, 2, 3, 3))  # カラムの幅を指定

    cols[0].write(product_name)
    cols[1].write(quantity)
    cols[2].write(date1)
    cols[3].write(date3)

# データベースとの接続を閉じる
conn.close()
