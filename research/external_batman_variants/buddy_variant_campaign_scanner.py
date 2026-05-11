"""External reference implementation preserved for research purposes only.

Not production architecture.
"""

import sys
import subprocess
import pandas as pd
import numpy as np
import yfinance as yf
from scipy.optimize import differential_evolution


def get_vix_rank():
    vix = yf.download("^VIX", period="2y", interval="1d", progress=False)
    if vix.empty:
        return 0.5

    current_vix = vix['Close'].iloc[-1]
    if isinstance(current_vix, pd.Series):
        current_vix = current_vix.iloc[0]

    rank = (vix['Close'] < current_vix).mean()
    if isinstance(rank, pd.Series):
        rank = rank.iloc[0]

    return rank


def evaluate_configuration(params, df, front_dte, back_dte, target_net_delta=3.0):
    target_l1_delta = params[0] / 100.0
    offset_l2 = params[1] / 100.0

    front_chain = df[df['DTE'] == front_dte]
    back_chain = df[df['DTE'] == back_dte]

    l1_idx = (front_chain['Delta'] - target_l1_delta).abs().argsort()[:1]
    if len(l1_idx) == 0:
        return 1e9

    leg1 = front_chain.iloc[l1_idx].iloc[0]

    target_l2_delta = leg1['Delta'] - offset_l2
    l2_idx = (back_chain['Delta'] - target_l2_delta).abs().argsort()[:1]
    if len(l2_idx) == 0:
        return 1e9

    leg2 = back_chain.iloc[l2_idx].iloc[0]

    required_d3 = (-leg1['Delta'] * 100) + (2 * leg2['Delta'] * 100) - target_net_delta
    if required_d3 <= 0:
        return 1e9

    l3_idx = (front_chain['Delta'] - (required_d3 / 100.0)).abs().argsort()[:1]
    if len(l3_idx) == 0:
        return 1e9

    return 0.0
