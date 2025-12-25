import csv
from itertools import product
from backtest import load_history, infer_next_results, simulate

def run_sweep(aggr_range, cons_range, stakes, initial_bank=1000.0):
    rows = load_history()
    inferred = infer_next_results(rows)
    results = []
    for a_thr, c_thr, stake in product(aggr_range, cons_range, stakes):
        thresholds = {'aggressive': a_thr, 'conservative': c_thr}
        res = simulate(inferred, stake_fraction=stake, initial_bank=initial_bank, thresholds=thresholds)
        # record key metrics for both modes
        for mode in ['aggressive','conservative']:
            r = res.get(mode, {})
            results.append({
                'aggressive_thr': a_thr,
                'conservative_thr': c_thr,
                'stake': stake,
                'mode': mode,
                'bets': r.get('bets',0),
                'wins': r.get('wins',0),
                'win_rate': r.get('win_rate',0.0),
                'net': r.get('net',0.0),
                'roi': r.get('roi',0.0),
                'final_bank': r.get('final_bank',initial_bank),
                'max_drawdown': r.get('max_drawdown',0.0)
            })
    return results

def save_csv(rows, path='sweep_report.csv'):
    keys = ['aggressive_thr','conservative_thr','stake','mode','bets','wins','win_rate','net','roi','final_bank','max_drawdown']
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

def print_top(rows, top=10, sort_key='roi'):
    sorted_rows = sorted(rows, key=lambda x: x.get(sort_key, 0), reverse=True)
    print(f'Top {top} by {sort_key}:')
    for r in sorted_rows[:top]:
        print(r)

if __name__ == '__main__':
    # default ranges
    aggr_range = [0.15, 0.20, 0.25, 0.30, 0.35]
    cons_range = [0.30, 0.35, 0.40, 0.45, 0.50]
    stakes = [0.01, 0.02, 0.05]
    print('Running sweep with ranges:')
    print('aggr:', aggr_range)
    print('cons:', cons_range)
    print('stakes:', stakes)
    rows = run_sweep(aggr_range, cons_range, stakes)
    save_csv(rows)
    print('Saved sweep_report.csv')
    print_top(rows, top=10, sort_key='roi')
