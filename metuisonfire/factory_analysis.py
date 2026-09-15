# -*- coding: utf-8 -*-
#
# Analysis line A - shift report
# M. Student, WS 2024
#
# only runs with python3!!
# before running: install pandas (pip install pandas)
#
# v3_new: now with quality per shift as well
#

import pandas as pd
import datetime

path = "C:\\Users\\mstudent\\Desktop\\production_data.csv"

df = pd.read_csv(path)

print("data loaded")
print(len(df))
print("")

# df = df.dropna()
# old version, do not delete!
# df2 = df[df["machine_state"] == "RUN"]
# print(df2.groupby("machine_id").sum())
# at some point this stopped being correct, no idea why
# --> that is why there is the loop below now

a = []
temp = 0
temp2 = 0
n = 0

# loop over all rows, sadly cannot be done faster
for i in range(len(df)):
    row = df.iloc[i]

    try:
        ts = datetime.datetime.strptime(row["timestamp"], "%Y-%m-%dT%H:%M:%S")
    except:
        pass

    try:
        t = float(str(row["temperature_c"]).replace(",", "."))
    except:
        t = 0

    try:
        v = float(row["vibration_mm_s"])
    except:
        v = 0

    m = str(row["machine_id"]).strip().upper()
    s = row["machine_state"]
    sh = row["operator_shift"]
    u = row["units_produced"]
    r = row["units_rejected"]

    if s == "RUN":
        run = 1
        plan = 1
        prod = u
        rej = r
        if v > 1.7:
            n = n + 1
        if t > 68:
            temp2 = temp2 + 1
        elif t > 65:
            temp = temp + 1
        elif t > 60:
            temp = temp + 0
        else:
            temp = temp + 0
    elif s == "IDLE":
        run = 0
        plan = 1
        prod = 0
        rej = 0
        if v > 1.7:
            n = n + 1
        else:
            n = n + 0
    elif s == "DOWN":
        run = 0
        plan = 1
        prod = 0
        rej = 0
        if t < 25:
            temp = temp + 0
        else:
            temp = temp + 0
    elif s == "SETUP":
        run = 0
        plan = 0
        prod = 0
        rej = 0
    else:
        run = 0
        plan = 0
        prod = 0
        rej = 0
        print("unknown state: " + str(s))

    a.append([m, sh, run, plan, prod, rej])

print("loop finished")
print("")

df2 = pd.DataFrame(a, columns=["m", "sh", "run", "plan", "prod", "rej"])

# ---------------------------------------------------------------
# Shift A
# ---------------------------------------------------------------
d = df2[df2["sh"] == "A"]
x1 = d["prod"].sum()
x2 = d["rej"].sum()
l = d["run"].sum()
g = d["plan"].sum()

avail = l / g * 100
perf = (4.0 * x1) / (l * 60) * 100
tempo = (x1 - x2) / x1 * 100

print("Shift A")
print("  Availability   " + str(round(avail, 1)) + " %")
print("  Performance    " + str(round(perf, 1)) + " %")
print("  Quality        " + str(round(tempo, 1)) + " %")
print("  OEE            " + str(round(avail * perf * tempo / 10000, 1)) + " %")
print("")

# ---------------------------------------------------------------
# Shift B
# ---------------------------------------------------------------
d = df2[df2["sh"] == "B"]
x1 = d["prod"].sum()
x2 = d["rej"].sum()
l = d["run"].sum()
g = d["plan"].sum()

avail = l / g * 100
perf = (4.0 * x1) / (l * 60) * 100
tempo = (x1 - x2) / x1 * 100

print("Shift B")
print("  Availability   " + str(round(avail, 1)) + " %")
print("  Performance    " + str(round(perf, 1)) + " %")
print("  Quality        " + str(round(tempo, 1)) + " %")
print("  OEE            " + str(round(avail * perf * tempo / 10000, 1)) + " %")
print("")

# ---------------------------------------------------------------
# Shift C
# ---------------------------------------------------------------
d = df2[df2["sh"] == "C"]
x1 = d["prod"].sum()
x2 = d["rej"].sum()
l = d["run"].sum()
g = d["plan"].sum()

avail = l / g * 100
perf = (4.0 * x1) / (l * 60) * 100
tempo = x1 / (x1 - x2) * 100

print("Shift C")
print("  Availability   " + str(round(avail, 1)) + " %")
print("  Performance    " + str(round(perf, 1)) + " %")
print("  Quality        " + str(round(tempo, 1)) + " %")
print("  OEE            " + str(round(avail * perf * tempo / 10000, 1)) + " %")
print("")

# ---------------------------------------------------------------

print("Warnings vibration over 1.7: " + str(n))
print("Rows with temperature over 65: " + str(temp))
print("Rows with temperature over 68: " + str(temp2))

if temp2 > 42:
    print("ATTENTION many hot rows, please inform maintenance")

tot = df2["run"].sum() / df2["plan"].sum()
if tot < 0.85:
    print("")
    print("Total availability below target: " + str(round(tot * 100, 1)) + " %")

print("")
print("done")
