import pandas as pd
import numpy as np
import re
import matplotlib.pyplot as plt
import os

def parse_tos_chain(filepath):
    """
    Parses a standard ThinkOrSwim option chain CSV export.
    Returns a DataFrame of call options with Greeks.
    """
    options = []
    current_expiry = None
    current_dte = None

    if not os.path.exists(filepath):
        parent_path = os.path.join("..", filepath)
        if os.path.exists(parent_path):
            filepath = parent_path
        else:
            return pd.DataFrame()

    with open(filepath, 'r') as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        match = re.search(r'(\d{1,2} [A-Z]{3} \d{2})\s+\((\d+)\)', line)
        if match:
            current_expiry = match.group(1)
            current_dte = int(match.group(2))
            continue

        parts = line.split(',')
        if len(parts) >= 15 and current_expiry is not None:
            try:
                strike_str = parts[11].strip()
                if not strike_str or not strike_str.replace('.','',1).isdigit():
                    continue
                strike = float(strike_str)

                call_bid = float(parts[6]) if parts[6].strip() else np.nan
                call_ask = float(parts[8]) if parts[8].strip() else np.nan
                call_delta = float(parts[2]) if parts[2].strip() else np.nan
                call_theta = float(parts[4]) if parts[4].strip() else np.nan

                if not np.isnan(call_bid) and not np.isnan(call_ask):
                    options.append({
                        'Expiration': current_expiry,
                        'DTE': current_dte,
                        'Type': 'Call',
                        'Strike': strike,
                        'Mid': (call_bid + call_ask) / 2,
                        'Delta': abs(call_delta),
                        'Theta': call_theta
                    })
            except (ValueError, IndexError):
                pass

    return pd.DataFrame(options).dropna(subset=['Mid', 'Delta'])
