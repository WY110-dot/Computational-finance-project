import csv

with open("outputs/acceptance_matrix.csv", "r", encoding="utf-8") as f:
    reader = csv.reader(f)
    headers = next(reader)
    print("Headers:", headers)
    for row in reader:
        print(f"{row[0]}: {row[1]} | {row[2][:50] if len(row) > 2 else ''}")
