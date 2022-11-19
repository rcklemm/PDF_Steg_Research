import argparse
import re
import sys
import json

nums_regex = re.compile(b"[\d\.\-]+")
tj_nums_regex = re.compile(b"[\d\.\-]+(?![^\(]*\))(?![^\<]*\>)")

class PdfStream:
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text
        
class Operator:
    def __init__(self, op_str, min_num_operands, max_num_operands, max_pcts, bits_per_operand):
        global nums_regex
        self.op_str = op_str
        self.min_num_operands = min_num_operands
        self.max_num_operands = max_num_operands
        self.max_pcts = max_pcts
        self.bits_per_operand = bits_per_operand
        self.regex_number_capture = nums_regex
        
        self.pattern = re.compile(b"(?:[\d\.\-]+\s+)" + b"{" + bytes(str(self.min_num_operands), 'ascii')
            + b"," + bytes(str(self.max_num_operands), 'ascii') + b"}" + bytes(self.op_str, 'ascii') + b"\s")
        
    def find_all(self, text):
        matches = [m for m in self.pattern.finditer(text)]
        return [(m.start(), m.end()) for m in matches]
    
    def embed(self, match, bits):
        parts = [m for m in self.regex_number_capture.finditer(match)]
        parts = [(p.start(), p.end()) for p in parts]
        
        bit_pieces = [bits[i:i+self.bits_per_operand] for i in range(0, len(bits), self.bits_per_operand)]
        replacement = b""
        match_index = 0
        part_index = 0
        bits_hidden = 0
        for (p, b) in zip(parts, bit_pieces):
            replacement += match[match_index:p[0]]
            num = match[p[0]:p[1]]
            replacement += embed_bit(num, self.max_pcts[part_index] / 100.0, self.bits_per_operand, b)
            match_index = p[1]
            part_index += 1
            bits_hidden += len(b)
        replacement += match[match_index:]
            
        return replacement, bits_hidden
        
    def extract(self, match):
        parts = [m for m in self.regex_number_capture.finditer(match)]
        parts = [(p.start(), p.end()) for p in parts]
        
        bits = ""
        for p in parts:
            num = match[p[0]:p[1]]
            bits += format_extracted(extract_bit(num, self.bits_per_operand), self.bits_per_operand)
            
        return bits

class TJ_Operator(Operator):
    def __init__(self, op_str, max_pct, bits_per_operand):
        global tj_nums_regex
        self.op_str = op_str
        self.max_pct = max_pct
        self.bits_per_operand = bits_per_operand
        self.regex_number_capture = tj_nums_regex
        
        self.pattern = re.compile(b"\[.+?\]\s*?TJ")
        
    def embed(self, match, bits):
        parts = [m for m in self.regex_number_capture.finditer(match)]
        parts = [(p.start(), p.end()) for p in parts]
        
        bit_pieces = [bits[i:i+self.bits_per_operand] for i in range(0, len(bits), self.bits_per_operand)]
        replacement = b""
        match_index = 0
        bits_hidden = 0
        for (p, b) in zip(parts, bit_pieces):
            replacement += match[match_index:p[0]]
            num = match[p[0]:p[1]]
            replacement += embed_bit(num, self.max_pct / 100.0, self.bits_per_operand, b)
            match_index = p[1]
            bits_hidden += len(b)
        replacement += match[match_index:]
            
        return replacement, bits_hidden

def embed_bit(str_op: bytes, pct: float, n: int, bits: str):
    orig = str_op
    negative = b"-" in str_op
    floating_point = b"." in str_op
    point_loc = len(str_op) if not floating_point else str_op.index(b".")
    str_op = str_op.replace(b"-", b"")
    
    leading_zeroes = 0
    if floating_point:
        for c in str_op.replace(b".", b""):
            if c == '0':
                leading_zeroes += 1
            else:
                break
                
    int_op = int(str_op.replace(b".", b""))
    mask = int(bits, 2)
    if extract_bit(str_op, n) == mask:
        return orig
        
    # Special case for operator = 0
    if int_op == 0:
        return b"0.0" + bytes(str(int(bits, 2)), 'ascii')
    
    small_enough_change = False
    working_int_op = int_op
    while (not small_enough_change):
        new_int_op = working_int_op ^ (working_int_op & int("1"*n, 2))
        new_int_op = new_int_op | mask
        
        if (abs(new_int_op - working_int_op) <= pct*working_int_op):
            small_enough_change = True
            working_int_op = new_int_op
        else:
            working_int_op *= 10
                
    return_str = b""
    if negative:
        return_str += b"-"
        
    return_str += b"0"*leading_zeroes
    return_str += bytes(str(working_int_op), 'ascii')
    
    if return_str[point_loc:] != b"":
        return_str = return_str[0:point_loc] + b"." + return_str[point_loc:]
        
    return return_str
    
def extract_bit(str_op: bytes, n: int):
    int_op = int(str_op.replace(b".",b"").replace(b"-", b""))
    mask = int("1"*n, 2)
    return int_op & mask
    
def format_extracted(extracted: int, n: int):
    return "{0:b}".format(extracted).zfill(n)
    
# Build operators from config file
config = []
with open("./config.json") as c:
    config = json.load(c)
    
operators = []    
for op in config:
    if not op["enabled"]:
        continue
    if op["operator"] != "TJ":
        operators.append(Operator(op["operator"], op["min_operands"], op["max_operands"], op["max_pct_per_operand"], 3))
    else:
        operators.append(TJ_Operator(op["operator"], op["max_pct_per_operand"][0], 3))
    
    
def find_all_streams(in_file):
    filebytes = in_file.read()
    in_file.seek(0)
    
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
    
    return streams
    
def collect_all_matches(text):
    global operators  
    matches = {}
    for op in operators:
        op_matches = op.find_all(text)
        for o in op_matches:
            matches[o] = op
            
    return sorted(matches.items(), key=lambda m: m[0][0]) 
    
def msg_to_bits(msg):
    bitstr = b''.join( [bin(b).lstrip('0b').zfill(8).encode() for b in msg]  )
    return ''.join( [chr(b) for b in bitstr] )
    
def bits_to_msg(bit_str):
    message = bytearray()
    msgSize = len(bit_str) // 8
    for i in range(msgSize):
        message.append(int(bit_str[(8*i):((8*i) + 8)], 2))
    
    return bytes(message)

def embed(in_file, out_file, msg):
    print("[+] Embedding Message")
    streams = find_all_streams(in_file)
    
    # Append 4-byte size to message, then embed message
    maxsize = stat(in_file)
    size = len(msg)
    
    if size > maxsize:
        print(f"Message of length {size} exceeds capacity {maxsize}")
        exit(1)
        
    sizebytes = size.to_bytes(4, 'big')
    sizebits = msg_to_bits(sizebytes)
    
    msgbits = msg_to_bits(msg)
    msgbits = sizebits + msgbits
    
    newstreams = []
    
    msgindex = 0
    
    for s in streams:
        print(f"{msgindex//8} / {len(msgbits)//8} Embedded ({100*round(float(msgindex)/len(msgbits), 2)}%)")
        text = s.text

        if msgindex >= len(msgbits):
            newstreams.append(text)
            continue
    
        matches = collect_all_matches(text)
        if len(matches) == 0:
            newstreams.append(text)
            continue
            
        newtext = b""
        textindex = 0
        for m in matches:
            newtext += text[textindex:m[0][0]]
            
            bits = msgbits[msgindex:]
            replacement, bits_hidden = m[1].embed(text[m[0][0]:m[0][1]], bits)
            msgindex += bits_hidden
            newtext += replacement
            
            textindex = m[0][1]
         
        newtext += text[textindex:]
        
        newstreams.append(newtext)
        
        
    # Assemble the output PDF
    fileindex = 0

    for t, n in zip(streams, newstreams):
        out_file.write(in_file.read(t.start - fileindex))
        out_file.write(n)
        fileindex = t.end
        in_file.seek(fileindex)

    out_file.write(in_file.read())
    print("[-] Message Embedded")

def extract(in_file, out_file):
    print("[+] Extracting Message")
    streams = find_all_streams(in_file)
    
    # Get all bits, then determine actual size from first 4 bytes
    msg_bits = ""
    for s in streams:
        text = s.text
        matches = collect_all_matches(text)
        
        for m in matches:
            msg_bits += m[1].extract(text[m[0][0]:m[0][1]])
    
    sizebits = msg_bits[0:32]

    sizebytes = bits_to_msg(sizebits)
    size = int.from_bytes(sizebytes, byteorder='big')
    
    relevant_msg_bits = msg_bits[32:32+(size*8)]
    msg = bits_to_msg(relevant_msg_bits)
    out_file.write(msg)
    print("[-] Message Extracted")
   
   
def stat(in_file):
    print("[+] Calculating Allowable Message Size")
    streams = find_all_streams(in_file)
    
    numbits = 0
    for s in streams:
        text = s.text
        matches = collect_all_matches(text)
        for m in matches:
            number_count = m[1].bits_per_operand * len(m[1].regex_number_capture.findall(text[m[0][0]:m[0][1]]))
            numbits += number_count
    
    # 4 bytes reserved for size info
    bytes_available = (numbits // 8) - 4
    print("[-] Message Size Calculated")
    return bytes_available
    
    
if __name__ == "__main__":
    usagestr = "Usage: python full_pdf_steg.py\n\tstat <in-file>\n\tembed <cover-file> <out-file> <message-file>\n\textract <in-file> <out-file>"
    if len(sys.argv) < 3:
        print(usagestr)
        exit(1) 
        
    in_file = open(sys.argv[2], "rb")

    if (sys.argv[1] == "stat"):
        n = stat(in_file)
        print(f"{max(n, 0)} bytes are hideable in this file with current config")
        in_file.close()
        exit(0)
        
    elif (sys.argv[1] == "embed"):
        if len(sys.argv) < 5:
            print(usagestr)
            exit(1)
            
        out_file = open(sys.argv[3], "wb")
        message_file = open(sys.argv[4], "rb")
        embed(in_file, out_file, message_file.read())
        print("Message successfully embedded")
        
        in_file.close()
        out_file.close()
        message_file.close()
        exit(0)
        
    elif (sys.argv[1] == "extract"):
        if len(sys.argv) < 4:
            print(usagestr)
            exit(1)
            
        out_file = open(sys.argv[3], "wb")
        extract(in_file, out_file)
        print("Message successfully extracted")
        
        in_file.close()
        out_file.close()
        exit(0)
        
    else:
        print(usagestr)
        in_file.close()
        exit(1)