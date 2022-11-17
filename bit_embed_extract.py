# Read the output of isolate_operators.py and perform the bit insertion algorithm on each given operand
# Track the amount of extra data added compared to the amount of data 

import re
import sys
import json
import random

def extract_bit(str_op: str, n: int):
    int_op = int(str_op.replace(".","").replace("-", ""))
    mask = int("1"*n, 2)
    return int_op & mask

# TODO: How do we handle a zero value????
def embed_bit(str_op: str, pct: float, n: int, bits: str):
    orig = str_op
    negative = "-" in str_op
    floating_point = "." in str_op
    point_loc = len(str_op) if not floating_point else str_op.index(".")
    str_op = str_op.replace("-", "")
    
    leading_zeroes = 0
    if floating_point:
        for c in str_op.replace(".", ""):
            if c == '0':
                leading_zeroes += 1
            else:
                break
                
    int_op = int(str_op.replace(".", ""))
    mask = int(bits, 2)
    if extract_bit(str_op, n) == mask:
        return orig
        
    # Special case for operator = 0
    if int_op == 0:
        return "0.0" + str(int(bits, 2))
    
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
                
    return_str = ""
    if negative:
        return_str += "-"
        
    return_str += "0"*leading_zeroes
    return_str += str(working_int_op)
    
    if return_str[point_loc:] != "":
        return_str = return_str[0:point_loc] + "." + return_str[point_loc:]
        
    return return_str
    
def format_extracted(extracted: int, n: int):
    return "{0:b}".format(extracted).zfill(n)

nums = re.compile("[\d\.\-]+")
tj_nums = re.compile("[\d\.\-]+(?![^\(]*\))")

if len(sys.argv) < 2:
    print(f"Usage: python {sys.argv[0]} <json_file>")
    exit(1)
    
config = {}
with open("config.json", "r") as fp:
    config = json.load(fp)
    
infilename = sys.argv[1]
file = open(infilename, "r")

op_json = json.load(file)

operators = op_json.keys()

for b in range(1, 9):
    total_size_diff = 0
    expected_size_diff = 0
    total_bits_embedded = 0
    num_bits_per_operand = b

    for c in config:
        if c["operator"] not in operators:
            continue
        if c["operator"] == "TJ":
            continue
                
        for m in op_json[c["operator"]]:
            n = nums.findall(m)
            i = 0
            for num in n:
                extracted_bits = extract_bit(num, num_bits_per_operand)
                to_embed = format_extracted( (~extracted_bits) & int("1"*num_bits_per_operand, 2), num_bits_per_operand)
                after_embed = embed_bit(num, c["max_pct_per_operand"][i] / 100.0, num_bits_per_operand, to_embed)
                size_diff = len(after_embed) - len(num)
                total_size_diff += size_diff
                total_bits_embedded += num_bits_per_operand
                
                #if random.randint(0, 1) == 0:
                #    expected_size_diff += size_diff
                
                extracted_after_embed = format_extracted(extract_bit(after_embed, num_bits_per_operand), num_bits_per_operand)
                embed_failure = extracted_after_embed != to_embed
                if embed_failure:
                    print(f"{num}: Becomes {after_embed}, size difference = {size_diff}, failed? {embed_failure}, pct={c['max_pct_per_operand'][i]}", flush=True)
                i += 1
                #exit(0)
            #print(f"{n} {c['operator']} {c['min_pct_per_operand']}")
    
    # Handle TJ separately
    for tj in op_json["TJ"]:
        n = tj_nums.findall(tj)
        for num in n:
            extracted_bits = extract_bit(num, num_bits_per_operand)
            to_embed = format_extracted( (~extracted_bits) & int("1"*num_bits_per_operand, 2), num_bits_per_operand)
            after_embed = embed_bit(num, float('inf'), num_bits_per_operand, to_embed)
            size_diff = len(after_embed) - len(num)
            total_size_diff += size_diff
            total_bits_embedded += num_bits_per_operand
                
            #if random.randint(0, 1) == 0:
            #    expected_size_diff += size_diff
            
            extracted_after_embed = format_extracted(extract_bit(after_embed, num_bits_per_operand), num_bits_per_operand)
            embed_failure = extracted_after_embed != to_embed
            if embed_failure:
                print(f"{num}: Becomes {after_embed}, size difference = {size_diff}, failed? {embed_failure}, pct={20}", flush=True)
                

    
    print(f"Num Bits per Operand: {b}, Total Embedable Bytes: {total_bits_embedded // 8}, Max. File Size Increase (Bytes): {total_size_diff}")
    #if b == 1:
    #    print(f"Expected Size Difference (Randomized): {expected_size_diff}")