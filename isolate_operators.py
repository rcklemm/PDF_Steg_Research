import re
import sys
import json


class PdfStream:
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text

if len(sys.argv) < 2:
    print(f"Usage: python {sys.argv[0]} <pdf_file>")
    exit(1)

infilename = sys.argv[1]

file = open(infilename, "rb")

filebytes = file.read()
file.close()

start = 0
end = 0
streams = []

# Find all streams in the PDF file
while True:
    try:
        start = filebytes.index(b'stream', start)
        end = filebytes.index(b'endstream', start)
    except:
        break

    if filebytes[(start+6):(start+8)] == b'\r\n':
        streams.append(PdfStream(start + 8, end - 2, filebytes[(start+8):(end-2)]))
    else:
        streams.append(PdfStream(start + 7, end - 1, filebytes[(start+7):(end-1)]))
    
    start = end + 9

operators = {
    "c": (6, 6), 
    "v": (4, 4), 
    "y": (4, 4), 
    "l": (2, 2), 
    "m": (2, 2), 
    "re": (4, 4),
    "cm": (6, 6),
    "i": (1, 1),
    "M": (1, 1),
    "w": (1, 1),
    "G": (1, 1),
    "g": (1, 1),
    "K": (4, 4),
    "k": (4, 4),
    "RG": (3, 3), 
    "rg": (3, 3),
    "SC": (1, 4),
    "sc": (1, 4),
    "SCN": (1, 4),
    "scn": (1, 4),
    "Tc": (1, 1),
    "Td": (2, 2),
    "TD": (2, 2),
    "Tf": (1, 1),
    "TL": (1, 1),
    "Tm": (6, 6),
    "Ts": (1, 1),
    "Tw": (1, 1),
    "Tz": (1, 1),
    "d0": (2, 2),
    "d1": (6, 6)
}

regex = {}

sequences = {}
for k in operators.keys():
    sequences[k] = []
sequences["TJ"] = []

brackets = re.compile("\[.+?\]")

for o in operators.keys():
    regex[o] = [re.compile("(?:[0-9\.-]+\s+)" + "{" + str(operators[o][0]) + "," + str(operators[o][1]) + "}" + o + "\s"), 0]


tj_reg = re.compile("\[.+?\]\s+?TJ")
tj_count = 0

nums = re.compile("[0-9\.-]+")

for t in streams:
    text = t.text.decode("utf-8", errors="ignore")
    cleaned_text = brackets.sub('', text)
    for o in regex.keys():
        r = regex[o][0]
        matches = r.findall(cleaned_text)
        sequences[o] += matches
        regex[o][1] += len(matches)
        
    # Handle TJ as special case
    matches = tj_reg.findall(text)
    sequences["TJ"] += matches
    tj_count += len(matches)

print("Operator Breakdown")
for k in regex.keys():
    print(f"\t{k}: {regex[k][1]}")
print(f"\tTJ: {tj_count}")


logfile = open(f"{infilename.replace('.pdf', '')}.operators.json", "w")

json.dump(sequences, logfile)
logfile.close()
