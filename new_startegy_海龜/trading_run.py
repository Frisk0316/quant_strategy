from pathlib import Path
from turtle import mode
import trading_target_func as ttf
import polars as pl
import plotly.graph_objects as go
from plotly.subplots import make_subplots
#=========================以下是找出高原的部分=========================

'''

csv_path = Path(r"C:\trading_data\暫存\index_parameter_result_full.csv")
result_df_all = pl.read_csv(csv_path)
plateaus_list=ttf.find_plateau(result_df_all,free_params=["enter_term_sys1", "leave_term_sys1", "enter_term_sys2"],
                min_asset = 0,
                min_expectancy= 0,
                min_plr= 1.0,
                mode='system1',
                plot = True)
print(plateaus_list)

'''
#========================以下跑策略的部分=========================
'''
csv_path = Path(r"C:\trading_data\btc_1m2.csv")
df = pl.read_csv(csv_path)
print(df.head())
daily_df= ttf.resample_to_daily(df,"BTC-USDT-SWAP")
'''
csv_path = Path(r"C:\trading_data\btc_1H_new.csv")
df = pl.read_csv(csv_path)
print(df.head())
daily_df = ttf.resample_to_daily(df,"BTC-USDT-SWAP")
#daily_df = pl.concat([daily_1m, daily_1h])


'''
trade_df_budget=ttf.turtle_trading_system_full(daily_df,20,55,10,20,4,4,50000.0,0.01,min_position=0.0001,fee= 0.003,atr_period = 20)

trade_df_budget.write_csv("trade_df_full_short.csv")
'''


sweep_df = ttf.sweep_params_interactive_full(daily_df,10000.0,0.25,0.0001,0.003,20, 4,4,10000.0)
print("Done")
sweep_df =  ttf.sweep_params_interactive(daily_df,30,1.0, 0.003, 'system1')
print("Done")


def plot_consec_distributions(
    csv_path: str = r"C:\Users\User\OneDrive\桌面\trading\index_parameter_result_full.csv",
    cols= None,
    output_html = None,
):
    """
    把 max_consec 系列欄位各自畫成長條分布圖（2x3 子圖）。

    Parameters
    ----------
    csv_path : CSV 路徑
    cols     : 要畫的欄位；None 時用預設六個
    output_html : 若給路徑則另存成 HTML
    """
    if cols is None:
        cols = [
            "s1_max_consec_win", "s1_max_consec_loss",
            "s2_max_consec_win", "s2_max_consec_loss",
            "overall_max_consec_win", "overall_max_consec_loss",
        ]

    df = pl.read_csv(csv_path)

    # 檢查欄位是否都存在，避免 silent 漏畫
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"CSV 缺少欄位：{missing}")

    n = len(cols)
    n_cols = 3
    n_rows = (n + n_cols - 1) // n_cols

    fig = make_subplots(
        rows=n_rows, cols=n_cols,
        subplot_titles=cols,
        horizontal_spacing=0.08,
        vertical_spacing=0.14,
    )

    for i, col in enumerate(cols):
        r, c = divmod(i, n_cols)
        r += 1
        c += 1

        # 算每個整數值出現次數，並依數值排序
        vc = (
            df.select(col)
            .drop_nulls()
            .group_by(col)
            .len()
            .sort(col)
        )
        x = vc[col].to_list()
        y = vc["len"].to_list()

        # win 用綠、loss 用紅，方便對照
        color = "#2ca02c" if "win" in col else "#d62728"

        fig.add_trace(
            go.Bar(
                x=x, y=y,
                marker_color=color,
                name=col,
                hovertemplate=f"{col}=%{{x}}<br>count=%{{y}}<extra></extra>",
                showlegend=False,
            ),
            row=r, col=c,
        )
        fig.update_xaxes(title_text="連續次數", dtick=1, row=r, col=c)
        fig.update_yaxes(title_text="出現次數", row=r, col=c)

    fig.update_layout(
        title="最大連續勝/負次數分布",
        height=320 * n_rows,
        bargap=0.15,
        template="plotly_white",
    )

    if output_html:
        fig.write_html(output_html)
        print(f"已存檔：{output_html}")

    fig.show()
    return fig
plot_consec_distributions()                                   # 直接顯示
plot_consec_distributions(output_html="consec_dist.html")     # 另存 HTML

