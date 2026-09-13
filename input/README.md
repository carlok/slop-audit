# Input

Paste the text under audit into `target.txt` (replace this file’s contents).

- Authoritative path: `input/target.txt`
- After setup smoke, the file holds only `# paste target text here`
- Operator flow: user pastes prose in chat → write to `target.txt` → `python run_audit.py` → return `report/report.md`
- Do not commit real target text (`target.txt` is gitignored)
