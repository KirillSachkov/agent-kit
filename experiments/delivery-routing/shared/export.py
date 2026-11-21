import csv
import json
import sys


def export(orders, output):
    writer = csv.writer(output)
    writer.writerow(["order"])
    for order in orders:
        writer.writerow([order["order"]])


if __name__ == "__main__":
    export(json.load(sys.stdin), sys.stdout)
