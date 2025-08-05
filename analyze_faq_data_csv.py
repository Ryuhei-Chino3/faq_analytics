import streamlit as st
import pandas as pd
import urllib.parse
import re
from io import BytesIO

st.set_page_config(page_title="FAQレポート解析アプリ")
st.title("FAQレポート解析アプリ")

def decode_column(df, col_name):
    if col_name in df.columns:
        df[col_name] = df[col_name].astype(str).apply(lambda x: urllib.parse.unquote(x))
    return df

def extract_query_param(value, param):
    if pd.isna(value) or value == "":
        return ""
    try:
        parsed = urllib.parse.urlparse(value)
        qs = urllib.parse.parse_qs(parsed.query)
        return qs.get(param, [""])[0]
    except:
        return ""

def load_csv_with_header_adjustment(uploaded_file):
    raw = uploaded_file.getvalue().decode("utf-8", errors="ignore")
    lines = raw.splitlines()
    if len(lines) < 7:
        st.error(f"{uploaded_file.name} は行数が少なく読み込めません。")
        return pd.DataFrame()
    header_line = lines[6]
    rest = lines[8:] if len(lines) > 8 else []
    combined = "\n".join([header_line] + rest)
    try:
        df = pd.read_csv(BytesIO(combined.encode("utf-8")), dtype=str)
    except Exception:
        df = pd.read_csv(uploaded_file, skiprows=6, dtype=str)
    return df

def clean_sheet_titles(df, sheet_name):
    # faqページ：A列（ページ タイトルとスクリーン クラス）から "| 個人のお客様" を削除
    if sheet_name == "faqページ":
        col = "ページ タイトルとスクリーン クラス"
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(r'\|\s*個人のお客様', '', regex=True)
    # 詳細ページ2 / カテゴリ2 / キーワード2：A列（ページ タイトルとスクリーン クラス）から "｜Q.ENEST（キューエネス）でんき" を削除
    if sheet_name in ["詳細ページ2", "カテゴリ2", "キーワード2"]:
        col = "ページ タイトルとスクリーン クラス"
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('｜Q.ENEST（キューエネス）でんき', '', regex=False)
    # 詳細ページ1 / カテゴリ1 / キーワード1：B列（ページ タイトルとスクリーン クラス）から "｜Q.ENEST（キューエネス）でんき" を削除
    if sheet_name in ["詳細ページ1", "カテゴリ1", "キーワード1"]:
        col = "ページ タイトルとスクリーン クラス"
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('｜Q.ENEST（キューエネス）でんき', '', regex=False)
    return df

def process_report(file, report_type):
    df = load_csv_with_header_adjustment(file)
    if df.empty:
        return {}

    sheets = {}
    faq_pattern = re.compile(r'^/lowv/faq/\d+-\d+$')

    if report_type == "report1":
        # 共通：ページパス + クエリ文字列 をデコード
        if "ページパス + クエリ文字列" in df.columns:
            df = decode_column(df, "ページパス + クエリ文字列")

        # 詳細ページ1：/lowv/faq/X-X だけ
        if "ページパス + クエリ文字列" in df.columns:
            detail_df = df[df["ページパス + クエリ文字列"].astype(str).str.match(faq_pattern, na=False)].copy()
            # カテゴリ/キーワード列を追加（detailのみ）
            detail_df["カテゴリ"] = detail_df["ページパス + クエリ文字列"].apply(lambda u: extract_query_param(u, "category"))
            detail_df["キーワード"] = detail_df["ページパス + クエリ文字列"].apply(lambda u: extract_query_param(u, "keyword"))
            detail_df = clean_sheet_titles(detail_df, "詳細ページ1")
            sheets["詳細ページ1"] = detail_df

            # カテゴリ1：元の全体（faq-pattern ではなく、カテゴリパラメータを持つ行全体）から
            if "ページパス + クエリ文字列" in df.columns:
                cat_base = df.copy()
                cat_base = decode_column(cat_base, "ページパス + クエリ文字列")
                cat_base["カテゴリ"] = cat_base["ページパス + クエリ文字列"].apply(lambda u: extract_query_param(u, "category"))
                cat_base["キーワード"] = cat_base["ページパス + クエリ文字列"].apply(lambda u: extract_query_param(u, "keyword"))
                cat_df = cat_base[cat_base["カテゴリ"].astype(str) != ""].copy()
                cat_df = clean_sheet_titles(cat_df, "カテゴリ1")
                sheets["カテゴリ1"] = cat_df

                # キーワード1
                kw_df = cat_base[cat_base["キーワード"].astype(str) != ""].copy()
                kw_df = clean_sheet_titles(kw_df, "キーワード1")
                sheets["キーワード1"] = kw_df

    elif report_type == "report2":
        # B列（ページパス + クエリ文字列）をデコード
        if "ページパス + クエリ文字列" in df.columns:
            df = decode_column(df, "ページパス + クエリ文字列")
        # C列「ページの参照元 URL」もあればデコード（すべてのシートに反映）
        if "ページの参照元 URL" in df.columns:
            df = decode_column(df, "ページの参照元 URL")

        # 詳細ページ2：/lowv/faq/X-X のみ（カテゴリ/キーワードなし）
        if "ページパス + クエリ文字列" in df.columns:
            detail_df = df[df["ページパス + クエリ文字列"].astype(str).str.match(faq_pattern, na=False)].copy()
            detail_df = clean_sheet_titles(detail_df, "詳細ページ2")
            sheets["詳細ページ2"] = detail_df

            # カテゴリ2：カテゴリパラメータのある行（元の構成を維持）
            tmp_cat = df.copy()
            tmp_cat["カテゴリ"] = tmp_cat["ページパス + クエリ文字列"].apply(lambda u: extract_query_param(u, "category")) if "ページパス + クエリ文字列" in tmp_cat.columns else ""
            tmp_cat["キーワード"] = tmp_cat["ページパス + クエリ文字列"].apply(lambda u: extract_query_param(u, "keyword")) if "ページパス + クエリ文字列" in tmp_cat.columns else ""
            cat_sheet = tmp_cat[tmp_cat["カテゴリ"].astype(str) != ""].copy()
            cat_sheet = clean_sheet_titles(cat_sheet, "カテゴリ2")
            sheets["カテゴリ2"] = cat_sheet

            # キーワード2
            kw_sheet = tmp_cat[tmp_cat["キーワード"].astype(str) != ""].copy()
            kw_sheet = clean_sheet_titles(kw_sheet, "キーワード2")
            sheets["キーワード2"] = kw_sheet

    elif report_type == "report4":
        url_col = "ページの参照元 URL"
        if url_col not in df.columns:
            st.warning(f"{file.name}: '{url_col}' 列がないため report4 の抽出ができません。")
            return {}

        filtered = df[df[url_col].astype(str).str.startswith("https://www.qenest-denki.com/lowv/faq/", na=False)].copy()
        if filtered.empty:
            st.warning(f"{file.name} に該当する faq URL 行がありません。")
            return {}
        filtered = decode_column(filtered, url_col)
        filtered["カテゴリ"] = filtered[url_col].apply(lambda u: extract_query_param(u, "category"))
        filtered["キーワード"] = filtered[url_col].apply(lambda u: extract_query_param(u, "keyword"))
        filtered = clean_sheet_titles(filtered, "faqページ")
        sheets["faqページ"] = filtered

    return sheets

uploaded_files = st.file_uploader("CSVファイルをアップロード（複数可）", type=["csv"], accept_multiple_files=True)

if uploaded_files:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for file in uploaded_files:
            fname = file.name
            lower = fname.lower()
            if lower.startswith("report1"):
                report_type = "report1"
            elif lower.startswith("report2"):
                report_type = "report2"
            elif lower.startswith("report4"):
                report_type = "report4"
            else:
                st.warning(f"{fname} は report1 / report2 / report4 のいずれでもないためスキップします。")
                continue

            sheets = process_report(file, report_type)
            for sheet_name, df in sheets.items():
                safe_name = sheet_name[:31]
                candidate = safe_name
                suffix = 1
                while candidate in writer.sheets:
                    suffix += 1
                    candidate = f"{safe_name}_{suffix}"[:31]
                df.to_excel(writer, sheet_name=candidate, index=False)

    output.seek(0)
    st.download_button(
        label="変換済み Excel をダウンロード",
        data=output.getvalue(),
        file_name="faq解析結果.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
