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
    # faqページ：A列の「| 個人のお客様 | Q.ENEST（キューエネス）でんき」削除
    if sheet_name == "faqページ":
        col = "ページ タイトルとスクリーン クラス"
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(r'\|\s*個人のお客様\s*\|\s*Q\.ENEST（キューエネス）でんき', '', regex=True)
    # 詳細ページ2 / カテゴリ2 / キーワード2：A列の「｜Q.ENEST（キューエネス）でんき」削除
    if sheet_name in ["詳細ページ2", "カテゴリ2", "キーワード2"]:
        col = "ページ タイトルとスクリーン クラス"
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('｜Q.ENEST（キューエネス）でんき', '', regex=False)
    # 詳細ページ1 / カテゴリ1 / キーワード1：B列の「｜Q.ENEST（キューエネス）でんき」削除（B列がタイトル列想定）
    if sheet_name in ["詳細ページ1", "カテゴリ1", "キーワード1"]:
        # B列はインデックス1
        if len(df.columns) > 1:
            col = df.columns[1]
            df[col] = df[col].astype(str).str.replace('｜Q.ENEST（キューエネス）でんき', '', regex=False)
    # カテゴリ1 / キーワード1：B列内の「 | 検索結果 | Q.ENEST（キューエネス）でんき」も削除
    if sheet_name in ["カテゴリ1", "キーワード1"]:
        if len(df.columns) > 1:
            col = df.columns[1]
            df[col] = df[col].astype(str).str.replace(r'\s*\|\s*検索結果\s*\|\s*Q\.ENEST（キューエネス）でんき', '', regex=True)
    # カテゴリ2 / キーワード2：A列内の「 | 検索結果 | Q.ENEST（キューエネス）でんき」削除
    if sheet_name in ["カテゴリ2", "キーワード2"]:
        if len(df.columns) > 0:
            col = df.columns[0]
            df[col] = df[col].astype(str).str.replace(r'\s*\|\s*検索結果\s*\|\s*Q\.ENEST（キューエネス）でんき', '', regex=True)
    return df

def reorder_and_trim_columns(df, sheet_name):
    # Excel列移動/削除指定
    def move_to_front(df, from_idx, new_name_prefix=None):
        if from_idx < len(df.columns):
            col = df.columns[from_idx]
            cols = [col] + [c for c in df.columns if c != col]
            return df[cols]
        return df

    if sheet_name == "詳細ページ1":
        # K,L列（インデックス10,11）を削除
        to_drop = []
        if len(df.columns) > 10:
            to_drop.append(df.columns[10])
        if len(df.columns) > 11:
            to_drop.append(df.columns[11])
        if to_drop:
            df = df.drop(columns=to_drop, errors="ignore")
    elif sheet_name == "カテゴリ1":
        # K列をAへ（idx10）、L列をBへ（idx11）
        cols = list(df.columns)
        new_order = []
        if len(cols) > 10:
            new_order.append(cols[10])  # K -> A
        if len(cols) > 11:
            new_order.append(cols[11])  # L -> B
        # then the rest excluding original K,L
        for c in cols:
            if c not in (cols[10] if len(cols) > 10 else None, cols[11] if len(cols) > 11 else None):
                new_order.append(c)
        df = df.reindex(columns=new_order)
    elif sheet_name == "キーワード1":
        cols = list(df.columns)
        new_order = []
        if len(cols) > 11:
            new_order.append(cols[11])  # L -> A
        if len(cols) > 10:
            new_order.append(cols[10])  # K -> B
        for c in cols:
            if c not in (cols[11] if len(cols) > 11 else None, cols[10] if len(cols) > 10 else None):
                new_order.append(c)
        df = df.reindex(columns=new_order)
    elif sheet_name in ["カテゴリ2", "キーワード2", "faqページ"]:
        cols = list(df.columns)
        new_order = []
        # M (idx12) to A, N (idx13) to B
        if len(cols) > 12:
            new_order.append(cols[12])
        if len(cols) > 13:
            new_order.append(cols[13])
        for c in cols:
            if c not in (cols[12] if len(cols) > 12 else None, cols[13] if len(cols) > 13 else None):
                new_order.append(c)
        df = df.reindex(columns=new_order)
    return df

def process_report(file, report_type):
    df = load_csv_with_header_adjustment(file)
    if df.empty:
        return {}

    sheets = {}
    faq_pattern = re.compile(r'^/lowv/faq/\d+-\d+$')

    if report_type == "report1":
        if "ページパス + クエリ文字列" in df.columns:
            df = decode_column(df, "ページパス + クエリ文字列")

        # 詳細ページ1
        if "ページパス + クエリ文字列" in df.columns:
            detail_df = df[df["ページパス + クエリ文字列"].astype(str).str.match(faq_pattern, na=False)].copy()
            detail_df["カテゴリ"] = detail_df["ページパス + クエリ文字列"].apply(lambda u: extract_query_param(u, "category"))
            detail_df["キーワード"] = detail_df["ページパス + クエリ文字列"].apply(lambda u: extract_query_param(u, "keyword"))
            detail_df = clean_sheet_titles(detail_df, "詳細ページ1")
            detail_df = reorder_and_trim_columns(detail_df, "詳細ページ1")
            sheets["詳細ページ1"] = detail_df

        # カテゴリ1：カテゴリパラメータを持つ元データ全体
        if "ページパス + クエリ文字列" in df.columns:
            base = df.copy()
            base = decode_column(base, "ページパス + クエリ文字列")
            base["カテゴリ"] = base["ページパス + クエリ文字列"].apply(lambda u: extract_query_param(u, "category"))
            base["キーワード"] = base["ページパス + クエリ文字列"].apply(lambda u: extract_query_param(u, "keyword"))
            cat_df = base[base["カテゴリ"].astype(str) != ""].copy()
            cat_df = clean_sheet_titles(cat_df, "カテゴリ1")
            cat_df = reorder_and_trim_columns(cat_df, "カテゴリ1")
            sheets["カテゴリ1"] = cat_df

            kw_df = base[base["キーワード"].astype(str) != ""].copy()
            kw_df = clean_sheet_titles(kw_df, "キーワード1")
            kw_df = reorder_and_trim_columns(kw_df, "キーワード1")
            sheets["キーワード1"] = kw_df

    elif report_type == "report2":
        if "ページパス + クエリ文字列" in df.columns:
            df = decode_column(df, "ページパス + クエリ文字列")
        if "ページの参照元 URL" in df.columns:
            df = decode_column(df, "ページの参照元 URL")

        # 詳細ページ2
        if "ページパス + クエリ文字列" in df.columns:
            detail_df = df[df["ページパス + クエリ文字列"].astype(str).str.match(faq_pattern, na=False)].copy()
            detail_df = clean_sheet_titles(detail_df, "詳細ページ2")
            detail_df = reorder_and_trim_columns(detail_df, "詳細ページ2")
            sheets["詳細ページ2"] = detail_df

        # カテゴリ2
        tmp_cat = df.copy()
        if "ページパス + クエリ文字列" in tmp_cat.columns:
            tmp_cat["カテゴリ"] = tmp_cat["ページパス + クエリ文字列"].apply(lambda u: extract_query_param(u, "category"))
            tmp_cat["キーワード"] = tmp_cat["ページパス + クエリ文字列"].apply(lambda u: extract_query_param(u, "keyword"))
            cat_sheet = tmp_cat[tmp_cat["カテゴリ"].astype(str) != ""].copy()
            cat_sheet = clean_sheet_titles(cat_sheet, "カテゴリ2")
            cat_sheet = reorder_and_trim_columns(cat_sheet, "カテゴリ2")
            sheets["カテゴリ2"] = cat_sheet

            kw_sheet = tmp_cat[tmp_cat["キーワード"].astype(str) != ""].copy()
            kw_sheet = clean_sheet_titles(kw_sheet, "キーワード2")
            kw_sheet = reorder_and_trim_columns(kw_sheet, "キーワード2")
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
        filtered = reorder_and_trim_columns(filtered, "faqページ")
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
