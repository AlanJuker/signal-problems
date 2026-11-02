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
probabilities for the seven days after the data ends, per station and hour. Recent counts are the ones known on
the last day, since later days haven't happened yet.

The commute check combines a trip's cells into the chance of at least one 5+ minute delay: each station's hourly
probability, weighted by the share of that hour inside the trip's window, assuming delays spread evenly within an
hour. Cells are treated as independent; [Whole trips](#whole-trips) measures what that costs. On the full
history, the model's chance lands close to what happened since 2025:

| Trip | Model, week after the data | 5+ minute delay since 2025 |
|---|---|---|
| Kipling → St George, Monday 07:45 | 9.4% | 8 of 87 Mondays (9.2%) |
| Bloor-Yonge → Union, Friday 08:15 | 4.2% | 3 of 87 Fridays (3.4%) |
| Finch → Eglinton, Wednesday 17:30 | 4.1% | 3 of 87 Wednesdays (3.4%) |


## Whole trips

The scores above are per station and hour, but the commute check shows one chance per trip. This checks that
chance against what happened. The setup was fixed before the results:

- **Trips**: every run of 3, 6 and 10 neighbouring stations on each line, leaving at 08:00, 12:00, 17:30 and
  21:00. That's 712 trips, each scored on all 638 days of the test period (data through 30 September 2026).
- **Outcome**: a 5+ minute delay at one of the trip's stations inside its window (sized from the TTC's
  scheduled run times), to the minute, as the commute check counts it.
- **Methods**: the model's test-period cells combined as the commute check combines them, and the frequency the
  commute check shows: the share of 2014–2024 days with the same weekday on which the trip was hit.
- **Rule**: if the combined chance overstates what happens by more than 10%, overall or in its top tenth,
  combining cells as independent needs a fix.

| Method | Log loss ↓ | Brier ↓ | ROC AUC ↑ | PR AUC ↑ |
|---|---|---|---|---|
| Frequency, 2014–2024 | 0.16812 | 0.03954 | 0.693 | 0.0906 |
| **Gradient boosting, cells combined** | **0.16428** | **0.03932** | **0.699** | **0.0912** |

4.19% of trip-days had a delay, and the combined chance averages 3.61%. **It's low, not high**: low in every
tenth (the top tenth predicts 9.3% and 10.7% happen; the bottom, 0.69% and 0.88%) and at every length.

To see where the gap comes from, the second row swaps the model's probabilities for each station's actual rate
per hour over the test period, combined the same way:

| Predicted ÷ observed | 3 stations | 6 stations | 10 stations | All trips |
|---|---|---|---|---|
| Model's cells, combined | 0.83 | 0.86 | 0.87 | 0.86 |
| Actual rate per station and hour, combined | 0.93 | 0.96 | 0.98 | 0.97 |

- **Combining cells as independent holds up.** Fed accurate cells, it lands 3% short of what happened. The
  error moves toward overstating as trips get longer, the direction independence predicts, but at 10 stations
  it's still 2% low. Short trips come out 7% low. Their windows are mostly part-hours, so spreading each hour's
  chance evenly across it is the more likely cause.
- **The gap is in the model's cells, and it isn't a trend.** Its cells run 6% low over the test period, about
  the same in 2025 and 2026. Its daily pattern is too flat: 14–15% low at 8 a.m., noon and 5 p.m., where most
  of these trips' windows fall, and 10–11% high at 7 a.m., 2 p.m. and 7 p.m.

### Decision

The rule didn't trigger, so the combination stays. Per trip, the model still beats the frequency (log loss
−2.3%), so the commute check keeps showing it. The model's flat daily pattern is tracked in #36.
