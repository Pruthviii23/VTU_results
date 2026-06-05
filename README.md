# VTU Results Scraper

A tool that automatically collects student results from the VTU results portal, calculates SGPA, and produces a formatted Excel sheet and a PDF summary report — all from a single list of USNs.

---

## What It Does

You give it a list of student USNs. It opens the VTU results website, solves the captcha for each student using a trained AI model, collects their marks, and saves everything into two output files:

**Excel file** — one sheet per semester found, with every subject's internal marks, external marks, total, result, and the calculated SGPA at the end of each student's row. If a student has backlogs from a previous semester, those appear in a separate sheet automatically.

**PDF report** — a clean, three-page summary designed for HODs and faculty. Page one is an executive dashboard with key metrics and auto-generated insights. Page two is a subject-wise performance table with pass percentages and remarks. Page three ranks all students by SGPA with their classification.

If the run is interrupted for any reason — power cut, network drop, anything — it picks up exactly where it left off the next time you run it. No re-scraping from the beginning.

---

## What You Need Before Starting

**1. Python**
Version 3.10 or higher. Check your version by opening a terminal and typing:
```
python --version
```
If you don't have it, download it from [python.org](https://www.python.org/downloads/).

**2. Google Chrome**
The scraper runs through Chrome. Make sure it's installed and up to date.

**3. ChromeDriver**
This is what lets Python control Chrome. It must match your Chrome version.
Download it from [chromedriver.chromium.org](https://chromedriver.chromium.org/downloads) and place the file in the same folder as the project, or add it to your system PATH.

**4. Your USN list**
An Excel file (`.xlsx`) with a column named exactly `USN`. One USN per row. Place it at:
```
vtu_results/
└── Inp-Out/
    └── usn_list.xlsx    ← your file goes here
```

---

## Installation

Open a terminal, navigate to the project folder, and run this once to install all required packages:

```
pip install selenium pandas openpyxl beautifulsoup4 tensorflow opencv-python pillow reportlab matplotlib
```

That's it. No other setup required.

---

## Folder Structure

Once everything is in place, your folder should look like this:

```
vtu_results/
│
└── In/Ou/                                  ← Inputs and outputs folder
    └── usn_list.xlsx                       ← your USN list goes here
    └── vtu_results.xlsx                    ← results list
    └── vtu_results_report.pfd              ← report PDF 
│
├── crnn_10_prediction_model.keras          ← captcha model
│
├── main.py                                 ← the file you run
├── config.py                               ← settings and subject credits
├── browser.py                              ← handles Chrome and captcha solving
├── scraper.py                              ← reads the results page
├── exporter.py                             ← builds the Excel file
├── report.py                               ← builds the PDF report
├── sgpa.py                                 ← calculates SGPA
├── checkpoint.py                           ← handles resume on crash
├── ocr.py                                  ← runs the AI model
│
├── checkpoint.txt
├── scraper.log
└──failed_usn.txt

```

## How to Run

Open a terminal inside the `vtu_results` folder and type:

```
python main.py
```

You will be asked two questions:

**1. Scheme year**
This refers to the VTU syllabus scheme your students are under. Currently supported: `2022`. Type the year and press Enter.

```
  Available schemes : ['2022', '2025']
  Enter scheme year (e.g. 2022): 2022
```

**2. Semester number**
Enter which semester's results you want to collect (1 through 8).

```
  Available semesters: [1, 2, 3, 4, 5, 6, 7, 8]
  Enter semester number: 5
```

After that, Chrome will open automatically and the scraper will start working through your USN list. You will see a live progress bar in the terminal showing how many students have been processed, how many passed or failed, and an estimated time remaining.

```
  [████████████░░░░░░░░]  60%  12/20  ✓11 ✗1  ETA 00:01:24  scraping  1XX22XX067
```

When it finishes:

```
  Done — 19 scraped  1 failed  Accuracy 95%  Time 0:03:42

  Writing outputs...
  Excel       → VTU/vtu_results.xlsx
  PDF report  → VTU/vtu_results_report.pdf
```

---

## Output Files

All outputs are saved inside the `VTU/` folder.

| File | What it contains |
|---|---|
| `vtu_results.xlsx` | Full marks data, one sheet per semester, SGPA per student |
| `vtu_results_report.pdf` | Executive summary report for faculty/HOD |
| `failed_usns.txt` | List of USNs that could not be scraped |
| `scraper.log` | Detailed log of everything that happened during the run |
| `checkpoint.txt` | Tracks progress — deleted automatically on clean finish |

---

## If Something Goes Wrong Mid-Run

If the scraper stops for any reason — Chrome crash, network issue, your laptop ran out of battery — just run it again:

```
python main.py
```

It will detect the checkpoint and ask:

```
  A previous run was interrupted after USN 1AM22AI045 (Scheme 2022, Sem 5).
  Resume from where it stopped? [Y/n]:
```

Press Enter (or type Y) and it picks up from the next USN. Type N to start over from scratch.

---

## If Some USNs Failed

After a run, check `VTU/failed_usns.txt`. USNs end up there for two reasons:

**The USN doesn't exist on the portal** — the VTU website returned an "not available" message. This usually means the student's results haven't been published yet, or the USN was entered incorrectly in your list.

**Captcha could not be solved** — the AI model failed to read the captcha after several attempts. This can happen if the captcha style changed on the VTU portal.

You can re-run failed USNs by replacing `usn_list.xlsx` with just the failed USNs and running again.

---

## Notes

- The scraper runs one USN at a time. It will not run faster by opening multiple windows — the VTU portal rate-limits requests.
- Keep the Chrome window visible while it runs. Do not minimise it to the taskbar on some systems, as this can cause screenshot capture to fail.
- The PDF report is designed for batches of students from the same class and semester. Running it across mixed branches in one go will produce a combined report — which may or may not be what you want.
- All activity during a run is logged in detail to `VTU/scraper.log`. If something unexpected happens, that file is the first place to look.
