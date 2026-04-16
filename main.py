import numpy as np
from scipy.stats import norm 
import matplotlib.pyplot as plt

# ==========================================
# 1. PARAMETERS & SETTINGS
# ==========================================
S = 100       # Current Stock Price
K = 100       # Strike Price
T = 1.0       # Time to Expiration (Years)
r = 0.05      # Risk-Free Interest Rate
sigma = 0.20  # Volatility (20%)
barrier = 80  # Barrier Trapdoor limit

num_paths = 10000 
steps_per_year = 252 

print("System parameters loaded.")

# ==========================================
# 2. BLACK-SCHOLES ENGINE & GREEKS
# ==========================================
def black_scholes(S, K, T, r, sigma, option_type="call"):
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - (sigma * np.sqrt(T))

    if option_type == "call":
        price = (S * norm.cdf(d1)) - (K * np.exp(-r * T) * norm.cdf(d2))
        delta = norm.cdf(d1)
        theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) - r * K * np.exp(-r * T) * norm.cdf(d2)) / 365
        rho = (K * T * np.exp(-r * T) * norm.cdf(d2)) / 100
    elif option_type == "put":
        price = (K * np.exp(-r * T) * norm.cdf(-d2)) - (S * norm.cdf(-d1))
        delta = norm.cdf(d1) - 1
        theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) + r * K * np.exp(-r * T) * norm.cdf(-d2)) / 365
        rho = (-K * T * np.exp(-r * T) * norm.cdf(-d2)) / 100

    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    vega = (S * norm.pdf(d1) * np.sqrt(T)) / 100

    return {
        "Price": price,
        "Delta": delta,
        "Gamma": gamma,
        "Theta": theta,
        "Vega": vega,
        "Rho": rho
    }

bs_results = black_scholes(S, K, T, r, sigma, option_type="call")
bs_price = bs_results["Price"]
print("Black-Scholes engine calculated.")

# ==========================================
# 3. MONTE CARLO ENGINE (VANILLA & EXOTICS)
# ==========================================
def exotic_monte_carlo(S, K, T, r, sigma, barrier=None, option_type="call", num_simulations=10000, steps=252):
    dt = T / steps 
    shocks = np.random.standard_normal((num_simulations, steps))
    
    daily_drift = (r - 0.5 * sigma ** 2) * dt
    daily_shock_impact = sigma * np.sqrt(dt) * shocks
    
    running_totals = np.cumsum(daily_drift + daily_shock_impact, axis=1)
    price_paths = S * np.exp(running_totals)

    ST = price_paths[:, -1]

    # Return pure paths for the visualization if vanilla
    if option_type == "vanilla_call":
        payoffs = np.maximum(ST - K, 0)
        return (np.mean(payoffs) * np.exp(-r * T)), price_paths

    if option_type == "asian":
        average_prices = np.mean(price_paths, axis=1)
        payoffs = np.maximum(average_prices - K, 0)
    elif option_type == "lookback":
        lowest_prices = np.min(price_paths, axis=1)
        payoffs = np.maximum(ST - lowest_prices, 0)
    elif option_type == "barrier":
        lowest_prices = np.min(price_paths, axis=1)
        normal_payoffs = np.maximum(ST - K, 0)
        payoffs = np.where(lowest_prices < barrier, 0, normal_payoffs)

    return np.mean(payoffs) * np.exp(-r * T)

mc_price, paths = exotic_monte_carlo(S, K, T, r, sigma, option_type="vanilla_call", num_simulations=num_paths, steps=steps_per_year)
asian_price = exotic_monte_carlo(S, K, T, r, sigma, option_type="asian", num_simulations=num_paths)
barrier_price = exotic_monte_carlo(S, K, T, r, sigma, barrier=barrier, option_type="barrier", num_simulations=num_paths)
lookback_price = exotic_monte_carlo(S, K, T, r, sigma, option_type="lookback", num_simulations=num_paths)
print("Monte Carlo stochastic trajectories completed.")

# ==========================================
# 4. RESULTS DASHBOARD
# ==========================================
print("\n" + "="*45)
print("       QUANTITATIVE OPTIONS PRICING ENGINE         ")
print("="*45)
print(f"Underlying Price (S):      ${S:,.2f}")
print(f"Model Option Strike (K):   ${K:,.2f}")
print(f"Time to Expiry (T):        {T} Years")
print(f"Market Volatility (Sigma): {sigma*100:.1f}%\n")
print("-" * 45)
print("            CLOSED-FORM GREEKS             ")
print("-" * 45)
for key, value in bs_results.items():
    print(f"{key}: {value:.4f}")
print("-" * 45)
print("             EXOTIC PRICING MULTIPLIERS    ")
print("-" * 45)
print(f"Vanilla Call (BS):      ${bs_price:.2f}")
print(f"Monte Carlo Estimate:   ${mc_price:.2f}")
print(f"Asian Average Option:   ${asian_price:.2f}")
print(f"Barrier Option ($80):   ${barrier_price:.2f}")
print(f"Lookback Call:          ${lookback_price:.2f}")
print("="*45 + "\n")

# ==========================================
# 5. MATPLOTLIB VISUALIZATIONS
# ==========================================
print("Rendering Visualizations Dashboard...")

plt.style.use('dark_background')
fig = plt.figure(figsize=(16, 10))
fig.suptitle('Options Pricing & Risk Analytics Dashboard', fontsize=18, fontweight='bold', y=0.98)

# Plot 1: Monte Carlo Price Paths (Top Left)
plt.subplot(2, 2, 1)
for i in range(100):
    plt.plot(paths[i, :], lw=1, alpha=0.1, color='cyan')
plt.axhline(y=K, color='yellow', linestyle='--', label='Strike Price')
plt.axhline(y=barrier, color='red', linestyle='--', label='Trapdoor Barrier')
plt.title(f'Monte Carlo Stochastic Trajectories (Sample: 100/{num_paths})')
plt.xlabel('Days')
plt.ylabel('Simulated Stock Price ($)')
plt.legend()

# Plot 2: Convergence (Top Right)
plt.subplot(2, 2, 2)
sim_counts = [10, 50, 100, 500, 1000, 5000, 10000]
conv_prices = []
for count in sim_counts:
    px, _ = exotic_monte_carlo(S, K, T, r, sigma, option_type="vanilla_call", num_simulations=count, steps=steps_per_year)
    conv_prices.append(px)
plt.plot(sim_counts, conv_prices, color='orange', label='MC Estimate', marker='o')
plt.axhline(y=bs_price, color='green', linestyle='--', label=f'Black-Scholes True')
plt.xscale('log')
plt.title('Monte Carlo Convergence (Law of Large Numbers)')
plt.xlabel('Simulations (Log Scale)')
plt.ylabel('Calculated Price ($)')
plt.legend()

# Plot 3: Option Price vs Volatility (Bottom Left)
plt.subplot(2, 2, 3)
vols = np.linspace(0.05, 0.80, 50)
call_prices = [black_scholes(S, K, T, r, v, "call")["Price"] for v in vols]
put_prices = [black_scholes(S, K, T, r, v, "put")["Price"] for v in vols]

plt.plot(vols * 100, call_prices, label='Call Value', color='#00FF00', lw=2)
plt.plot(vols * 100, put_prices, label='Put Value', color='#FF0000', lw=2)
plt.title('Option Premium vs. Market Volatility (Vega)')
plt.xlabel('Volatility (Sigma %)')
plt.ylabel('Option Premium ($)')
plt.legend()

# Plot 4: Dynamic Options Heatmap (Bottom Right)
plt.subplot(2, 2, 4)
strikes = np.linspace(80, 120, 20)
times = np.linspace(0.1, 2.0, 20)
heatmap_grid = np.zeros((len(times), len(strikes)))

for i, t_exp in enumerate(times):
    for j, strk in enumerate(strikes):
        heatmap_grid[i, j] = black_scholes(S, strk, t_exp, r, sigma, "call")["Price"]

cax = plt.imshow(heatmap_grid, cmap='magma', origin='lower', aspect='auto', extent=[80, 120, 0.1, 2.0])
plt.colorbar(cax, label="Call Option Price ($)")
plt.title('Call Option Value Heatmap')
plt.xlabel('Strike Price ($)')
plt.ylabel('Time to Expiration (Years)')

plt.tight_layout()
plt.subplots_adjust(top=0.92)
plt.show()
