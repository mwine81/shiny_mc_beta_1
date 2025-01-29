from shiny.express import input, render, ui
from shiny import reactive
from shinywidgets import render_plotly
import plotly.express as px
from config import *
import polars as pl
from polars import col as c
import polars.selectors as cs

ui.page_opts(title="Beta App")

with ui.sidebar(width=300):
    ui.input_selectize(
        id='files',
        label='File Choice',
        choices=[str(file.stem) for file in CLAIM_DIR.iterdir() ],
        multiple=True,
        selected=[str(file.stem) for file in CLAIM_DIR.iterdir()]
    )

    ui.input_selectize(
        id='drug_class',
        label='Drug Class Choice',
        choices=[],
        multiple=True,
        remove_button=True
    )

    ui.input_selectize(
        id='product',
        label='Product Choice',
        choices=[],
        remove_button=True,
        multiple=True
    )

    ui.input_selectize(
        id='affiliated',
        label='Affiliated Choice',
        choices=['All','Affiliated','Non-Affiliated'],
        remove_button=True,
        selected='All'
    )
    ui.input_selectize(
        id='special',
        label='Specialty Choice',
        choices=['All','Specialty','Non-Specialty'],
        remove_button=True,
        selected='All'
    )

@reactive.effect
def filter_drug_class():
    data = load_file()

    if input.product():
        data = data.filter(c.product.is_in(input.product()))

    data = data.select(c.drug_class).unique().sort(by='drug_class').collect().to_series().to_list()
    data = [GROUP_DICT[d] for d in GROUP_DICT]
    ui.update_selectize(
        id='drug_class',
        choices=data,
        selected=[]
        )

@reactive.calc
def load_file():
    files = [CLAIM_DIR / f'{file}.parquet' for file in input.files()]
    if not files:
        files = [file for file in CLAIM_DIR.iterdir()]
    data = (
        pl.scan_parquet(files)
    )
    return data

@reactive.calc
def filter_data() -> pl.LazyFrame:
    diff = (c.total - c.mc_total).alias('diff')
    data = load_file().with_columns(diff)
    if input.drug_class():
        drug_group_map = {v:k for k,v in GROUP_DICT.items()}
        drug_groups = [drug_group_map[g] for g in input.drug_class()]
        data = data.filter(c.drug_class.is_in(drug_groups))
    if input.product():
        data = data.filter(c.product.is_in(input.product()))
    if input.affiliated() != 'All':
        affiliation_map = {'Affiliated':True, 'Non-Affiliated':False}
        data = data.filter(c.affiliated == affiliation_map[input.affiliated()])
    if input.special() != 'All':
        specialty_map = {'Specialty':True, 'Non-Specialty':False}
        data = data.filter(c.affiliated == specialty_map[input.special()])
    return data

@reactive.effect
def filter_product():
    data =  load_file()
    if input.drug_class():
        data = data.filter(c.drug_class.is_in(input.drug_class()))

    data = data.select(c.product).unique().sort(by='product').collect().to_series().to_list()
    ui.update_selectize(
        id='product',
        choices=data,
        selected=[]
        )

with ui.layout_column_wrap(fill=False,max_height=150):
    with ui.value_box():
        'Total'
        @render.ui
        def total():
            total = filter_data().select(c.total.sum()).collect().item()
            return f'${total:,.0f}'
    with ui.value_box():
        'MCCPDC'
        @render.ui
        def mc_total():
            total = filter_data().select(c.mc_total.sum()).collect().item()
            return f'${total:,.0f}'

    with ui.value_box():
        'MCCPDC DIFF'
        @render.ui
        def diff():
            total = filter_data().select(c.total.sum() - c.mc_total.sum()).collect().item()
            return f'${total:,.0f}'

    with ui.value_box():
        'Rx Total'
        @render.ui
        def rx_total():
            total = filter_data().select(c.rx_ct.sum()).collect().item()
            return f'{total:,.0f}'

    with ui.value_box():
        'Avg. Per Rx'
        @render.ui
        def svg_rx():
            total = filter_data().select((c.total.sum() - c.mc_total.sum()) / c.rx_ct.sum()).collect().item()
            return f'${total:,.2f}'

with ui.layout_columns(col_widths =[7,5],fill=False):
    with ui.card():
        @render_plotly
        def drug_class_plot():
            # rk = TOP_SAVINGS_DICT.get(rank_by)
            data = (
                filter_data()
                .group_by(c.drug_class, c.generic_name)
                .agg(
                    c.diff.sum(),
                    c.total.sum(),
                    c.rx_ct.sum()
                )
                .with_columns(c.drug_class.replace(GROUP_DICT))
                # .with_columns(saving_per_rx())
            )
            fig = px.pie(
                data.collect(),
                values='diff',
                names="drug_class",
                hole=.7,
            )
            return fig

    with ui.card(full_screen=True):
        @render_plotly
        def top_saving_drugs():
            def saving_per_rx():
                return (c.diff / c.rx_ct).round(2).alias("per_rx")
            #rk = TOP_SAVINGS_DICT.get(rank_by)
            #sort_col = 'per_rx' if rk == 'per_rx' else 'diff'
            data = (
                filter_data()
                .group_by(c.generic_name)
                .agg(c.diff.sum(), c.total.sum(), c.mc_total.sum(), c.rx_ct.sum())
                .with_columns(saving_per_rx())
                #.sort(rk, descending=True)
                .sort('per_rx', descending=True)
                #.head(n_results)
                .head(10)
                #.sort(by=sort_col)
                .collect()
            )

            fig = px.bar(
                data,
                y="generic_name",
                #x=[sort_col],
                x="per_rx",
                #title=f"MCCPDC Savings - Top {n_results} Drugs by {rank_by}($)",
                orientation="h",
                barmode="group",
                # text_auto=True,
                text=data['diff'],#data[sort_col],
                color_discrete_sequence=[MCCPDC_PRIMARY],
            )
            fig.update_traces(texttemplate="%{text:$,.0f}", )
            fig.update_layout(
                showlegend=False,
                #height=50 * n_results,
            )

            fig.update_xaxes(
                # tickformat="$,.0f",
                showticklabels=False,
                title='',

            )
            fig.update_yaxes(
                title='',
                ticksuffix='    '

            )
            return fig

#with ui.layout_columns(col_widths =[3,9],fill=False):
    # with ui.card():
    #     @render_plotly
    #     def average_charge_per_rx_fig():
    #         data = (
    #             filter_data()
    #             .select(c.total.sum().round(2), c.mc_total.sum().round(2), c.rx_ct.sum().round(2))
    #             .select(pl.col('total', 'mc_total') / c.rx_ct)
    #             .unpivot()
    #         )
    #         fig = px.bar(
    #             data.collect(),
    #             x="variable",
    #             y="value",
    #             color="variable",
    #             text="value",
    #             color_discrete_map={'mc_total': MCCPDC_PRIMARY, 'total': MCCPDC_ACCENT}
    #         )
    #         fig.update_yaxes(
    #             showticklabels=False,
    #             title='',
    #             range=[0, data.select(c.value).max().collect().item() * 1.2]
    #         )
    #         # Style the labels (optional)
    #         fig.update_traces(
    #             texttemplate="%{text:$.2f}",  # Format the text labels
    #             textposition="outside",
    #             textfont_size=20,
    #             textfont_color=MCCPDC_PRIMARY,
    #             # textfont_color = 'white'
    #         )
    #         fig.update_xaxes(
    #             title='',
    #             showticklabels=False,
    #         )
    #         fig.update_layout(
    #             plot_bgcolor='white',
    #             legend=dict(
    #                 orientation="h",  # Set legend orientation to horizontal
    #                 x=.75,  # Set the x-position of the legend (centered)
    #                 xanchor="center",  # Anchor the legend at the center
    #                 y=1.2,  # Adjust the y-position (above the plot),
    #                 title='',
    #             ),
    #
    #         )
    #         return fig

    # with ui.card():
    #     @render_plotly
    #     def fig_monthly_spend():
    #         fee = 10
    #         data = (
    #             filter_data()
    #             .with_columns((c.total - c.mc_total).alias('diff'))
    #             .with_columns(((fee * c.rx_ct) + c.nadac).alias('nadac'))
    #             .group_by(pl.date(c.year, c.month, 1).alias('dos'))
    #             .agg(pl.col('total', 'mc_total', 'nadac').sum())
    #             .sort(c.dos)
    #         )
    #         fig = px.line(data.collect(),
    #                       x='dos',
    #                       y=['total', 'mc_total', 'nadac'],
    #                       line_shape='spline',
    #                       color_discrete_map={'mc_total':MCCPDC_PRIMARY,'nadac':MCCPDC_SECONDARY,'total':MCCPDC_ACCENT}
    #                       )
    #         fig.update_layout(
    #             plot_bgcolor = 'white',
    #             legend=dict(
    #             title='',
    #             orientation="h",
    #             x=.1,
    #             xanchor="center",
    #             y=1.2,
    #         )
    #                           )
    #         fig.update_traces(
    #             line=dict(width=4),
    #             opacity=0.60,
    #         )
    #         fig.update_xaxes(title='')
    #         fig.update_yaxes(title='Spend($)')
    #         return fig


