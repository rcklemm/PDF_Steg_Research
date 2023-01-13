import random
import string
import sys
import os

n = int(input("Enter Message Size: "))

if n <= 0:
    print("Size must be a positive integer")
    sys.exit(1)

if len(sys.argv) == 1 or sys.argv[1] != "bytes":
    message = open("message.txt", "w")

    message.write(''.join(random.choices(string.ascii_letters + string.digits, k=n)))

    message.close()

else:
    message = open("message.txt", "wb")

    message.write(os.urandom(n))

    message.close()