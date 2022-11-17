import random
import string
import sys

n = int(input("Enter Message Size: "))

if n <= 0:
    print("Size must be a positive integer")
    sys.exit(1)
    
message = open("message.txt", "w")

message.write(''.join(random.choices(string.ascii_letters + string.digits, k=n)))

message.close()