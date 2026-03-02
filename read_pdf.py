import sys
try:
    import pypdf
except ImportError:
    import os
    os.system('pip install pypdf')
    import pypdf

reader = pypdf.PdfReader('Nepra.pdf')
with open('nepra_text.txt', 'w', encoding='utf-8') as f:
    for page in reader.pages:
        f.write(page.extract_text() + '\n')
print("Extracted to nepra_text.txt")
