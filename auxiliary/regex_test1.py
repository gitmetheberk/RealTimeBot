import re

regex = re.compile("(\\b\\w*\\b)?\\s*([0-9]{1,2}:[0-9]{1,2}|[0-9]{1,4})\\s?([a-z]+|$)?", re.IGNORECASE)

while True:
    text = input()
    text.replace(",", "")
    matches = re.findall(regex, text)
    print(matches)
