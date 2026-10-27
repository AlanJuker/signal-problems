# 3. Serving the delay model as precomputed forecasts

Date: 2026-10-27
Status: Accepted

## Context

The commute check reports a historical frequency ("24 of 87 Fridays"). The gradient boosting model from the
#24 experiment beats that frequency on held-out data (log loss −4.3%, PR AUC +9%), so #25 adds its probability
next to it.

Loading the model in the API would put pandas and scikit-learn in the image that serves every request, and
predicting needs features (delays at the station in the previous 7 and 28 days) recomputed from the delay table
on each call. The model's inputs only change when new data is ingested, once a month.

## Decision

`train-model` refits the model on all the data and stores its probabilities for the **seven days after the data
ends**, per station and service hour (70 × 7 × 21 = 10,290 rows), in a `forecasts` table. The API reads that
table like any other.

A trip's chance combines its cells: each station's hourly probability, weighted by the share of that hour
inside the trip's window, as `1 − ∏(1 − p)^share`. That is the event the frequency counts (a 5+ minute delay
at a trip station within the window), so the two numbers can sit side by side.

## Consequences

- The API never imports scikit-learn. The image installs the `ml` group only when built with `ML=true`, which
  `make model` uses for training; CI builds it that way and checks a chance comes back.
- Training on the full history takes about 8 s, so it can run after every monthly ingest.
- Forecasts describe the week after the data ends, not the week the user asks in; the response says which
  day (`model_day`).
- Cells are treated as independent, which overstates the chance a little when one disruption hits several
  stations. On the real data the model lands close to what happened since 2025 (for example 9.4% vs 8 of 87
  Mondays for Kipling → St George at 07:45). A model of whole trips would remove the assumption.
