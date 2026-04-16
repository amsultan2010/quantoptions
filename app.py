import os
import json
import traceback

import numpy as np
from scipy.stats import norm
import plotly.graph_objects as go
import plotly.utils
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


# ── Black-Scholes ──────────────────────────────────────────────────────────────

def black_scholes(S, K, T, r, sigma, option_type="call"):
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)

    if option_type == "call":
        price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        delta = norm.cdf(d1)
        theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) - r * K * np.exp(-r * T) * norm.cdf(d2)) / 365
        rho   = K * T * np.exp(-r * T) * norm.cdf(d2) / 100
    else:
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        delta = norm.cdf(d1) - 1
        theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) + r * K * np.exp(-r * T) * norm.cdf(-d2)) / 365
        rho   = -K * T * np.exp(-r * T) * norm.cdf(-d2) / 100

    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    vega  = S * norm.pdf(d1) * np.sqrt(T) / 100

    return dict(price=float(price), delta=float(delta), gamma=float(gamma),
                theta=float(theta), vega=float(vega), rho=float(rho))


# ── Monte Carlo engines ────────────────────────────────────────────────────────

def _paths(S, T, r, sigma, n, steps=252):
    dt = T / steps
    shocks = np.random.standard_normal((n, steps))
    log_ret = (r - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * shocks
    return S * np.exp(np.cumsum(log_ret, axis=1))


def mc_vanilla(S, K, T, r, sigma, option_type, n, steps=252):
    pp = _paths(S, T, r, sigma, n, steps)
    ST = pp[:, -1]
    payoffs = np.maximum(ST - K, 0) if option_type == "call" else np.maximum(K - ST, 0)
    return float(np.mean(payoffs) * np.exp(-r * T)), pp


def mc_asian(S, K, T, r, sigma, n, steps=252):
    pp = _paths(S, T, r, sigma, n, steps)
    avg = np.mean(pp, axis=1)
    return float(np.mean(np.maximum(avg - K, 0)) * np.exp(-r * T))


def mc_lookback(S, K, T, r, sigma, n, steps=252):
    pp = _paths(S, T, r, sigma, n, steps)
    ST  = pp[:, -1]
    mn  = np.min(pp, axis=1)
    return float(np.mean(np.maximum(ST - mn, 0)) * np.exp(-r * T))


def mc_barrier(S, K, T, r, sigma, barrier, n, steps=252):
    pp = _paths(S, T, r, sigma, n, steps)
    ST  = pp[:, -1]
    mn  = np.min(pp, axis=1)
    raw = np.maximum(ST - K, 0)
    return float(np.mean(np.where(mn < barrier, 0, raw)) * np.exp(-r * T))


# ── Chart helpers ──────────────────────────────────────────────────────────────

_BASE_LAYOUT = dict(
    paper_bgcolor="#0d0d1a",
    plot_bgcolor="#07070f",
    font=dict(color="#94a3b8", family="Inter, system-ui, sans-serif"),
    margin=dict(l=55, r=60, t=55, b=48),
    height=370,
    xaxis=dict(gridcolor="#151525", zerolinecolor="#151525", color="#64748b"),
    yaxis=dict(gridcolor="#151525", zerolinecolor="#151525", color="#64748b"),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#e2e8f0")),
    hoverlabel=dict(bgcolor="#13132a", bordercolor="#8b5cf6", font=dict(color="#f0eeff")),
)


def _fig_json(fig):
    return json.loads(json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder))


def build_paths_chart(paths, K, barrier):
    fig = go.Figure()
    n = min(100, paths.shape[0])
    days = np.arange(paths.shape[1])

    for i in range(n):
        fig.add_trace(go.Scatter(
            x=days, y=paths[i], mode="lines",
            line=dict(width=0.65, color="rgba(139,92,246,0.20)"),
            showlegend=False, hoverinfo="skip",
        ))

    fig.add_hline(y=K, line_dash="dash", line_color="#fbbf24",
                  annotation_text=f"Strike ${K:,.0f}",
                  annotation_position="top right",
                  annotation_font=dict(color="#fbbf24", size=11))
    if barrier and barrier > 0:
        fig.add_hline(y=barrier, line_dash="dash", line_color="#f43f5e",
                      annotation_text=f"Barrier ${barrier:,.0f}",
                      annotation_position="bottom right",
                      annotation_font=dict(color="#f43f5e", size=11))

    layout = dict(**_BASE_LAYOUT)
    layout["title"] = dict(text="Simulated Stock Price Paths", font=dict(size=14, color="#e2e8f0"), x=0)
    layout["xaxis"]  = dict(**_BASE_LAYOUT["xaxis"], title="Trading Days")
    layout["yaxis"]  = dict(**_BASE_LAYOUT["yaxis"], title="Stock Price ($)")
    fig.update_layout(**layout)
    return _fig_json(fig)


def build_vega_chart(S, K, T, r):
    vols = np.linspace(0.05, 0.80, 60)
    call_px = [black_scholes(S, K, T, r, v, "call")["price"] for v in vols]
    put_px  = [black_scholes(S, K, T, r, v, "put")["price"]  for v in vols]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=vols * 100, y=call_px, name="Call",
                             line=dict(color="#8b5cf6", width=2.5), mode="lines"))
    fig.add_trace(go.Scatter(x=vols * 100, y=put_px,  name="Put",
                             line=dict(color="#f43f5e", width=2.5), mode="lines"))

    layout = dict(**_BASE_LAYOUT)
    layout["title"] = dict(text="How Volatility Affects Option Value (Vega)", font=dict(size=14, color="#e2e8f0"), x=0)
    layout["xaxis"]  = dict(**_BASE_LAYOUT["xaxis"], title="Volatility (%)")
    layout["yaxis"]  = dict(**_BASE_LAYOUT["yaxis"], title="Option Price ($)")
    fig.update_layout(**layout)
    return _fig_json(fig)


def build_heatmap_chart(S, r, sigma):
    # Strikes centered around current price; times from 1 month to 2.5 years
    strikes = np.linspace(S * 0.65, S * 1.35, 28)
    times   = np.linspace(0.08, 2.5, 28)
    grid    = np.array([[black_scholes(S, k, t, r, sigma, "call")["price"]
                         for k in strikes] for t in times])

    fig = go.Figure(data=go.Heatmap(
        z=grid, x=np.round(strikes, 1), y=np.round(times, 2),
        colorscale=[
            [0.00, "#07070f"],
            [0.15, "#2d1b69"],
            [0.40, "#5b21b6"],
            [0.70, "#8b5cf6"],
            [0.88, "#c4b5fd"],
            [1.00, "#ede9fe"],
        ],
        colorbar=dict(
            title=dict(text="Call Price ($)", font=dict(color="#64748b", size=11)),
            tickfont=dict(color="#64748b"),
        ),
    ))

    layout = dict(**_BASE_LAYOUT)
    layout["title"] = dict(text="Option Value Surface", font=dict(size=14, color="#e2e8f0"), x=0)
    layout["xaxis"]  = dict(**_BASE_LAYOUT["xaxis"], title="Strike Price ($)")
    layout["yaxis"]  = dict(**_BASE_LAYOUT["yaxis"], title="Time to Expiration (Years)")
    fig.update_layout(**layout)
    return _fig_json(fig)


def build_convergence_chart(S, K, T, r, sigma, option_type, max_sims):
    bs_price = black_scholes(S, K, T, r, sigma, option_type)["price"]

    all_checkpoints = [10, 50, 100, 250, 500, 1000, 2500, 5000,
                       10000, 25000, 50000, 100000]
    checkpoints = [c for c in all_checkpoints if c <= max_sims]
    if not checkpoints:
        checkpoints = [max_sims]

    # One big batch — subsample for speed
    big_n   = max(checkpoints)
    pp      = _paths(S, T, r, sigma, big_n)
    ST_all  = pp[:, -1]

    conv_prices = []
    for n in checkpoints:
        sub = ST_all[:n]
        payoffs = np.maximum(sub - K, 0) if option_type == "call" else np.maximum(K - sub, 0)
        conv_prices.append(float(np.mean(payoffs) * np.exp(-r * T)))

    fig = go.Figure()

    # ±5% convergence band
    fig.add_trace(go.Scatter(
        x=checkpoints + checkpoints[::-1],
        y=[bs_price * 1.05] * len(checkpoints) + [bs_price * 0.95] * len(checkpoints),
        fill="toself", fillcolor="rgba(16,185,129,0.05)",
        line=dict(color="rgba(0,0,0,0)"), showlegend=False, hoverinfo="skip",
    ))

    fig.add_trace(go.Scatter(
        x=checkpoints, y=conv_prices, name="MC Estimate",
        mode="lines+markers",
        line=dict(color="#8b5cf6", width=2.5),
        marker=dict(size=7, color="#a78bfa", symbol="circle",
                    line=dict(color="#6d28d9", width=1.5)),
    ))

    fig.add_hline(y=bs_price, line_dash="dash", line_color="#10b981",
                  annotation_text=f"Black-Scholes: ${bs_price:.4f}",
                  annotation_position="top right",
                  annotation_font=dict(color="#10b981", size=11))

    layout = dict(**_BASE_LAYOUT)
    layout["title"]  = dict(text="Monte Carlo Convergence (Law of Large Numbers)", font=dict(size=14, color="#e2e8f0"), x=0)
    layout["xaxis"]  = dict(**_BASE_LAYOUT["xaxis"], title="Number of Simulations (log scale)", type="log")
    layout["yaxis"]  = dict(**_BASE_LAYOUT["yaxis"], title="Estimated Option Price ($)")
    layout["height"] = 420
    fig.update_layout(**layout)

    return _fig_json(fig), bs_price, conv_prices[-1]


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/calculate", methods=["POST"])
def calculate():
    try:
        d = request.get_json(force=True)
        S      = float(d["S"])
        K      = float(d["K"])
        T      = float(d["T"])
        r      = float(d["r"])
        sigma  = float(d["sigma"])
        barrier = float(d.get("barrier", 80))
        n_sims  = int(d.get("num_simulations", 10000))
        otype   = d.get("option_type", "call").lower()

        if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
            return jsonify({"error": "Stock price, strike, time to expiry, and volatility must all be positive."}), 400
        if sigma >= 5:
            return jsonify({"error": "Volatility should be a decimal fraction (e.g. 0.20 for 20%, not 20)."}), 400
        if not (1000 <= n_sims <= 100000):
            return jsonify({"error": "Simulations must be between 1,000 and 100,000."}), 400
        if otype not in ("call", "put"):
            return jsonify({"error": "option_type must be 'call' or 'put'."}), 400

        bs = black_scholes(S, K, T, r, sigma, otype)
        mc_price, paths = mc_vanilla(S, K, T, r, sigma, otype, n_sims)

        exotic_n = min(n_sims, 20000)
        asian    = mc_asian(S, K, T, r, sigma, exotic_n)
        barrier_p = mc_barrier(S, K, T, r, sigma, barrier, exotic_n)
        lookback = mc_lookback(S, K, T, r, sigma, exotic_n)

        return jsonify({
            "bs_price":  bs["price"],
            "mc_price":  mc_price,
            "greeks":    {k: bs[k] for k in ("delta", "gamma", "theta", "vega", "rho")},
            "exotics": {
                "vanilla_bs":  bs["price"],
                "vanilla_mc":  mc_price,
                "asian":       asian,
                "barrier":     barrier_p,
                "lookback":    lookback,
            },
            "charts": {
                "paths":   build_paths_chart(paths, K, barrier),
                "vega":    build_vega_chart(S, K, T, r),
                "heatmap": build_heatmap_chart(S, r, sigma),
            },
        })

    except KeyError as e:
        return jsonify({"error": f"Missing required field: {e}"}), 400
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "Internal server error."}), 500


@app.route("/api/convergence", methods=["POST"])
def convergence():
    try:
        d = request.get_json(force=True)
        S      = float(d["S"])
        K      = float(d["K"])
        T      = float(d["T"])
        r      = float(d["r"])
        sigma  = float(d["sigma"])
        n_sims  = int(d.get("num_simulations", 10000))
        otype   = d.get("option_type", "call").lower()

        chart, bs_price, final_mc = build_convergence_chart(S, K, T, r, sigma, otype, n_sims)

        return jsonify({"chart": chart, "bs_price": bs_price, "final_mc": final_mc})

    except Exception:
        traceback.print_exc()
        return jsonify({"error": "Internal server error."}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5001)
