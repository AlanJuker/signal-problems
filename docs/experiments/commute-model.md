# Can a model beat the historical frequency? (#21)

The commute check reports a historical frequency: the share of past days on which a trip's stations had a 5+
minute delay in its window. Before replacing it, this experiment measures whether a model predicts better.

Reproduce with `uv run --group ml signal-problems model-eval` (about 30 s, after `ingest --history`).

## Setup

Decided in the issue before any result was seen.

- **Unit**: a station, a date and an hour of service (0–1 a.m. and 5 a.m.–midnight). **Label**: at least one
  5+ minute delay at that station in that hour.
- **Temporal split**: train 2014–2023 (5.4 M cells), validation 2024 (0.5 M), test January 2025 – August 2026
  (0.9 M). Nothing is shuffled, so every score is on data later than what the method learned from.
- **Baselines**: the frequency per station, weekday and hour, smoothed toward the overall rate, (1) over every
  year before the test period and (2) over 2024 only.
- **Model**: scikit-learn's histogram gradient boosting on station, weekday, hour, month, the station's 5+
  minute delays in the previous 7 and 28 days, and the whole network's in the previous 7 days. Recent counts
  only use days before the cell's date (tested). The number of boosting rounds is picked on 2024, then the
  model is refit on 2014–2024.

## Results on January 2025 – August 2026

0.88% of cells have a 5+ minute delay.

| Method | Log loss ↓ | Brier ↓ | ROC AUC ↑ | PR AUC ↑ |
|---|---|---|---|---|
| Frequency, 2014–2024 | 0.05077 | 0.008656 | 0.638 | 0.0186 |
| Frequency, 2024 only | 0.05212 | 0.008724 | 0.582 | 0.0142 |
| **Gradient boosting** | **0.04859** | **0.008642** | **0.665** | **0.0203** |

The model's probabilities are well calibrated: in the top tenth of cells it predicts 2.27% and 2.23% happen;
in the bottom tenth, 0.26% and 0.25%.

## Decision

The model meets the rule set in #21: it beats both baselines on log loss (−4.3%) and PR AUC (+9%) on the test
period, so it's a candidate for the commute check.

What the numbers don't say: with ROC AUC 0.67, **delays are hard to predict hour by hour**. The model ranks
risk somewhat better than history alone, mostly from recent activity at the station and on the network. That's
a modest gain, so the frequency's simple explanation ("24 of 87 Fridays") stays in the product either way.

## Limitations

- Labels count logged incidents at a station. Delays logged on a segment or line-wide aren't attributed to
  stations yet.
- The 2024-only baseline is noisier than the full history: a single year gives few cells per station,
  weekday and hour.
- Delays doubled between 2014 and 2024, so a model trained on older years has to lean on recent counts. They
  carry most of its gain.

## Serving (#25)

`train-model` refits the model on every day in the data, with the 50 boosting rounds chosen here, and stores its
probabilities for the seven days after the data ends, per station and hour. Recent counts are the ones known on
the last day, since later days haven't happened yet.

The commute check combines a trip's cells into the chance of at least one 5+ minute delay: each station's hourly
probability, weighted by the share of that hour inside the trip's window, assuming delays spread evenly within an
hour. Cells are treated as independent, which overstates the chance a little when one disruption hits several
stations. On the full history, the model's chance lands close to what happened since 2025:

| Trip | Model, week after the data | 5+ minute delay since 2025 |
|---|---|---|
| Kipling → St George, Monday 07:45 | 9.4% | 8 of 87 Mondays (9.2%) |
| Bloor-Yonge → Union, Friday 08:15 | 4.2% | 3 of 87 Fridays (3.4%) |
| Finch → Eglinton, Wednesday 17:30 | 4.1% | 3 of 87 Wednesdays (3.4%) |

