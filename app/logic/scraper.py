import requests
from bs4 import BeautifulSoup
import re

def scrape_pitc_bill(ref_no, company="mepcobill"):
    """
    Scrapes a duplicate electricity bill from bill.pitc.com.pk
    Requires ref_no (14 digits) and company (e.g. mepcobill, lescobill).
    Returns a standardized dictionary matching the OCR output format.
    """
    # Standardize company input
    company = company.lower().strip()
    if not company.endswith("bill"):
        company += "bill"
        
    url = f"https://bill.pitc.com.pk/{company}"
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml",
        "Origin": "https://bill.pitc.com.pk",
        "Referer": url,
    })

    try:
        # Step 1: GET request to retrieve ASP.NET hidden tokens
        response = session.get(url, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')

        viewstate_elem = soup.find('input', {'id': '__VIEWSTATE'})
        viewstategen_elem = soup.find('input', {'id': '__VIEWSTATEGENERATOR'})
        eventval_elem = soup.find('input', {'id': '__EVENTVALIDATION'})
        reqtoken_elem = soup.find('input', {'name': '__RequestVerificationToken'})

        if not viewstate_elem:
            return {"error": "Could not initiate connection to the billing server."}

        # Step 2: POST request to submit the form
        payload = {
            '__VIEWSTATE': viewstate_elem.get('value', ''),
            '__VIEWSTATEGENERATOR': viewstategen_elem.get('value', '') if viewstategen_elem else "",
            '__EVENTVALIDATION': eventval_elem.get('value', '') if eventval_elem else "",
            '__RequestVerificationToken': reqtoken_elem.get('value', '') if reqtoken_elem else "",
            'rbSearchByList': 'refno',
            'searchTextBox': ref_no,
            'ruCodeTextBox': '', # Blank for Urban 'U'
            'btnSearch': 'Search'
        }

        post_url = f"https://bill.pitc.com.pk/{company}"
        post_response = session.post(post_url, data=payload, timeout=20)
        
        if post_response.status_code != 200:
            return {"error": f"Billing server returned status {post_response.status_code}"}
            
        post_soup = BeautifulSoup(post_response.text, 'html.parser')
        
        # Verify if bill was retrieved
        if "PAYABLE WITHIN DUE DATE" not in post_response.text.upper() and "TOTAL AMOUNT" not in post_response.text.upper():
            return {"error": "Bill not found for the provided Reference Number."}

        parsed_data = parse_scraped_bill(post_soup, ref_no)
        parsed_data["raw_html"] = post_response.text
        return parsed_data

    except Exception as e:
        return {"error": str(e)}


def _clean_text(td_elem):
    if not td_elem:
        return "0"
    text = td_elem.get_text(separator=' ', strip=True)
    text = re.sub(r'[^\d.]', '', text)
    return text if text else "0"

def parse_scraped_bill(soup, ref_no):
    """Parses the BeautifulSoup object into our standardized dict"""
    data = {
        "Consumer Name": "Unknown",
        "Reference No": ref_no,
        "Issue Date": "Unknown",
        "Units Consumed": "0",
        "FPA": "0",
        "Arrears": "0",
        "Total Amount": "0"
    }
    
    # Extract Issue Date
    # Looking for table headers
    headers = soup.find_all('h4')
    for idx, h in enumerate(headers):
        if "ISSUE DATE" in h.text.upper():
            # The value is in the next row, same column index
            # This is fragile, so we use a safer approach:
            td = h.find_parent('td')
            if td:
                tr = td.find_parent('tr')
                next_tr = tr.find_next_sibling('tr')
                if next_tr:
                    tds = next_tr.find_all('td')
                    # Find index of the header in its row
                    header_tds = tr.find_all('td')
                    try:
                        h_idx = header_tds.index(td)
                        data["Issue Date"] = tds[h_idx].get_text(strip=True)
                    except:
                        pass
            break
            
    # Extract Consumer Name (Usually near "NAME & ADDRESS")
    name_span = soup.find(lambda tag: tag.name == "span" and "NAME & ADDRESS" in tag.text.upper())
    if name_span:
        parent_p = name_span.find_parent('p')
        if parent_p:
            spans = parent_p.find_all('span')
            if len(spans) > 1:
                data["Consumer Name"] = spans[1].get_text(strip=True)

    # Extract Billing Values
    for b_tag in soup.find_all('b'):
        text = b_tag.get_text(strip=True).upper()
        
        if "UNITS CONSUMED" in text:
            td = b_tag.find_parent('td')
            if td:
                next_td = td.find_next_sibling('td')
                data["Units Consumed"] = _clean_text(next_td)
                
        elif "FUEL PRICE ADJUSTMENT" in text or "FPA" in text:
            td = b_tag.find_parent('td')
            if td:
                next_td = td.find_next_sibling('td')
                val = _clean_text(next_td)
                # Some tables might have multiple FPAs or differ, pick the largest or first
                if data["FPA"] == "0" and val != "0":
                    data["FPA"] = val
                    
        elif "ARREAR/AGE" in text or "ARREARS" in text:
            td = b_tag.find_parent('td')
            if td:
                next_td = td.find_next_sibling('td')
                data["Arrears"] = _clean_text(next_td)
                
        elif "PAYABLE WITHIN DUE DATE" in text:
            td = b_tag.find_parent('td')
            if td:
                next_td = td.find_next_sibling('td')
                data["Total Amount"] = _clean_text(next_td)

    # Fallback for Total Amount if "PAYABLE WITHIN DUE DATE" wasn't exactly matched
    if data["Total Amount"] == "0":
        for div in soup.find_all('div'):
            if "PAYABLE WITHIN DUE DATE" in div.get_text(strip=True).upper():
                parent_td = div.find_parent('td')
                if parent_td:
                    next_td = parent_td.find_next_sibling('td')
                    data["Total Amount"] = _clean_text(next_td)

    return data
