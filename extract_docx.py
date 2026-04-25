import zipfile
import xml.etree.ElementTree as ET

with zipfile.ZipFile("REpooort_V333_FIXED_(1).docx", 'r') as z:
    root = ET.fromstring(z.read('word/document.xml'))

ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
text = ''.join(t.text or '' for t in root.findall('.//w:t', ns))

with open("_report_full.txt", "w", encoding="utf-8") as f:
    f.write(text)

print(f"Extracted {len(text)} characters")
print("\n=== SECTIONS 2-4 SAMPLE ===\n")
print(text[5000:8000])
