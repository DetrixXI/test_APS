import csv
import re
with open('posts.csv', 'r', encoding='utf-8') as f:
    a = csv.reader(f, delimiter=',')
    b = [next(a) for _ in range(2)]

c = b[1][2]

regex = '[\[\]\',]'
print((c.translate(str.maketrans('','', regex))).split(' '))
