# LinkedIn post draft

---

It rained all bank holiday weekend, so naturally I spent it forecasting motorcycle sales. 🏍️🌧️

The MCIA publishes UK new-bike registration stats every month as free PDFs. I scraped 80 of them (Jan 2020 → Jul 2026), added Met Office weather data, and built a monthly forecasting model for the UK motorcycle market.

**Where the market stands (Jul 2026):**
📈 2026 year-to-date: 67,565 registrations, +15.6% vs 2025
📅 July: 10,644, +17.5% YoY (−9.1% vs June — normal seasonal fade)
🔮 August forecast: ~7,600 (+11% YoY) · September: ~10,900 (≈ level with last year's strong plate month)
🗓️ Full-year 2026 on track for ~104k, +10% — recovering most of 2025's Euro 5+ hangover

**Three things the data taught me:**
1️⃣ Seasonality is everything: a March sells ~3× a January (plate months rule bikes too)
2️⃣ The weather? Almost irrelevant. Once you control for seasonality, rain and sunshine predict nothing. The only signal that survives: a warm month lifts *next* month's registrations ~4% per +1°C. You buy the bike after the sunny weekend, not during it.
3️⃣ Adventure bikes are the growth engine: +27% YTD, now 1 in 4 new bikes. Honda takes 1 in 5 of everything.

A simple, boring linear regression beat SARIMAX in backtesting (10% vs 15% error). The fancy model isn't always the better one.

**Where this could go with richer (CRM-level) data:** the same toolkit predicts *people*, not just markets — logistic regression to score which of a brand's mower/car/ATV owners are likely to cross over to two wheels, decision trees to turn those scores into explainable dealer rules, k-nearest-neighbours to find lookalikes of recent buyers for aftermarket offers, and cohort analysis to time the parts/accessories/upgrade cycle from first registration. And with MCIA's full dataset: model-level and regional forecasts.

All public data, Python, and a wet weekend.

#DataScience #Forecasting #Motorcycles #Analytics #Python

---

## Notes for posting
- Numbers as at data through July 2026; forecast intervals are wide (80% band on August: 6.2k–9.1k) — keep claims directional.
- September's forecast is slightly *below* last September (−4%) despite the recovering market, because Sep 2025 was unusually strong. "Level with last year" is the honest framing.
- MCIA data is © MCIA — figures are fine to quote with credit; don't attach their PDFs.
