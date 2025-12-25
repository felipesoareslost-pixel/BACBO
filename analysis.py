from collections import Counter
import math

def normalize_seq(seq):
    # seq expected like ['B','P','B','T',...]
    return [s.upper() for s in seq if s.upper() in ('B','P','T')]

def detect_manipulation(seq):
    seq = normalize_seq(seq)
    n = len(seq)
    if n == 0:
        return {'manipulated': False, 'reason': 'sem dados'}

    # Detect long runs of same result
    max_run = 1
    cur = 1
    for i in range(1, n):
        if seq[i] == seq[i-1]:
            cur += 1
            max_run = max(max_run, cur)
        else:
            cur = 1

    # Detect alternation pattern like B P B P ...
    alt_count = 0
    for i in range(2, n):
        if seq[i] == seq[i-2] and seq[i] != seq[i-1]:
            alt_count += 1

    # Heuristics thresholds
    manipulated = False
    reasons = []
    if max_run >= max(4, int(0.25 * n)):
        manipulated = True
        reasons.append(f'longa sequência de {max_run} repetidos')
    if alt_count >= max(3, int(0.2 * n)):
        manipulated = True
        reasons.append(f'alternância detectada ({alt_count} padrões)')

    return {'manipulated': manipulated, 'reasons': reasons, 'max_run': max_run, 'alt_count': alt_count}

def recommend(seq, lookback=20):
    seq = normalize_seq(seq)
    if not seq:
        return {'recommendation': 'N/A', 'confidence': 0.0, 'notes': 'Sem dados'}

    recent = seq[-lookback:]
    counts = Counter(recent)
    total = sum(counts.values())

    # Basic frequency probabilities
    pB = counts.get('B', 0) / total
    pP = counts.get('P', 0) / total
    pT = counts.get('T', 0) / total

    # Simple scoring: prefer highest probability but penalize if manipulated
    analysis = detect_manipulation(seq)
    penalty = 0.0
    if analysis['manipulated']:
        penalty = 0.2
    # compute confidence as normalized difference
    probs = {'BANKER': pB, 'PLAYER': pP, 'TIE': pT}
    best = max(probs.items(), key=lambda x: x[1])
    second = sorted(probs.items(), key=lambda x: x[1], reverse=True)[1]
    raw_conf = max(0.0, best[1] - second[1])

    # Two-mode confidences: agressivo (aceita sinais menores) e conservador (exige sinal forte)
    # agressivo: reduz penalidade e favorece decisões mesmo com menor diferença
    penalty_aggressive = penalty * 0.5
    conf_aggressive = max(0.0, min(1.0, raw_conf - penalty_aggressive + math.log1p(total)/10 + 0.05))

    # conservador: aumenta penalidade, exige diferença maior e mais dados
    penalty_conservative = penalty * 1.5
    sample_bonus = math.log1p(total)/12  # menor bônus por amostra
    conf_conservative = max(0.0, min(1.0, raw_conf - penalty_conservative + sample_bonus - 0.05))

    # regras para emitir recomendações: conservador só recomenda se conf alta, agressivo recomenda se conf moderada
    rec_aggressive = best[0] if conf_aggressive >= 0.05 else 'N/A'
    rec_conservative = best[0] if conf_conservative >= 0.25 else 'N/A'

    notes = []
    if analysis['manipulated']:
        notes.append('Possível manipulação: ' + '; '.join(analysis.get('reasons', [])))
    else:
        notes.append('Sem sinais fortes de manipulação')

    return {
        'modes': {
            'aggressive': {'recommendation': rec_aggressive, 'confidence': round(conf_aggressive, 3)},
            'conservative': {'recommendation': rec_conservative, 'confidence': round(conf_conservative, 3)}
        },
        'probabilities': probs,
        'notes': notes,
        'analysis': analysis
    }

if __name__ == '__main__':
    # exemplo rápido
    seq = ['B','B','B','B','B','P','P','T','B','P','B','P']
    print(detect_manipulation(seq))
    print(recommend(seq))
