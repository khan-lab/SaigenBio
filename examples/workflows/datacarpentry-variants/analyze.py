"""Teaching workflow for a processed variant table, not variant calling."""
import collections
import csv
import sys

mode, source, destination = sys.argv[1:4]
with open(source, newline='') as stream:
    reader = csv.DictReader(stream)
    fields = reader.fieldnames
    rows = list(reader)
if mode == 'filter':
    threshold = float(sys.argv[4])
    rows = [row for row in rows if float(row['QUAL']) >= threshold]
    with open(destination, 'w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
elif mode == 'summarize':
    counts = collections.Counter(row['sample_id'] for row in rows)
    with open(destination, 'w', newline='') as stream:
        writer = csv.writer(stream, delimiter='\t')
        writer.writerow(['sample', 'variants'])
        writer.writerows(sorted(counts.items()))
else:
    raise ValueError('Unknown teaching workflow operation')
