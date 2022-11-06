import json

data = json.load(open('flags.json'))
flags = {}
for obj in data:
    flags[obj['code']] = obj['emoji']

del data

def get_flag(code):
    return flags.get(code, code)

