import streamlit as st
import pandas as pd
import urllib.parse
import re
import io
from openpyxl import Workbook
from datetime import datetime

st.title("レポートファイル変換アプリ（report1～4対応）")

uploaded_files = st.file_uploader("CSVファイルをアップロード（複数可）", type="csv", accept_multiple_files=True)

def decode_url_and_extract(df, col_name):
    decoded = df[col_name].fillna("").apply(lambda x: urllib.parse.unquote(str(x)))
    category = decoded.str.extract(r'[?&]category=([^&]+)')
    keyword = decoded.str.extract(r'[?&]keyword=([^&]+)')
    return decoded, category[0], keyword[0]

def clean_title_column(df, title_col="ページ タイトルとスクリーン クラス"):
    df[title_col] = df[title_col].str.replace(r"\|\s*Q\.ENEST（キューエネス）でんき", "", regex=True)
    return df

def extract_report_type(filename):
    match = re.match(r"report(\d)_", filename)
    return f"report{match.group(1)}" if match else "unknown"

def process_report(file, report_type):
    df = pd.read_csv(file, header=6)
    sheet_dict = {}

    if report_type == "report2":
        # 詳細ページ
        detail_df = df.copy()
        detail_df = clean_title_column(detail_df)
        sheet_dict["詳細ページ"] = detail_df

        # カテゴリページ・キーワードページ
        decoded, category, keyword = decode_url_and_extract(df, "ページパス + クエリ文字列")
        category_df = df.copy()
        keyword_df = df.copy()

        category_df.insert(2, "カテゴリ", category)
        keyword_df.insert(2, "キーワード", keyword)

        category_df["ページパス + クエリ文字列"] = decoded
        keyword_df["ページパス + クエリ文字列"] = decoded

        sheet_dict["カテゴリページ"] = category_df
        sheet_dict["キーワードページ"] = keyword_df

    elif report_type == "report4":
        # 特定URLフィルタ処理
        df = clean_title_column(df)
        filtered_df = df[df["ページの参照元 URL"].fillna("").str.startswith("https://www.qenest-denki.com/lowv/faq/")].copy()
        if not filtered_df.empty:
            decoded, category, keyword = decode_url_and_extract(filtered_df, "ページの参照元 URL")
            filtered_df.insert(3, "カテゴリ", category)
            filtered_df.insert(4, "キーワード", keyword)
            filtered_df["ページの参照元 URL"] = decoded
            sheet_dict["faqページ"] = filtered_df
        else:
            st.warning(f"{file.name} には条件を満たす行が存在しません")

    else:
        # デフォルト処理（report1など）
        df = clean_title_column(df)
        decoded, category, keyword = decode_url_and_extract(df, "ページパス + クエリ文字列")

        df["ページパス + クエリ文字列"] = decoded

        detail_df = df.copy()
        detail_df.insert(2, "カテゴリ", category)
        detail_df.insert(3, "キーワード", keyword)

        category_df = detail_df.copy()
        keyword_df = detail_df.copy()

        sheet_dict["詳細ページ"] = detail_df
        sheet_dict["カテゴリページ"] = category_df
        sheet_dict["キーワードページ"] = keyword_df

    return sheet_dict

if uploaded_files:
    for file in uploaded_files:
        report_type = extract_report_type(file.name)
        sheets = process_report(file, report_type)

        # Excel出力
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            for name, df in sheets.items():
                df.to_excel(writer, sheet_name=name[:31], index=False)

        st.download_button(
            label=f"{file.name} の変換済みファイルをダウンロード",
            data=output.getvalue(),
            file_name=f"{file.name.replace('.csv', '')}_converted.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
