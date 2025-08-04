import streamlit as st
import pandas as pd
import urllib.parse
import re
from io import BytesIO

st.set_page_config(page_title="FAQレポート解析アプリ")
st.title("FAQレポート解析アプリ")

def safe_replace_title(df):
    col = "ページ タイトルとスクリーン クラス"
    if col in df.columns:
        df[col] = df[col].astype(str).str.replace(r"\|\s*Q\.ENEST（キューエネス）でんき", "", regex=True)
    return df

def decode_column(df, col_name):
    if col_name in df.columns:
        df[col_name] = df[col_name].astype(str).apply(lambda x: urllib.parse.unquote(x))
    return df

def extract_query_param(value, param):
    if pd.isna(value):
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

def clean_filename_base(fname):
    # 拡張子と日付レンジ（_YYYYMMDD_YYYYMMDD）を削除
    name = re.sub(r'\.csv$', '', fname, flags=re.IGNORECASE)
    name = re.sub(r'_(\d{8}_\d{8})$', '', name)
    return name

def process_report(file, report_type):
    df = load_csv_with_header_adjustment(file)
    if df.empty:
        return {}

    df = safe_replace_title(df)
    sheets = {}

    faq_pattern = re.compile(r'^/lowv/faq/\d+-\d+$')

    if report_type == "report1":
        # ページパス + クエリ文字列 をデコード
        if "ページパス + クエリ文字列" in df.columns:
            df = decode_column(df, "ページパス + クエリ文字列")
            # detail: /lowv/faq/X-X のみ抽出
            detail_df = df[df["ページパス + クエリ文字列"].astype(str).str.match(faq_pattern, na=False)].copy()
            # カテゴリ／キーワードを付与（C,D）
            detail_df["カテゴリ"] = detail_df["ページパス + クエリ文字列"].apply(lambda u: extract_query_param(u, "category"))
            detail_df["キーワード"] = detail_df["ページパス + クエリ文字列"].apply(lambda u: extract_query_param(u, "keyword"))
            sheets["詳細ページ"] = detail_df

    elif report_type == "report2":
        # B列（ページパス + クエリ文字列）をデコード
        if "ページパス + クエリ文字列" in df.columns:
            df = decode_column(df, "ページパス + クエリ文字列")
            # 詳細ページは /lowv/faq/X-X のみを出す（カテゴリ/キーワード追加しない）
            detail_df = df[df["ページパス + クエリ文字列"].astype(str).str.match(faq_pattern, na=False)].copy()
            sheets["詳細ページ"] = detail_df

            # カテゴリシート（カテゴリがある行、元の列構成を維持）
            tmp = df.copy()
            tmp["カテゴリ"] = tmp["ページパス + クエリ文字列"].apply(lambda u: extract_query_param(u, "category"))
            tmp["キーワード"] = tmp["ページパス + クエリ文字列"].apply(lambda u: extract_query_param(u, "keyword"))
            cat_sheet = tmp[tmp["カテゴリ"].astype(str) != ""].copy()
            kw_sheet = tmp[tmp["キーワード"].astype(str) != ""].copy()
            sheets["カテゴリ"] = cat_sheet
            sheets["キーワード"] = kw_sheet

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
            base = clean_filename_base(fname)
            for sheet_name, df in sheets.items():
                safe_name = f"{sheet_name}"
                # 複数ファイルのときシート名衝突を防ぐ（同名ファイル複数ならインデックス付与）
                candidate = safe_name
                suffix = 1
                while candidate[:31] in writer.sheets:
                    suffix += 1
                    candidate = f"{safe_name}_{suffix}"
                df.to_excel(writer, sheet_name=candidate[:31], index=False)

    output.seek(0)
    st.download_button(
        label="変換済み Excel をダウンロード",
        data=output.getvalue(),
        file_name="faq解析結果.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
