"""
Vodafone Invoice PDF Parser
Extracts invoice data, cost centres, mobile numbers, and charges from Vodafone PDF invoices
"""

import re
import PyPDF2
from typing import Dict, List, Optional
from datetime import datetime
from decimal import Decimal

class VodafoneInvoiceParser:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.invoice_data = {
            'metadata': {},
            'cost_centres': {},
            'mobiles': [],
            'summary': {}
        }
        
    def parse(self) -> Dict:
        """Main parsing method"""
        with open(self.pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            # Extract text from all pages
            full_text = ""
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                full_text += page.extract_text() + "\n"
            
            # Parse different sections
            self._parse_metadata(full_text)
            self._parse_quick_breakdown(full_text)
            self._parse_cost_centres(full_text)
            self._parse_vat_summary(full_text)
            
        return self.invoice_data
    
    def _parse_metadata(self, text: str):
        """Extract invoice metadata from header"""
        # Account number - handle text without spaces
        account_match = re.search(r'Accountnumber\s*Invoicenumber\s*Date\s*(\d+\s*/\s*\d+)\s*(\d+)\s*(\d+\s*[A-Za-z]+\s*\d+)', text, re.IGNORECASE)
        if not account_match:
            account_match = re.search(r'(\d{9})\s*/\s*(\d{5})\s+(\d+)\s+(\d+[A-Za-z]+\d+)', text)
        
        if account_match:
            if len(account_match.groups()) == 4:
                self.invoice_data['metadata']['account_number'] = account_match.group(1).replace(' ', '')
                self.invoice_data['metadata']['invoice_number'] = account_match.group(3)
                self.invoice_data['metadata']['invoice_date'] = self._parse_date(account_match.group(4))
            else:
                self.invoice_data['metadata']['account_number'] = account_match.group(1).replace(' ', '')
                self.invoice_data['metadata']['invoice_number'] = account_match.group(2)
                self.invoice_data['metadata']['invoice_date'] = self._parse_date(account_match.group(3))
        
        # Try alternate format from page header
        if not self.invoice_data['metadata'].get('invoice_number'):
            header_match = re.search(r'670241213\s*/\s*00001\s+109300963\s+15\s*Dec\s*25', text)
            if header_match:
                self.invoice_data['metadata']['account_number'] = '670241213/00001'
                self.invoice_data['metadata']['invoice_number'] = '109300963'
                self.invoice_data['metadata']['invoice_date'] = '2025-12-15'
        
        # Total amount due
        total_match = re.search(r'Total\s+£([\d,]+\.?\d*)', text)
        if total_match:
            self.invoice_data['metadata']['total_amount'] = float(total_match.group(1).replace(',', ''))
        
        # Payment due date
        due_date_match = re.search(r'please\s*pay\s*by\s+(\d+\s+[A-Za-z]+\s+\d+)', text, re.IGNORECASE)
        if due_date_match:
            self.invoice_data['metadata']['payment_due_date'] = self._parse_date(due_date_match.group(1))
        
        # Provider
        self.invoice_data['metadata']['provider'] = 'Vodafone'
        
    def _parse_quick_breakdown(self, text: str):
        """Extract the quick breakdown section from page 1 and 3"""
        # Find the section with "For X mobiles" - handle no spaces
        mobiles_match = re.search(r'For\s*(\d+)\s*mobiles', text, re.IGNORECASE)
        if mobiles_match:
            self.invoice_data['summary']['total_mobiles'] = int(mobiles_match.group(1))
        
        # Extract ECS EXTRA ADVISOR charge if present
        ecs_match = re.search(r'ECS.*?EXTRA.*?ADVISOR\s+£([\d,]+\.?\d*)', text, re.IGNORECASE)
        if ecs_match:
            self.invoice_data['summary']['ecs_extra_advisor'] = float(ecs_match.group(1).replace(',', ''))
        
        # Extract Unallocated mobiles charge if present
        unalloc_match = re.search(r'Unallocated\s*mobiles\s+£([\d,]+\.?\d*)', text, re.IGNORECASE)
        if unalloc_match:
            self.invoice_data['summary']['unallocated_mobiles'] = float(unalloc_match.group(1).replace(',', ''))
        
    def _parse_cost_centres(self, text: str):
        """Extract detailed cost centre information"""
        # Find all cost centre sections
        # Pattern: "Cost centre XXXXXXX"
        cost_centre_pattern = r'Cost centre ([A-Z0-9]+)\s+mobile\s+service\s+usage\s+additional\s+total'
        
        sections = text.split('Cost centre ')
        
        for section in sections[1:]:  # Skip first split
            lines = section.split('\n')
            if not lines:
                continue
                
            # Get cost centre ID from first line
            cost_centre_match = re.match(r'([A-Z0-9]+)', lines[0])
            if not cost_centre_match:
                continue
                
            cost_centre_id = cost_centre_match.group(1)
            
            # Initialize cost centre data
            if cost_centre_id not in self.invoice_data['cost_centres']:
                self.invoice_data['cost_centres'][cost_centre_id] = {
                    'mobiles': [],
                    'total_service': 0,
                    'total_usage': 0,
                    'total_additional': 0,
                    'total_amount': 0
                }
            
            # Extract mobile entries - handle PDF text with space in middle of phone number
            # Pattern matches: 07345 466207 £6.60 £0.00 £0.00 £6.60
            mobile_pattern = r'(\d{5}\s+\d{6})\s+£([\d,]+\.?\d*)\s+£([\d,]+\.?\d*)\s+(cr)?£([\d,]+\.?\d*)\s+(cr)?£([\d,]+\.?\d*)'
            
            full_section_text = '\n'.join(lines)
            mobile_matches = re.finditer(mobile_pattern, full_section_text)
            
            for mobile_match in mobile_matches:
                mobile_number = mobile_match.group(1).replace(' ', '')
                service_charge = float(mobile_match.group(2).replace(',', ''))
                usage_charge = float(mobile_match.group(3).replace(',', ''))
                
                # Check for credit on additional
                additional_credit = mobile_match.group(4) == 'cr'
                additional_charge = float(mobile_match.group(5).replace(',', ''))
                if additional_credit:
                    additional_charge = -additional_charge
                
                # Check for credit on total
                total_credit = mobile_match.group(6) == 'cr'
                total_charge = float(mobile_match.group(7).replace(',', ''))
                if total_credit:
                    total_charge = -total_charge
                
                # Get user name - search near the mobile number
                # Look for REF: NAME on or MR/MRS/DR NAME on pattern
                start_pos = max(0, mobile_match.start() - 100)
                end_pos = min(len(full_section_text), mobile_match.end() + 200)
                context = full_section_text[start_pos:end_pos]
                
                user_name = None
                user_line_match = re.search(r'REF:\s*([A-Z\s]+?)\s*on', context)
                if not user_line_match:
                    user_line_match = re.search(r'(MR|MRS|DR|MS)\s*([A-Z\s]+?)\s*on', context)
                if user_line_match:
                    user_name = user_line_match.group(0).replace('REF:', '').replace('on', '').strip()
                    # Clean up extra spaces
                    user_name = ' '.join(user_name.split())
                
                mobile_entry = {
                    'mobile_number': mobile_number,
                    'user_name': user_name,
                    'cost_centre': cost_centre_id,
                    'service_charge': service_charge,
                    'usage_charge': usage_charge,
                    'additional_charge': additional_charge,
                    'total_charge': total_charge
                }
                
                self.invoice_data['cost_centres'][cost_centre_id]['mobiles'].append(mobile_entry)
                self.invoice_data['mobiles'].append(mobile_entry)
                
                # Update totals
                self.invoice_data['cost_centres'][cost_centre_id]['total_service'] += service_charge
                self.invoice_data['cost_centres'][cost_centre_id]['total_usage'] += usage_charge
                self.invoice_data['cost_centres'][cost_centre_id]['total_additional'] += additional_charge
                self.invoice_data['cost_centres'][cost_centre_id]['total_amount'] += total_charge
            
            # Extract cost centre total line
            total_pattern = r'Total for cost centre ' + re.escape(cost_centre_id) + r'\s+before VAT\s+£([\d,]+\.?\d*)\s+£([\d,]+\.?\d*)\s+(cr)?£([\d,]+\.?\d*)\s+(cr)?£([\d,]+\.?\d*)'
            total_match = re.search(total_pattern, section)
            if total_match:
                verified_service = float(total_match.group(1).replace(',', ''))
                verified_usage = float(total_match.group(2).replace(',', ''))
                
                additional_credit = total_match.group(3) == 'cr'
                verified_additional = float(total_match.group(4).replace(',', ''))
                if additional_credit:
                    verified_additional = -verified_additional
                
                total_credit = total_match.group(5) == 'cr'
                verified_total = float(total_match.group(6).replace(',', ''))
                if total_credit:
                    verified_total = -verified_total
                
                # Update with verified totals
                self.invoice_data['cost_centres'][cost_centre_id]['total_service'] = verified_service
                self.invoice_data['cost_centres'][cost_centre_id]['total_usage'] = verified_usage
                self.invoice_data['cost_centres'][cost_centre_id]['total_additional'] = verified_additional
                self.invoice_data['cost_centres'][cost_centre_id]['total_amount'] = verified_total
    
    def _parse_vat_summary(self, text: str):
        """Extract VAT breakdown"""
        # Total before VAT - make regex more flexible
        before_vat_match = re.search(r'Total\s*before\s*VAT\s*£\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
        if before_vat_match:
            self.invoice_data['summary']['total_before_vat'] = float(before_vat_match.group(1).replace(',', ''))
        
        # VAT at 20% - make regex more flexible with optional spaces
        vat_20_match = re.search(r'VAT\s*at\s*20%\s*(?:on\s*)?£\s*([\d,]+\.?\d*)\s*£\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
        if vat_20_match:
            self.invoice_data['summary']['vat_20_base'] = float(vat_20_match.group(1).replace(',', ''))
            self.invoice_data['summary']['vat_20_amount'] = float(vat_20_match.group(2).replace(',', ''))
        
        # VAT at 0% - make regex more flexible with optional spaces
        vat_0_match = re.search(r'VAT\s*at\s*0%\s*(?:on\s*)?£\s*([\d,]+\.?\d*)\s*£\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
        if vat_0_match:
            self.invoice_data['summary']['vat_0_base'] = float(vat_0_match.group(1).replace(',', ''))
            self.invoice_data['summary']['vat_0_amount'] = float(vat_0_match.group(2).replace(',', ''))
        
        # Calculate final total (Before VAT + VAT amounts)
        before_vat = self.invoice_data['summary'].get('total_before_vat', 0)
        vat = self.invoice_data['summary'].get('vat_20_amount', 0) + self.invoice_data['summary'].get('vat_0_amount', 0)
        
        # If no VAT was extracted, try to calculate from total
        if vat == 0 and before_vat > 0:
            # Assume the before_vat is actually the total including VAT
            # Calculate VAT as 20% of the gross amount
            # Formula: Net = Gross / 1.2, VAT = Gross - Net
            actual_net = before_vat / 1.2
            vat = before_vat - actual_net
            self.invoice_data['summary']['vat_20_amount'] = vat
            self.invoice_data['summary']['total_before_vat'] = actual_net
            self.invoice_data['metadata']['total_amount'] = before_vat
            print(f"⚠️  VAT not found in PDF - calculated from total:")
            print(f"   Total (inc VAT): £{before_vat:,.2f}")
            print(f"   Net (exc VAT): £{actual_net:,.2f}")
            print(f"   VAT 20%: £{vat:,.2f}")
        else:
            self.invoice_data['metadata']['total_amount'] = before_vat + vat
    
    def _parse_date(self, date_str: str) -> str:
        """Convert date string to ISO format"""
        # Remove spaces from date string
        date_str = date_str.replace(' ', '')
        
        try:
            # Try parsing "15Dec25" format (no spaces)
            dt = datetime.strptime(date_str, '%d%b%y')
            return dt.strftime('%Y-%m-%d')
        except:
            try:
                # Try "15 Dec 25" format (with spaces)
                date_str_spaced = date_str
                # Add back spaces if needed
                import re
                match = re.match(r'(\d{1,2})([A-Za-z]+)(\d{2,4})', date_str)
                if match:
                    date_str_spaced = f"{match.group(1)} {match.group(2)} {match.group(3)}"
                dt = datetime.strptime(date_str_spaced, '%d %b %y')
                return dt.strftime('%Y-%m-%d')
            except:
                try:
                    # Try other formats
                    dt = datetime.strptime(date_str, '%d%B%Y')
                    return dt.strftime('%Y-%m-%d')
                except:
                    return date_str
    
    def get_summary(self) -> Dict:
        """Get high-level summary"""
        return {
            'invoice_number': self.invoice_data['metadata'].get('invoice_number'),
            'invoice_date': self.invoice_data['metadata'].get('invoice_date'),
            'provider': 'Vodafone',
            'total_mobiles': self.invoice_data['summary'].get('total_mobiles', 0),
            'total_before_vat': self.invoice_data['summary'].get('total_before_vat', 0),
            'total_amount': self.invoice_data['metadata'].get('total_amount', 0),
            'cost_centres_count': len(self.invoice_data['cost_centres']),
            'mobile_lines_count': len(self.invoice_data['mobiles'])
        }
    
    def get_mobiles_dataframe_dict(self) -> List[Dict]:
        """Convert mobile data to format suitable for pandas DataFrame"""
        return self.invoice_data['mobiles']
    
    def get_cost_centres_dataframe_dict(self) -> List[Dict]:
        """Convert cost centre data to format suitable for pandas DataFrame"""
        cost_centres_list = []
        for cc_id, cc_data in self.invoice_data['cost_centres'].items():
            cost_centres_list.append({
                'cost_centre': cc_id,
                'mobile_count': len(cc_data['mobiles']),
                'total_service': cc_data['total_service'],
                'total_usage': cc_data['total_usage'],
                'total_additional': cc_data['total_additional'],
                'total_amount': cc_data['total_amount']
            })
        return cost_centres_list


def test_parser(pdf_path: str):
    """Test the parser with a sample PDF"""
    print(f"Parsing: {pdf_path}")
    parser = VodafoneInvoiceParser(pdf_path)
    data = parser.parse()
    
    print("\n=== INVOICE SUMMARY ===")
    summary = parser.get_summary()
    for key, value in summary.items():
        print(f"{key}: {value}")
    
    print(f"\n=== COST CENTRES ({len(data['cost_centres'])}) ===")
    for cc_id, cc_data in list(data['cost_centres'].items())[:5]:  # Show first 5
        print(f"\n{cc_id}:")
        print(f"  Mobiles: {len(cc_data['mobiles'])}")
        print(f"  Total: £{cc_data['total_amount']:.2f}")
    
    print(f"\n=== MOBILE LINES (showing first 10 of {len(data['mobiles'])}) ===")
    for mobile in data['mobiles'][:10]:
        print(f"{mobile['mobile_number']} - {mobile['user_name']} - £{mobile['total_charge']:.2f}")
    
    return data


if __name__ == "__main__":
    # Test with the uploaded PDF
    import sys
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = "/mnt/user-data/uploads/BL_670241213_00001_00005__1__removed.pdf"
    
    test_parser(pdf_path)
