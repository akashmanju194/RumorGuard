import re

html = open("d:/PROGRAMS/rumorguard-backend/RumorGuard/index.html", encoding="utf-8").read()
ids = re.findall(r'id="([^"]+)"', html)
duplicates = set([id for id in ids if ids.count(id) > 1])
print("Duplicates:", duplicates)

# Check for unclosed tags
from html.parser import HTMLParser
class MyParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
    def handle_starttag(self, tag, attrs):
        if tag not in ['meta', 'link', 'br', 'hr', 'img', 'input']:
            self.stack.append(tag)
    def handle_endtag(self, tag):
        if not self.stack:
            print("Error: Extra closing tag", tag)
        elif self.stack[-1] == tag:
            self.stack.pop()
        else:
            print(f"Error: Mismatched tag. Expected {self.stack[-1]} but got {tag}")
            self.stack.pop()

parser = MyParser()
parser.feed(html)
if parser.stack:
    print("Unclosed tags:", parser.stack)
