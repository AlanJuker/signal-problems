# Can a model beat the historical frequency? (#21)

The commute check reports a historical frequency: the share of past days on which a trip's stations had a 5+
minute delay in its window. Before replacing it, this experiment measures whether a model predicts better.

Reproduce with `uv run --group ml signal-problems model-eval` (about 45 s, after `ingest --history`).

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
probabilities for the seven days after the data ends, per station and hour, scaled by the
[hourly correction](#hourly-correction-36). Recent counts are the ones known on the last day, since later days
haven't happened yet.

The commute check combines a trip's cells into the chance of at least one 5+ minute delay: each station's hourly
probability, weighted by the share of that hour inside the trip's window, assuming delays spread evenly within an
hour. Cells are treated as independent; [Whole trips](#whole-trips) measures what that costs. On the full
history, through 30 September 2026:

| Trip | Model, week after the data | 5+ minute delay since 2025 |
|---|---|---|
| Kipling → St George, Monday 07:45 | 7.9% | 6 of 91 Mondays (6.6%) |
| Bloor-Yonge → Union, Friday 08:15 | 5.1% | 3 of 91 Fridays (3.3%) |
| Finch → Eglinton, Wednesday 17:30 | 4.5% | 3 of 92 Wednesdays (3.3%) |

Single trips are only a sanity check: 3 days in 91 fits a true chance anywhere from 0.7% to 9.3% (95%
interval). [Whole trips](#whole-trips) scores 712 trips over every test day.


## Whole trips

The scores above are per station and hour, but the commute check shows one chance per trip. This checks that
chance against what happened. The setup was fixed before the results:

- **Trips**: every run of 3, 6 and 10 neighbouring stations on each line, leaving at 08:00, 12:00, 17:30 and
  21:00. That's 712 trips, each scored on all 638 days of the test period (data through 30 September 2026).
- **Outcome**: a 5+ minute delay at one of the trip's stations inside its window, to the minute, as the commute
  check counts it.
- **Methods**: the model's test-period cells combined as the commute check combines them, and the frequency the
  commute check shows: the share of 2014–2024 days with the same weekday on which the trip was hit.
- **Rule**: if the combined chance overstates what happens by more than 10%, overall or in its top tenth,
  combining cells as independent needs a fix.

| Method | Log loss ↓ | Brier ↓ | ROC AUC ↑ | PR AUC ↑ |
|---|---|---|---|---|
| Frequency, 2014–2024 | 0.17344 | 0.04127 | 0.698 | 0.0952 |
| **Gradient boosting, cells combined** | **0.16954** | **0.04103** | **0.704** | 0.0952 |

4.39% of trip-days had a delay, and the combined chance averages 3.78%. **It's low, not high**: low in every
tenth (the top tenth predicts 9.8% and 11.2% happen; the bottom, 0.71% and 0.88%) and at every length.

To see where the gap comes from, the second row swaps the model's probabilities for each station's actual rate
per hour over the test period, combined the same way:

| Predicted ÷ observed | 3 stations | 6 stations | 10 stations | All trips |
|---|---|---|---|---|
| Model's cells, combined | 0.84 | 0.86 | 0.87 | 0.86 |
| Actual rate per station and hour, combined | 0.93 | 0.97 | 0.98 | 0.97 |

- **Combining cells as independent holds up.** Fed accurate cells, it lands within 3% of what happened. The
  error moves toward overstating as trips get longer, the direction independence predicts, but at 10 stations
  it's still 2% low. Short trips come out 7% low. Their windows are mostly part-hours, so spreading each hour's
  chance evenly across it is the more likely cause.
- **The gap is in the model's cells, and it isn't a trend.** Its cells run 6% low over the test period, about
  the same in 2025 and 2026. Its daily pattern is too flat: 14–15% low at 8 a.m., noon and 5 p.m., where most
  of these trips' windows fall, and 10–11% high at 7 a.m., 2 p.m. and 7 p.m.

### Decision

The rule didn't trigger, so the combination stays. Per trip, the model still beats the frequency (log loss
−2.3%), so the commute check keeps showing it. The model's flat daily pattern is tracked in #36.

## Hourly correction (#36)

[Whole trips](#whole-trips) found the model's cells running low at the hours most trips fall in. Treating hour
as a category, weighting recent years and bigger trees didn't bring whole trips within the ±5% that #36 set
(0.90 at best; the table is in the issue). Correcting the model with its own recent errors gets closer:

- **Correction**: each probability is multiplied by its hour's observed ÷ predicted delays over the previous
  182 days, all stations together. A prior of 30 delays on both sides pulls an hour with few delays toward no
  correction. A day never sees its own labels.
- **Chosen on 2024**, with the model fit on 2014–2023: 182 days and a prior of 30, out of 28, 91, 182 or 365
  days and 10, 30 or 100 (log loss on 2024 0.05224 → 0.05212).
- **Rule**, from #36: whole-trip predicted ÷ observed within ±5%, overall and in the top tenth, and cell log
  loss no worse than 0.04829.

On the test period, with data through 30 September 2026 (so the first row differs a little from
[Results](#results-on-january-2025--august-2026)):

| | Cells: log loss ↓ | Cells: PR AUC ↑ | Trips: log loss ↓ | Trips: predicted ÷ observed | Top tenth of trips |
|---|---|---|---|---|---|
| Gradient boosting | 0.04829 | 0.0201 | 0.16428 | 0.86 | 0.87 |
| **With the hourly correction** | **0.04825** | **0.0203** | **0.16384** | 0.93 | 0.94 |

| Cells, predicted ÷ observed | 8 a.m. | Noon | 5 p.m. | 10 p.m. |
|---|---|---|---|---|
| Gradient boosting | 0.86 | 0.86 | 0.85 | 0.82 |
| With the hourly correction | 0.96 | 0.97 | 0.96 | 0.96 |

- **The rule isn't met.** Whole trips are still 7% low, and about 3 points of that is the combination itself,
  which lands 3% short even when given actual rates.
- **The top tenth of cells now runs high**: 2.43% predicted, 2.23% observed. Scaling an hour up raises its
  riskiest cells as well. On whole trips the top tenth is still low (10.15% predicted, 10.77% observed).
- **It isn't one lucky setting.** The neighbours of the chosen one (91 or 365 days, a prior of 10 or 100) also
  improve both log losses on the test period. It holds in each test year alone: predicted ÷ observed goes from
  0.935 to 0.982 in 2025 and from 0.941 to 0.997 in 2026.

### Serving it

`train-model` refits on all the data every time, so it has no unseen recent days to measure errors on. A
second model that stops 182 days before the data ends supplies them, and its factors scale the full model's
forecasts. With no data before those 182 days, it serves the model uncorrected. This was backtested against the old `train-model` on 15 weekly forecasts, one starting on the first
of each month from July 2025 to September 2026. Each used only the data before its week:

| Weekly forecasts | Log loss ↓ | Predicted ÷ observed | 8 a.m. | 5 p.m. | 10 p.m. |
|---|---|---|---|---|---|
| Model on all data (before) | 0.04717 | 0.97 | 0.85 | 0.84 | 0.76 |
| Held-out model, corrected | 0.04719 | 1.01 | 0.94 | 0.94 | 0.90 |
| **Model on all data × held-out factors (now)** | **0.04714** | 1.02 | 0.94 | 0.94 | 0.91 |

Losing 6 months of training cost the held-out model about what the correction gained. The third row was tried
after seeing that, and it beats the old forecast in 10 of the 15 weeks.

### Decision

Serve the third row. Its log loss gain is small (10 of 15 weeks happens by chance 15% of the time), but at
commute hours the chance the commute check shows goes from about 15% low to about 6% low. The cost is the top
tenth of cells running 9% high. #36 stays open, since whole trips are still outside ±5%.

