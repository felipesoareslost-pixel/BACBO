import sqlite3
import json
from collections import defaultdict

DB_FILE = 'sistemabacbo.db'

def load_history():
    db = sqlite3.connect(DB_FILE)
    db.row_factory = sqlite3.Row
    cur = db.cursor()
    cur.execute('SELECT timestamp, sequence, result_json FROM history ORDER BY id ASC')
    rows = [dict(r) for r in cur.fetchall()]
    # parse sequences into token lists
    for r in rows:
        r['tokens'] = [t for t in r['sequence'].split() if t]
        try:
            r['result'] = json.loads(r['result_json'])
        except Exception:
            r['result'] = {}
    return rows

def infer_next_results(rows):
    # Heuristic: build a merged timeline by appending non-overlapping tails
    timeline = []
    maps = []  # map entry index -> last index in timeline for that entry's sequence
    for i, r in enumerate(rows):
        tokens = r['tokens']
        if i == 0:
            timeline = tokens.copy()
            maps.append(len(timeline)-1 if timeline else -1)
            continue
        # find largest prefix of tokens that matches a suffix of timeline
        m = 0
        max_m = min(len(timeline), len(tokens))
        for k in range(max_m, 0, -1):
            if timeline[-k:] == tokens[:k]:
                m = k
                break
        # append remaining
        append = tokens[m:]
        for t in append:
            timeline.append(t)
        maps.append(len(timeline)-1 if timeline else -1)

    # Now infer next result for each row: if there is element after maps[i], that's the next
    inferred = []
    for i, r in enumerate(rows):
        last_idx = maps[i]
        next_token = None
        if last_idx is not None and last_idx + 1 < len(timeline):
            next_token = timeline[last_idx + 1]
        inferred.append({'timestamp': r['timestamp'], 'sequence': r['sequence'], 'result': r.get('result', {}), 'next': next_token})
    return inferred

def simulate(inferred, stake_fraction=0.01, initial_bank=1000.0, thresholds={'aggressive':0.25,'conservative':0.4}):
    results = {}
    payout = {'BANKER':0.95, 'PLAYER':1.0, 'TIE':8.0}
    for mode in ['aggressive','conservative']:
        bank = initial_bank
        peak = bank
        max_dd = 0.0
        bets = 0
        wins = 0
        net = 0.0
        history = []
        for entry in inferred:
            next_out = entry['next']  # 'B'/'P'/'T' or None
            if not next_out:
                continue
            mode_info = entry['result'].get('modes', {}).get(mode, {})
            rec = mode_info.get('recommendation','N/A')
            conf = mode_info.get('confidence',0.0)
            if rec == 'N/A' or conf < thresholds.get(mode, 0.0):
                continue
            # place bet
            stake = initial_bank * stake_fraction
            bets += 1
            bet_side = rec  # 'BANKER'/'PLAYER'/'TIE'
            profit = 0.0
            if bet_side == 'BANKER':
                if next_out == 'B':
                    profit = stake * payout['BANKER']
                elif next_out == 'T':
                    profit = 0.0
                else:
                    profit = -stake
            elif bet_side == 'PLAYER':
                if next_out == 'P':
                    profit = stake * payout['PLAYER']
                elif next_out == 'T':
                    profit = 0.0
                else:
                    profit = -stake
            elif bet_side == 'TIE':
                if next_out == 'T':
                    profit = stake * payout['TIE']
                else:
                    profit = -stake
            bank += profit
            net += profit
            if profit > 0:
                wins += 1
            peak = max(peak, bank)
            dd = (peak - bank)
            max_dd = max(max_dd, dd)
            history.append({'timestamp': entry['timestamp'], 'bet': bet_side, 'next': next_out, 'profit': profit, 'bank': bank, 'conf': conf})
        roi = (bank - initial_bank) / initial_bank if initial_bank else 0.0
        win_rate = (wins / bets) if bets else 0.0
        results[mode] = {'bets': bets, 'wins': wins, 'win_rate': round(win_rate,3), 'net': round(net,2), 'roi': round(roi,4), 'max_drawdown': round(max_dd,2), 'final_bank': round(bank,2), 'history': history}
    return results

def report(results):
    for mode, r in results.items():
        print(f"Mode: {mode}")
        print(f"  Bets: {r['bets']}")
        print(f"  Wins: {r['wins']}")
        print(f"  Win rate: {r['win_rate']*100:.1f}%")
        print(f"  Net P&L: {r['net']}")
        print(f"  ROI: {r['roi']*100:.2f}%")
        print(f"  Max drawdown: {r['max_drawdown']}")
        print(f"  Final bank: {r['final_bank']}\n")

if __name__ == '__main__':
    rows = load_history()
    inferred = infer_next_results(rows)
    # use multiple stake sizes
    stakes = [0.01, 0.02, 0.05]
    for s in stakes:
        print('--- Stake fraction:', s, '---')
        res = simulate(inferred, stake_fraction=s)
        report(res)
