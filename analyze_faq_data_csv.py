import streamlit as st
import pandas as pd
import urllib.parse
import io

st.title("CSV加工＆Excelダウンロード")

uploaded_file = st.file_uploader("CSVファイルをアップロード", type=["csv"])

if uploaded_file:
    # 文字列として読み込み（全体）
    raw_text = uploaded_file.getvalue().decode("utf-8")
    lines = raw_text.splitlines()

    # 1〜6行目削除（index 0〜5を除外）
    # 7行目をヘッダー（index 6）
    # 8行目（index 7）を削除（除外）
    processed_lines = [lines[6]] + lines[8:]  # 7行目のヘッダー + 9行目以降

    # pandasで読み込み
    df = pd.read_csv(io.StringIO("\n".join(processed_lines)))

    # A列（1列目）のURLデコード
    col_name = df.columns[0]
    df[col_name] = df[col_name].astype(str).apply(urllib.parse.unquote)

    st.write("加工後データプレビュー")
    st.dataframe(df.head())

    # Excelファイル作成
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="加工データ")
    output.seek(0)

    st.download_button(
        label="加工データをExcelでダウンロード",
        data=output,
        file_name="processed_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
