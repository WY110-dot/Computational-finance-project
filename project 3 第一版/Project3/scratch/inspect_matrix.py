import csv

with open("outputs/acceptance_matrix.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        print(f"{row['id']}: status={row['status']}, desc={row['description'][:40]}")
