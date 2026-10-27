# Demo guide (about 3 minutes)

## Before you start

```bash
pip install -r requirements.txt
```

No API key is needed for the demo.

## Script

1. **Show the problem (20 s).** "Qualifying a lead means reading a website, scanning news, comparing it with the ideal customer, and writing an email. This tool does the first pass and explains every point."
2. **Run it (20 s).**
   ```bash
   python run.py --mode demo
   ```
   Six companies are scored in a second because the research is replayed from saved snapshots.
3. **Open `data/output/report.html` (60 s).** Walk through:
   - the ranking and the three tiers;
   - one high-priority card: each criterion shows points, the value found, and the quote that proves it;
   - **Allbirds** or **Etsy**: the orange note shows a business rule that capped the score;
   - a low-fit lead (Notion): summary only, no email, on purpose.
4. **Show the "no guessing" rule (30 s).** Point at "Not verified: ..." in a summary and at the confidence value. Explain: the AI must quote evidence, code checks the quote exists, otherwise the fact scores zero.
5. **Show configurability (40 s).** Open `config/icp.yaml`, change a weight (keep the total at 100) or `outreach_min_score`, rerun `python run.py --mode demo` and show that the scores change instantly.
6. **Optional live run (30 s)**, if you have a key in `.env`:
   ```bash
   python run.py --mode live --company "Warby Parker"
   ```

## Screenshots to capture for the README

Open `data/output/report.html` in your browser, press **Win + Shift + S** and select the area. Save PNG files in `docs/screenshots/` with these names:

| File | What to capture |
|---|---|
| `report-overview.png` | Top of the report: title, banner, the three counters and the first card |
| `lead-card.png` | One card (e.g. Warby Parker) with the email draft expanded (click "Email draft") |
| `capped-lead.png` | The Allbirds or Etsy card showing the orange cap note |
| `csv.png` | `data/output/results.csv` opened in Excel (optional) |

Then uncomment the image lines in `README.md` (search for "uncomment").
