import requests
from bs4 import BeautifulSoup

ref_no = "05151280432603"
comp = "mepcobill"
url = f"https://bill.pitc.com.pk/{comp}"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://bill.pitc.com.pk",
    "Referer": url,
    "Connection": "keep-alive"
})

# Step 1: GET the page to extract ASP.NET hidden fields
print("Fetching form tokens...")
response = session.get(url, timeout=10)
soup = BeautifulSoup(response.text, 'html.parser')

viewstate_elem = soup.find('input', {'id': '__VIEWSTATE'})
viewstategen_elem = soup.find('input', {'id': '__VIEWSTATEGENERATOR'})
eventval_elem = soup.find('input', {'id': '__EVENTVALIDATION'})
reqtoken_elem = soup.find('input', {'name': '__RequestVerificationToken'})

if not viewstate_elem:
    print("Failed to find viewstate")
    exit(1)

__VIEWSTATE = viewstate_elem.get('value')
__VIEWSTATEGENERATOR = viewstategen_elem.get('value') if viewstategen_elem else ""
__EVENTVALIDATION = eventval_elem.get('value') if eventval_elem else ""
__ReqToken = reqtoken_elem.get('value') if reqtoken_elem else ""

# Step 2: POST the data
payload = {
    '__VIEWSTATE': __VIEWSTATE,
    '__VIEWSTATEGENERATOR': __VIEWSTATEGENERATOR,
    '__EVENTVALIDATION': __EVENTVALIDATION,
    '__RequestVerificationToken': __ReqToken,
    'rbSearchByList': 'refno',
    'searchTextBox': ref_no,
    'ruCodeTextBox': '', # Empty string for U, 'R' for Rural
    'btnSearch': 'Search'
}

print("Submitting form...")
post_url = f"https://bill.pitc.com.pk/{comp}"
post_response = session.post(post_url, data=payload, timeout=15)

if post_response.status_code == 200:
    post_soup = BeautifulSoup(post_response.text, 'html.parser')
    # Check if we got a bill
    if "Amount Payable" in post_response.text or "Total Amount" in post_response.text or "UNITS CONSUMED" in post_response.text.upper():
        print("Success! Bill found.")
        with open("mepco_result.html", "w", encoding="utf-8") as f:
            f.write(post_response.text)
    else:
        print("Bill possibly not found or different structure. Saving for review.")
        with open("mepco_error.html", "w", encoding="utf-8") as f:
            f.write(post_response.text)
else:
    print(f"Failed with status: {post_response.status_code}")
