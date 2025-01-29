from shiny.express import input, render, ui
from shinywidgets import render_plotly
import plotly.express as px
ui.input_slider("n", "N", 0, 100, 20)


@render.code
def txt():
    return f"n*2 is {input.n() * 2}"

@render_plotly
def plot():
    fig = px.scatter(x=[1, 2, 3], y=[1, 4, 9], title="Basic Scatter Plot")
    return fig
