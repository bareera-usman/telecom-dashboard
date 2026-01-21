"""
Three Mobile PDF Invoice Parser
Extracts complete invoice data including VAT from Three Business PDF bills
"""

import PyPDF2
import re
from typing import Dict
from datetime import datetime

class ThreePDFParser:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.invoice_data = {
            'metadata': {
                'provider': 'Three'
            },
            'summary': {},
            'mobiles': [],
            'cost_centres': {}
        }
    
    def parse(self) -> Dict:
        """Main parsing method"""
        # Read PDF
        with open(self.pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            # Extract text from all pages
            full_text = ''
            for page in pdf_reader.pages:
                full_text += page.extract_text()
            
            print(f"\n📄 THREE PDF PARSER")
            print(f"   Pages: {len(pdf_reader.pages)}")
            print(f"   Text length: {len(full_text)} chars")
            
            # Parse different sections
            self._parse_header(full_text)
            self._parse_summary(full_text)
            self._parse_vat(full_text)
            
            # Verify we have required data
            if not self.invoice_data['metadata'].get('invoice_number'):
                raise ValueError("Could not extract invoice number from Three PDF")
            if not self.invoice_data['metadata'].get('invoice_date'):
                raise ValueError("Could not extract invoice date from Three PDF")
            if not self.invoice_data['metadata'].get('total_amount'):
                raise ValueError("Could not extract total amount from Three PDF")
            
            print(f"✅ Three PDF parsed successfully")
            
        return self.invoice_data
    
    def _parse_header(self, text: str):
        """Extract invoice header information"""
        # Number of connections - comes BEFORE the label in Three PDFs!
        # Format: "1006\nNumber of Connections"
        connections_match = re.search(r'(\d+)\s*[\r\n]+\s*Number of Connections', text, re.IGNORECASE)
        if connections_match:
            self.invoice_data['summary']['total_mobiles'] = int(connections_match.group(1))
            print(f"   📱 Mobiles: {connections_match.group(1)}")
        else:
            print(f"   ⚠️  Could not find mobile count")
        
        # Bill number - comes BEFORE "Your Bill Number"
        bill_match = re.search(r'(\d+)\s*[\r\n]+\s*Your Bill Number', text, re.IGNORECASE)
        if bill_match:
            self.invoice_data['metadata']['invoice_number'] = bill_match.group(1)
            print(f"   📄 Invoice: {bill_match.group(1)}")
        else:
            print(f"   ⚠️  Could not find invoice number")
        
        # Account number - comes BEFORE "Your Account Number"
        account_match = re.search(r'(\d+)\s*[\r\n]+\s*Your Account Number', text, re.IGNORECASE)
        if account_match:
            self.invoice_data['metadata']['account_number'] = account_match.group(1)
            print(f"   🏢 Account: {account_match.group(1)}")
        
        # Bill date - comes BEFORE "Bill Date"
        date_match = re.search(r'(\d+\s+[A-Za-z]+\s+\d+)\s*[\r\n]+\s*Bill Date', text, re.IGNORECASE)
        if date_match:
            date_str = date_match.group(1).strip()
            parsed_date = self._parse_date(date_str)
            if parsed_date:
                self.invoice_data['metadata']['invoice_date'] = parsed_date
                print(f"   📅 Date: {parsed_date}")
        
        # Fallback date if not found
        if not self.invoice_data['metadata'].get('invoice_date'):
            self.invoice_data['metadata']['invoice_date'] = datetime.now().strftime('%Y-%m-%d')
            print(f"   ⚠️  Using today's date as fallback")
    
    def _parse_summary(self, text: str):
        """Extract billing summary"""
        # Total monthly recurring charges
        recurring_match = re.search(r'Total monthly recurring charges\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
        if recurring_match:
            value = float(recurring_match.group(1).replace(',', ''))
            self.invoice_data['summary']['recurring_charges'] = value
            print(f"   💰 Recurring: £{value:,.2f}")
        
        # Total usage charges
        usage_match = re.search(r'Total usage charges\s*£([\d,]+\.?\d*)', text, re.IGNORECASE)
        if usage_match:
            value = float(usage_match.group(1).replace(',', ''))
            self.invoice_data['summary']['usage_charges'] = value
            print(f"   📞 Usage: £{value:,.2f}")
        
        # Total charges before VAT
        before_vat_match = re.search(r'Total charges before VAT\s*£([\d,]+\.?\d*)', text, re.IGNORECASE)
        if before_vat_match:
            value = float(before_vat_match.group(1).replace(',', ''))
            self.invoice_data['summary']['total_before_vat'] = value
            print(f"   💵 Before VAT: £{value:,.2f}")
    
    def _parse_vat(self, text: str):
        """Extract VAT breakdown and final total"""
        # VAT at 0%
        vat_0_match = re.search(r'VAT at 0%\s*on\s*£([\d,]+\.?\d*)\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
        if vat_0_match:
            base = float(vat_0_match.group(1).replace(',', ''))
            amount = float(vat_0_match.group(2).replace(',', ''))
            self.invoice_data['summary']['vat_0_base'] = base
            self.invoice_data['summary']['vat_0_amount'] = amount
            print(f"   🔵 VAT 0%: £{amount:,.2f} on £{base:,.2f}")
        
        # VAT at 20%
        vat_20_match = re.search(r'VAT at 20%\s*on\s*£([\d,]+\.?\d*)\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
        if vat_20_match:
            base = float(vat_20_match.group(1).replace(',', ''))
            amount = float(vat_20_match.group(2).replace(',', ''))
            self.invoice_data['summary']['vat_20_base'] = base
            self.invoice_data['summary']['vat_20_amount'] = amount
            print(f"   🟠 VAT 20%: £{amount:,.2f} on £{base:,.2f}")
        
        # Total charges after VAT (final total)
        total_after_vat_match = re.search(r'Total charges after VAT\s*£([\d,]+\.?\d*)', text, re.IGNORECASE)
        if total_after_vat_match:
            total_amount = float(total_after_vat_match.group(1).replace(',', ''))
            self.invoice_data['metadata']['total_amount'] = total_amount
            print(f"   ✅ TOTAL (after VAT): £{total_amount:,.2f}")
        
        # Net charges (should match total after VAT)
        net_match = re.search(r'Net Charges for this month\s*£([\d,]+\.?\d*)', text, re.IGNORECASE)
        if net_match:
            net_amount = float(net_match.group(1).replace(',', ''))
            # Use net charges if total_amount not found
            if 'total_amount' not in self.invoice_data['metadata']:
                self.invoice_data['metadata']['total_amount'] = net_amount
                print(f"   ✅ TOTAL (net charges): £{net_amount:,.2f}")
        
        # Calculate total_amount if not found
        if 'total_amount' not in self.invoice_data['metadata'] or self.invoice_data['metadata']['total_amount'] == 0:
            before_vat = self.invoice_data['summary'].get('total_before_vat', 0)
            vat_20 = self.invoice_data['summary'].get('vat_20_amount', 0)
            vat_0 = self.invoice_data['summary'].get('vat_0_amount', 0)
            calculated_total = before_vat + vat_20 + vat_0
            self.invoice_data['metadata']['total_amount'] = calculated_total
            print(f"   ⚠️  Calculated TOTAL: £{calculated_total:,.2f} (Before VAT + VAT)")
    
    def _parse_date(self, date_str: str) -> str:
        """Convert date string to ISO format - never returns None"""
        try:
            # Clean the date string
            date_str = date_str.strip().replace('\n', ' ').replace('\r', ' ')
            # Remove extra spaces
            date_str = ' '.join(date_str.split())
            
            # Try different formats
            formats = [
                '%d %b %y',      # 25 Jan 25
                '%d %B %y',      # 25 January 25
                '%d %b %Y',      # 25 Jan 2025
                '%d %B %Y',      # 25 January 2025
                '%d-%b-%y',      # 25-Jan-25
                '%d/%m/%y',      # 25/01/25
                '%d/%m/%Y',      # 25/01/2025
            ]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    # Ensure year is in 2000s if 2-digit year
                    if dt.year < 2000:
                        dt = dt.replace(year=dt.year + 2000)
                    return dt.strftime('%Y-%m-%d')
                except ValueError:
                    continue
            
            # If all formats fail, return today's date
            print(f"⚠️  Failed to parse date '{date_str}' with any format")
            return datetime.now().strftime('%Y-%m-%d')
            
        except Exception as e:
            print(f"⚠️  Date parsing error: {e}")
            return datetime.now().strftime('%Y-%m-%d')
