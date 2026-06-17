import re
from pathlib import Path

path = Path("docs/Roadmap.html")
html = path.read_text(encoding="utf-8")

match = re.search(r'(<h2>Main Task Roadmap.*?</h2>\s*<p>.*?</p>\s*<div class="table-wrap">\s*<table.*?>\s*<thead>.*?</thead>\s*<tbody>)(.*?)(</tbody>)', html, flags=re.DOTALL)
if match:
    tbody = match.group(2)
    # let's split by <tr>
    rows = re.findall(r'<tr[^>]*>.*?</tr>', tbody, flags=re.DOTALL)
    print(f"Found {len(rows)} rows.")
    count_t = 0
    count_phase = 0
    for r in rows:
        if 'class="phase-hdr"' in r or 'class="phase-row"' in r or '<td colspan=' in r:
            count_phase += 1
        else:
            count_t += 1
            # Try to extract Task ID
            # Usually the first <td> contains the task ID
            td1 = re.search(r'<td[^>]*>(.*?)</td>', r, flags=re.DOTALL)
            if td1:
                text = re.sub(r'<[^>]+>', '', td1.group(1)).strip()
                # print("Task:", text)
    print(f"Task rows: {count_t}, Phase rows: {count_phase}")
else:
    print("Match failed!")
