import streamlit as st
import requests
import pandas as pd
import os

# --- 設定 ---
API_KEY = st.secrets["API_KEY"]
SAVE_FILE = "tft_history.csv"

# ページ設定：ワイドレイアウト、サイドバーは最初から表示
st.set_page_config(page_title="TFT Review Tool", layout="wide", initial_sidebar_state="expanded")
st.title("🛡️ TFT 自己分析ダッシュボード")

# CSVの準備（"scouting" 列を新しく追加しています）
if not os.path.exists(SAVE_FILE):
    columns = ["match_id", "placement", "units", "augments", "item_quality", "scouting", "cause", "memo"]
    pd.DataFrame(columns=columns).to_csv(SAVE_FILE, index=False)

# セッション状態（記憶）の初期化
if "match_data_list" not in st.session_state:
    st.session_state.match_data_list = []

# --- 保存用関数 ---
def save_data(m_id, placement, units_list, augs, item_q, scouting, cause, memo):
    df = pd.read_csv(SAVE_FILE)
    units_str = " / ".join(units_list)
    augs_str = " | ".join(augs)

    new_data = {
        "match_id": m_id, 
        "placement": placement, 
        "units": units_str, 
        "augments": augs_str,
        "item_quality": item_q,
        "scouting": scouting, # 追加項目
        "cause": cause, 
        "memo": memo
    }

    if m_id in df['match_id'].values:
        # 既存データがある場合は上書き
        df.loc[df['match_id'] == m_id, list(new_data.keys())] = list(new_data.values())
    else:
        # 新規データは下に追加
        df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
    
    # マッチIDで昇順に並び替え（時系列順にする）
    df = df.sort_values("match_id", ascending=True)
    df.to_csv(SAVE_FILE, index=False)
    st.success(f"試合 {m_id} の詳細を保存しました！")

# --- サイドバー：プレイヤー検索 ---
with st.sidebar:
    st.header("👤 プレイヤー検索")
    game_name = st.text_input("Game Name", value="umc")
    tag_line = st.text_input("Tag Line", value="9999")
    
    if st.button("戦績を取得", use_container_width=True):
        with st.spinner("最新の戦績を取得中..."):
            # 1. PUUIDを取得
            acc_url = f"https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}?api_key={API_KEY}"
            acc_res = requests.get(acc_url)
            if acc_res.status_code == 200:
                puuid = acc_res.json()['puuid']
                # 2. 直近5試合のMatch IDを取得
                m_url = f"https://asia.api.riotgames.com/tft/match/v1/matches/by-puuid/{puuid}/ids?count=5&api_key={API_KEY}"
                m_ids = requests.get(m_url).json()
                
                # 3. 各試合の詳細データを取得
                temp_list = []
                for m_id in m_ids:
                    d_url = f"https://asia.api.riotgames.com/tft/match/v1/matches/{m_id}?api_key={API_KEY}"
                    m_info = requests.get(d_url).json()
                    for p in m_info['info']['participants']:
                        if p['puuid'] == puuid:
                            temp_list.append({"id": m_id, "data": p})
                st.session_state.match_data_list = temp_list
            else:
                st.error("APIキーが無効か、プレイヤー名が間違っています")

# --- メイン表示エリア ---
if st.session_state.match_data_list:
    history_df = pd.read_csv(SAVE_FILE)
    
    for item in st.session_state.match_data_list:
        m_id = item['id']
        p = item['data']
        
        # 既存データの読み込み（なければ初期値を設定）
        existing = history_df[history_df['match_id'] == m_id]
        d_aug = existing['augments'].values[0].split(" | ") if not existing.empty else ["", "", ""]
        d_item = existing['item_quality'].values[0] if not existing.empty else "理想"
        d_scout = existing['scouting'].values[0] if not existing.empty else "OK"
        d_cause = existing['cause'].values[0] if not existing.empty else "選択してください"
        d_memo = existing['memo'].values[0] if not existing.empty else ""

        # 試合ごとの折りたたみパネル
        with st.expander(f"📊 {p['placement']}位 - 試合ID: {m_id}"):
            col_info, col_aug, col_input = st.columns([1.5, 1.5, 1.5])
            
            # 左カラム：盤面と基本評価
            with col_info:
                st.write("**🛡️ 最終盤面**")
                units = [f"{u['character_id'].split('_')[-1]}{'★'*u['tier']}" for u in p['units']]
                st.info(" / ".join(units))
                
                st.write("**⚔️ アイテム完成度**")
                sel_item = st.radio("アイテムについて", ["理想", "妥協"], index=["理想", "妥協"].index(d_item), key=f"item_{m_id}", horizontal=True)

                st.write("**👀 スカウティング**")
                sel_scout = st.radio("配置・被り確認", ["OK", "不足"], index=["OK", "不足"].index(d_scout), key=f"scout_{m_id}", horizontal=True)

            # 中央カラム：オーグメント
            with col_aug:
                st.write("**✨ オーグメント記録**")
                aug1 = st.text_input("1つ目", value=d_aug[0] if len(d_aug)>0 else "", key=f"aug1_{m_id}")
                aug2 = st.text_input("2つ目", value=d_aug[1] if len(d_aug)>1 else "", key=f"aug2_{m_id}")
                aug3 = st.text_input("3つ目", value=d_aug[2] if len(d_aug)>2 else "", key=f"aug3_{m_id}")

            # 右カラム：自由記述レビュー
            with col_input:
                st.write("**📝 レビュー**")
                opts = ["選択してください", "進行が良い", "配置勝ち", "配置ミス", "進行ミス", "下振れ", "上振れ"]
                idx = opts.index(d_cause) if d_cause in opts else 0
                sel_c = st.selectbox("勝因/敗因", opts, index=idx, key=f"c_{m_id}")
                sel_m = st.text_area("今後の課題・メモ", value=d_memo, key=f"m_{m_id}", height=100)
                
                # 保存ボタン
                if st.button("この試合を保存", key=f"btn_{m_id}", use_container_width=True):
                    save_data(m_id, p['placement'], units, [aug1, aug2, aug3], sel_item, sel_scout, sel_c, sel_m)

# --- 管理エリア（CSVの表示とダウンロード） ---
st.divider()
st.subheader("📊 保存済みデータの管理")
if os.path.exists(SAVE_FILE):
    export_df = pd.read_csv(SAVE_FILE) 
    if not export_df.empty:
        # データの一覧表示
        st.dataframe(export_df, use_container_width=True)
        
        col_dl, col_reset = st.columns([1, 1])
        with col_dl:
            # CSVダウンロード機能
            csv_data = export_df.to_csv(index=False).encode('utf_8_sig')
            st.download_button(
                label="📥 全データをCSVでダウンロード", 
                data=csv_data, 
                file_name="tft_review_history.csv", 
                mime="text/csv"
            )
        
        with col_reset:
            # データリセット機能
            st.write("---")
            confirm_reset = st.checkbox("保存された全データを削除しますか？")
            if st.button("🚨 データをリセットする", disabled=not confirm_reset):
                os.remove(SAVE_FILE)
                st.session_state.match_data_list = []
                st.success("全てのデータを削除しました。")
                st.rerun()
    else:
        st.info("まだ保存された試合データがありません。戦績を取得してレビューを書いてみましょう！")