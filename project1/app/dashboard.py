# -*- coding: utf-8 -*-
"""
MA216 Quantitative Trading System Dashboard
Interactive visualization for strategy performance
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
from datetime import datetime

sys.path.append('src')

# Page configuration
st.set_page_config(
    page_title="MA216 Quant System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
    }
    .positive {
        color: #00cc00;
    }
    .negative {
        color: #ff0000;
    }
    </style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    """Load processed data from local files"""
    try:
        # Load best strategy data from Phase 7
        df = pd.read_csv('outputs/tables/best_strategy_in_sample_20260917_150126.csv')
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        return df
    except FileNotFoundError:
        st.error("Data file not found. Please run Phase 7 first.")
        return None

@st.cache_data
def load_comparison_data():
    """Load strategy comparison data"""
    try:
        df = pd.read_csv('outputs/tables/strategy_comparison_in_sample_20260917_150126.csv')
        return df
    except FileNotFoundError:
        return None

def calculate_metrics(df):
    """Calculate key metrics"""
    metrics = {}
    
    if len(df) > 0:
        metrics['latest_date'] = df['trade_date'].max().strftime('%Y-%m-%d')
        metrics['latest_price'] = df['close'].iloc[-1]
        metrics['latest_ma5'] = df.get('ma5', pd.Series([None])).iloc[-1] if 'ma5' in df.columns else None
        metrics['latest_ma20'] = df.get('ma20', pd.Series([None])).iloc[-1] if 'ma20' in df.columns else None
        
        # Calculate returns
        initial_equity = df['strategy_equity'].iloc[0]
        final_equity = df['strategy_equity'].iloc[-1]
        metrics['total_return'] = (final_equity / initial_equity - 1) * 100
        
        # Calculate benchmark return
        benchmark_initial = df['benchmark_equity'].iloc[0]
        benchmark_final = df['benchmark_equity'].iloc[-1]
        metrics['benchmark_return'] = (benchmark_final / benchmark_initial - 1) * 100
        
        # Trading days
        trading_days = len(df)
        years = trading_days / 252
        metrics['annual_return'] = ((1 + metrics['total_return']/100) ** (1/years) - 1) * 100
        
        # Volatility
        returns = df['strategy_return'].dropna()
        metrics['volatility'] = returns.std() * np.sqrt(252) * 100
        
        # Sharpe ratio
        excess_returns = returns - 0  # Assuming risk-free rate = 0
        if returns.std() != 0:
            metrics['sharpe_ratio'] = (excess_returns.mean() / returns.std()) * np.sqrt(252)
        else:
            metrics['sharpe_ratio'] = 0
        
        # Max drawdown
        running_max = df['strategy_equity'].cummax()
        drawdown = (df['strategy_equity'] - running_max) / running_max * 100
        metrics['max_drawdown'] = drawdown.min()
        
        # Number of trades
        metrics['num_trades'] = (df['trade'] != 0).sum() if 'trade' in df.columns else 0
        
        # Current signal
        if 'signal' in df.columns:
            metrics['current_signal'] = 'BUY' if df['signal'].iloc[-1] == 1 else 'SELL'
        else:
            metrics['current_signal'] = 'N/A'
    
    return metrics

def plot_price_chart(df):
    """Plot price chart with MA and trading signals"""
    fig = make_subplots(rows=1, cols=1)
    
    # Price line
    fig.add_trace(go.Scatter(
        x=df['trade_date'], 
        y=df['close'],
        mode='lines',
        name='Close Price',
        line=dict(color='blue', width=2)
    ))
    
    # MA lines if available
    if 'ma5' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['trade_date'], 
            y=df['ma5'],
            mode='lines',
            name='MA5',
            line=dict(color='orange', width=1.5, dash='dash')
        ))
    
    if 'ma20' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['trade_date'], 
            y=df['ma20'],
            mode='lines',
            name='MA20',
            line=dict(color='red', width=1.5, dash='dash')
        ))
    
    # Bollinger Bands if available
    if 'bb_upper' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['trade_date'], 
            y=df['bb_upper'],
            mode='lines',
            name='BB Upper',
            line=dict(color='gray', width=1, dash='dot')
        ))
        fig.add_trace(go.Scatter(
            x=df['trade_date'], 
            y=df['bb_lower'],
            mode='lines',
            name='BB Lower',
            line=dict(color='gray', width=1, dash='dot'),
            fill='tonexty',
            fillcolor='rgba(128,128,128,0.1)'
        ))
    
    # Trading signals
    if 'trade' in df.columns:
        buy_signals = df[df['trade'] == 1]
        sell_signals = df[df['trade'] == -1]
        
        fig.add_trace(go.Scatter(
            x=buy_signals['trade_date'],
            y=buy_signals['close'],
            mode='markers',
            name='Buy',
            marker=dict(symbol='triangle-up', size=12, color='green')
        ))
        
        fig.add_trace(go.Scatter(
            x=sell_signals['trade_date'],
            y=sell_signals['close'],
            mode='markers',
            name='Sell',
            marker=dict(symbol='triangle-down', size=12, color='red')
        ))
    
    fig.update_layout(
        title='Price Chart with Trading Signals',
        xaxis_title='Date',
        yaxis_title='Price (RMB)',
        hovermode='x unified',
        height=500
    )
    
    return fig

def plot_equity_curve(df):
    """Plot equity curve comparison"""
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df['trade_date'],
        y=df['strategy_equity'],
        mode='lines',
        name='Strategy',
        line=dict(color='green', width=2)
    ))
    
    fig.add_trace(go.Scatter(
        x=df['trade_date'],
        y=df['benchmark_equity'],
        mode='lines',
        name='Buy & Hold',
        line=dict(color='blue', width=2, dash='dash')
    ))
    
    fig.update_layout(
        title='Equity Curve: Strategy vs Buy & Hold',
        xaxis_title='Date',
        yaxis_title='Equity (RMB)',
        hovermode='x unified',
        height=400
    )
    
    return fig

def plot_drawdown(df):
    """Plot drawdown chart"""
    running_max = df['strategy_equity'].cummax()
    drawdown = (df['strategy_equity'] - running_max) / running_max * 100
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df['trade_date'],
        y=drawdown,
        mode='lines',
        name='Drawdown',
        line=dict(color='red', width=2),
        fill='tozeroy',
        fillcolor='rgba(255,0,0,0.2)'
    ))
    
    fig.update_layout(
        title='Strategy Drawdown',
        xaxis_title='Date',
        yaxis_title='Drawdown (%)',
        hovermode='x unified',
        height=300
    )
    
    return fig

# Main application
def main():
    st.title("📊 MA216 Quantitative Trading System Dashboard")
    st.markdown("---")
    
    # Sidebar
    st.sidebar.header("⚙️ Configuration")
    
    st.sidebar.subheader("Security")
    security = st.sidebar.text_input("Symbol", "510050.SH", disabled=True)
    
    st.sidebar.subheader("Strategy")
    strategy_type = st.sidebar.selectbox(
        "Strategy Type",
        ["Bollinger Bands (Best)", "MA5/20", "MA10/30", "MA20/60"]
    )
    
    st.sidebar.markdown("---")
    st.sidebar.info("""
    **Note**: This dashboard displays pre-computed results from Phase 7.
    Data is loaded from local files to avoid repeated API calls.
    """)
    
    # Load data
    df = load_data()
    
    if df is None:
        st.error("❌ Failed to load data. Please ensure Phase 7 has been completed.")
        return
    
    # Calculate metrics
    metrics = calculate_metrics(df)
    
    # Section 1: Market Overview
    st.header("🔍 Market Overview")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Latest Date", metrics['latest_date'])
    
    with col2:
        st.metric("Latest Price", f"{metrics['latest_price']:.3f} RMB")
    
    with col3:
        if metrics['latest_ma5']:
            st.metric("MA5", f"{metrics['latest_ma5']:.3f}")
        else:
            st.metric("BB Upper", "N/A")
    
    with col4:
        if metrics['latest_ma20']:
            st.metric("MA20", f"{metrics['latest_ma20']:.3f}")
        else:
            st.metric("BB Lower", "N/A")
    
    with col5:
        signal_color = "🟢" if metrics['current_signal'] == 'BUY' else "🔴"
        st.metric("Signal", f"{signal_color} {metrics['current_signal']}")
    
    st.markdown("---")
    
    # Section 2: Strategy Performance
    st.header("📈 Strategy Performance")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Total Return", 
            f"{metrics['total_return']:.2f}%",
            delta=f"{metrics['total_return'] - metrics['benchmark_return']:.2f}% vs Benchmark"
        )
        st.metric("Annual Return", f"{metrics['annual_return']:.2f}%")
    
    with col2:
        st.metric("Sharpe Ratio", f"{metrics['sharpe_ratio']:.4f}")
        st.metric("Volatility", f"{metrics['volatility']:.2f}%")
    
    with col3:
        st.metric("Max Drawdown", f"{metrics['max_drawdown']:.2f}%")
        st.metric("Number of Trades", f"{int(metrics['num_trades'])}")
    
    st.markdown("---")
    
    # Section 3: Price Chart
    st.header("📉 Price Chart with Trading Signals")
    fig_price = plot_price_chart(df)
    st.plotly_chart(fig_price, use_container_width=True)
    
    st.markdown("---")
    
    # Section 4: Equity Curve
    st.header("💰 Equity Curve Comparison")
    fig_equity = plot_equity_curve(df)
    st.plotly_chart(fig_equity, use_container_width=True)
    
    # Performance comparison table
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Strategy Performance")
        perf_data = {
            "Metric": ["Total Return", "Annual Return", "Sharpe Ratio", "Max Drawdown"],
            "Value": [
                f"{metrics['total_return']:.2f}%",
                f"{metrics['annual_return']:.2f}%",
                f"{metrics['sharpe_ratio']:.4f}",
                f"{metrics['max_drawdown']:.2f}%"
            ]
        }
        st.dataframe(pd.DataFrame(perf_data), use_container_width=True, hide_index=True)
    
    with col2:
        st.subheader("Benchmark Performance")
        bench_data = {
            "Metric": ["Total Return", "Strategy", "Excess Return"],
            "Value": [
                f"{metrics['benchmark_return']:.2f}%",
                f"{metrics['total_return']:.2f}%",
                f"{metrics['total_return'] - metrics['benchmark_return']:.2f}%"
            ]
        }
        st.dataframe(pd.DataFrame(bench_data), use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # Section 5: Drawdown Chart
    st.header("📊 Drawdown Analysis")
    fig_dd = plot_drawdown(df)
    st.plotly_chart(fig_dd, use_container_width=True)
    
    st.markdown("---")
    
    # Footer
    st.markdown("---")
    st.caption(f"""
    **MA216 Computational Finance - Project 1b**  
    Quantitative Trading System for 510050.SH (SSE 50 ETF)  
    Data Period: 2020-2025 (In-Sample)  
    Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """)

if __name__ == "__main__":
    main()
