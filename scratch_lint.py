import xml.etree.ElementTree as ET
try:
    # Wrap in a root element to allow multiple root elements if they existed, though HTML should have one.
    with open('index.html', encoding='utf-8') as f:
        html = f.read()
    # Strip doctype as it's not valid XML
    html = html.replace('<!DOCTYPE html>', '')
    # Self-close the meta/link/input tags because we didn't self-close some?
    # Actually wait, let's just use html5lib which is designed for HTML!
    import html5lib
    from html5lib.filters import lint
    parser = html5lib.HTMLParser(strict=True)
    try:
        parser.parse(html)
        print("html5lib strict parse passed.")
    except Exception as e:
        print("html5lib parse error:", e)

    # Let's also report errors manually collected
    parser2 = html5lib.HTMLParser()
    document = parser2.parse(html)
    if parser2.errors:
        print("html5lib errors found:")
        for err in parser2.errors:
            print(err)

except Exception as e:
    print(e)
