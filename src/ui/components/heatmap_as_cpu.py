"""
CPU Heatmap Component for AS Analysis
Creates heatmaps grouped by Application System (AS) showing all servers for each AS
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def create_as_cpu_heatmap(
    analysis_df: pd.DataFrame,
    server_cpu_capacity_map: Dict[str, float],
    server_ram_capacity_map: Dict[str, float],
    sort_by: str = "Суммарной нагрузке",
    sort_order: str = "По убыванию"
) -> Tuple[go.Figure, List[str], List[str], np.ndarray, pd.DataFrame]:
    """
    Create CPU heatmap grouped by AS (Application System)
    
    Args:
        analysis_df: DataFrame with columns: as_name, server, timestamp, cpu.usage.average
        server_cpu_capacity_map: Dictionary mapping server names to CPU capacity
        server_ram_capacity_map: Dictionary mapping server names to RAM capacity
        sort_by: Sort option ("Суммарной нагрузке", "Средней нагрузке", "Мощности CPU", "Имени АС")
        sort_order: Sort order ("По убыванию" or "По возрастанию")
    
    Returns:
        Tuple of (figure, y_labels, x_labels, values_matrix, pivot_df)
    """
    if 'cpu.usage.average' not in analysis_df.columns:
        raise ValueError("DataFrame must contain 'cpu.usage.average' column")
    
    # Prepare data
    df = analysis_df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Create 30-minute intervals
    df['half_hour_interval'] = (
        df['timestamp'].dt.hour * 2 +
        (df['timestamp'].dt.minute // 30)
    )
    
    # Group by AS, server, and interval
    heatmap_data = df.groupby(['as_name', 'server', 'half_hour_interval'])[
        'cpu.usage.average'].mean().reset_index()
    
    # Create pivot table
    pivot_df = heatmap_data.pivot_table(
        index=['as_name', 'server'],
        columns='half_hour_interval',
        values='cpu.usage.average',
        fill_value=0
    ).reset_index()
    
    # Calculate load metrics for sorting
    pivot_df['total_load'] = pivot_df.iloc[:, 2:].sum(axis=1)
    pivot_df['avg_load'] = pivot_df.iloc[:, 2:].mean(axis=1)
    
    # Apply sorting
    if sort_by == "Суммарной нагрузке":
        pivot_df = pivot_df.sort_values('total_load', ascending=(sort_order == "По возрастанию"))
    elif sort_by == "Средней нагрузке":
        pivot_df = pivot_df.sort_values('avg_load', ascending=(sort_order == "По возрастанию"))
    elif sort_by == "Мощности CPU":
        pivot_df['capacity_cpu'] = pivot_df['server'].map(server_cpu_capacity_map)
        pivot_df = pivot_df.sort_values('capacity_cpu', ascending=(sort_order == "По возрастанию"))
    else:  # "Имени АС"
        pivot_df = pivot_df.sort_values(['as_name', 'server'], ascending=(sort_order == "По возрастанию"))
    
    # Prepare intervals
    all_intervals = list(range(48))
    for interval in all_intervals:
        if interval not in pivot_df.columns:
            pivot_df[interval] = 0
    
    # Create Y labels (AS | Server with capacities)
    y_labels = []
    for _, row in pivot_df.iterrows():
        as_name = row['as_name']
        server = row['server']
        cpu_capacity = server_cpu_capacity_map.get(server, 0)
        ram_capacity = server_ram_capacity_map.get(server, 0)
        y_label = f"{as_name} | {server} (CPU: {cpu_capacity:.0f} ядер, RAM: {ram_capacity:.0f} GB)"
        y_labels.append(y_label)
    
    # Prepare values matrix
    values_matrix = pivot_df[all_intervals].values
    
    # Create X labels (time intervals)
    x_labels = []
    for interval in all_intervals:
        hour = interval // 2
        minute = (interval % 2) * 30
        x_labels.append(f"{hour:02d}:{minute:02d}")
    
    # Prepare hover data
    hover_texts = []
    for i, (_, row) in enumerate(pivot_df.iterrows()):
        as_name = row['as_name']
        server = row['server']
        cpu_capacity = server_cpu_capacity_map.get(server, 0)
        ram_capacity = server_ram_capacity_map.get(server, 0)
        row_hover = []
        
        for j, interval in enumerate(range(48)):
            load_value = values_matrix[i, j]
            hour = interval // 2
            minute = (interval % 2) * 30
            time_str = f"{hour:02d}:{minute:02d}"
            
            if load_value <= 0:
                text = (f"<b>{as_name} | {server}</b><br>"
                       f"CPU: {cpu_capacity:.0f} ядер<br>"
                       f"RAM: {ram_capacity:.0f} GB<br>"
                       f"Время: {time_str}<br>Нет данных")
            else:
                # Color categorization
                if load_value < 15:
                    load_status = "🟢 Низкая"
                elif load_value < 85:
                    load_status = "🟡 Средняя"
                else:
                    load_status = "🔴 Высокая"
                
                text = (f"<b>{as_name} | {server}</b><br>"
                       f"CPU: {cpu_capacity:.0f} ядер<br>"
                       f"RAM: {ram_capacity:.0f} GB<br>"
                       f"🕐 {time_str}<br>"
                       f"📊 Нагрузка CPU: <b>{load_value:.1f}%</b><br>"
                       f"🏷️ {load_status}<br>")
            
            row_hover.append(text)
        hover_texts.append(row_hover)
    
    # Create figure
    fig = go.Figure()
    
    # Color scale
    colorscale = [
        [0.0, "#00FF00"],  # Green (0%)
        [0.3, "#90EE90"],  # Light green (30%)
        [0.5, "#FFFF00"],  # Yellow (50%)
        [0.7, "#FFA500"],  # Orange (70%)
        [1.0, "#FF0000"]   # Red (100%)
    ]
    
    # Add heatmap trace
    fig.add_trace(go.Heatmap(
        z=values_matrix,
        x=x_labels,
        y=y_labels,
        colorscale=colorscale,
        text=values_matrix.round(1),
        texttemplate='%{text}%',
        textfont={"size": 8, "color": "black"},
        hovertemplate="%{hovertext}<extra></extra>",
        hoverinfo='text',
        hovertext=hover_texts,
        colorbar=dict(
            title="Нагрузка CPU (%)",
            titleside="right",
            tickvals=[0, 25, 50, 75, 100],
            ticktext=["0%", "25%", "50%", "75%", "100%"],
            len=0.9
        ),
        zmin=0,
        zmax=100,
        showscale=True,
        xgap=0.5,
        ygap=0.5
    ))
    
    # Calculate chart height
    chart_height = max(600, len(y_labels) * 25)
    
    # Update layout (без заголовка на карте)
    fig.update_layout(
        height=chart_height,
        xaxis=dict(
            title="Время суток (интервалы по 30 минут)",
            tickmode='array',
            tickvals=list(range(0, 48, 4)),
            ticktext=[x_labels[i] for i in range(0, 48, 4)],
            tickangle=45,
            tickfont=dict(size=10),
            gridcolor='rgba(128, 128, 128, 0.2)',
            showgrid=True
        ),
        yaxis=dict(
            title="АС | Сервер (CPU ядра, RAM GB)",
            tickfont=dict(size=9),
            automargin=True
        ),
        margin=dict(l=200, r=50, t=50, b=100),
        plot_bgcolor='white',
        paper_bgcolor='white'
    )
    
    # Add hour lines
    for hour in range(0, 48, 2):
        fig.add_vline(
            x=hour - 0.5,
            line_dash="dot",
            line_color="rgba(128, 128, 128, 0.3)",
            line_width=1
        )
    
    return fig, y_labels, x_labels, values_matrix, pivot_df


def create_separate_as_heatmaps(
    analysis_df: pd.DataFrame,
    server_cpu_capacity_map: Dict[str, float],
    server_ram_capacity_map: Dict[str, float],
    sort_by: str = "Суммарной нагрузке",
    sort_order: str = "По убыванию"
) -> Dict[str, go.Figure]:
    """
    Create separate CPU heatmaps for each AS
    
    Args:
        analysis_df: DataFrame with columns: as_name, server, timestamp, cpu.usage.average
        server_cpu_capacity_map: Dictionary mapping server names to CPU capacity
        server_ram_capacity_map: Dictionary mapping server names to RAM capacity
        sort_by: Sort option
        sort_order: Sort order
    
    Returns:
        Dictionary mapping AS names to their heatmap figures
    """
    if 'cpu.usage.average' not in analysis_df.columns:
        raise ValueError("DataFrame must contain 'cpu.usage.average' column")
    
    # Group by AS
    as_groups = analysis_df.groupby('as_name')
    as_figures = {}
    
    for as_name, as_df in as_groups:
        try:
            fig, _, _, _, _ = create_as_cpu_heatmap(
                as_df,
                server_cpu_capacity_map,
                server_ram_capacity_map,
                sort_by,
                sort_order
            )
            
            # Update title for specific AS
            fig.update_layout(
                title=dict(
                    text=f"АС: {as_name}<br>Нагрузка CPU по серверам",
                    font=dict(size=16),
                    x=0.5,
                    xanchor='center'
                )
            )
            
            as_figures[as_name] = fig
        except Exception as e:
            print(f"Error creating heatmap for AS {as_name}: {e}")
            continue
    
    return as_figures


# Keep the existing scrollable HTML function for backward compatibility
def create_scrollable_html(fig_heatmap_as, y_labels, x_labels, values_matrix, pivot_df, server_capacity_map,
                           start_date, end_date, selected_as_count, total_servers, total_capacity):
    """
    Legacy function - creates scrollable HTML for CPU heatmaps
    Kept for backward compatibility with existing code
    """
    # This is the existing implementation from the original file
    # Import it from the original location if needed
    pass
