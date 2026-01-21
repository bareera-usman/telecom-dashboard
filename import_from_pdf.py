"""
Database Import Script for Vodafone PDF Invoices
Imports parsed PDF data into SQLite database
"""

import sqlite3
import pandas as pd
from pdf_parser import VodafoneInvoiceParser
from datetime import datetime
import os

class InvoiceImporter:
    def __init__(self, db_path='telecom_dashboard.db'):
        self.db_path = db_path
        self.conn = None
        self._init_database()
    
    def _init_database(self):
        """Initialize database with required tables"""
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()
        
        # Invoices table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE NOT NULL,
                account_number TEXT,
                provider TEXT NOT NULL,
                invoice_date DATE NOT NULL,
                payment_due_date DATE,
                total_mobiles INTEGER,
                total_before_vat REAL,
                total_vat REAL,
                total_amount REAL,
                ecs_extra_advisor REAL,
                unallocated_mobiles REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Mobile lines table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mobile_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                mobile_number TEXT NOT NULL,
                user_name TEXT,
                cost_centre TEXT,
                service_charge REAL,
                usage_charge REAL,
                additional_charge REAL,
                total_charge REAL,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id)
            )
        ''')
        
        # Cost centres summary table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cost_centres (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                cost_centre TEXT NOT NULL,
                mobile_count INTEGER,
                total_service REAL,
                total_usage REAL,
                total_additional REAL,
                total_amount REAL,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id),
                UNIQUE(invoice_id, cost_centre)
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_invoice_date ON invoices(invoice_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_mobile_invoice ON mobile_lines(invoice_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_mobile_number ON mobile_lines(mobile_number)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cost_centre ON cost_centres(cost_centre)')
        
        self.conn.commit()
    
    def import_pdf(self, pdf_path: str, overwrite=False):
        """Import a Vodafone PDF invoice into the database"""
        print(f"\nProcessing: {pdf_path}")
        
        # Parse the PDF
        parser = VodafoneInvoiceParser(pdf_path)
        data = parser.parse()
        
        metadata = data['metadata']
        summary = data['summary']
        
        invoice_number = metadata.get('invoice_number')
        if not invoice_number:
            raise ValueError("Could not extract invoice number from PDF")
        
        # Check if invoice already exists
        cursor = self.conn.cursor()
        cursor.execute('SELECT id FROM invoices WHERE invoice_number = ?', (invoice_number,))
        existing = cursor.fetchone()
        
        if existing and not overwrite:
            print(f"❌ Invoice {invoice_number} already exists. Use overwrite=True to replace.")
            return existing[0]
        
        if existing and overwrite:
            print(f"♻️  Deleting existing data for invoice {invoice_number}...")
            invoice_id = existing[0]
            cursor.execute('DELETE FROM mobile_lines WHERE invoice_id = ?', (invoice_id,))
            cursor.execute('DELETE FROM cost_centres WHERE invoice_id = ?', (invoice_id,))
            cursor.execute('DELETE FROM invoices WHERE id = ?', (invoice_id,))
            self.conn.commit()
        
        # Insert invoice
        vat_amount = summary.get('vat_20_amount', 0) + summary.get('vat_0_amount', 0)
        
        cursor.execute('''
            INSERT INTO invoices (
                invoice_number, account_number, provider, invoice_date,
                payment_due_date, total_mobiles, total_before_vat, total_vat,
                total_amount, ecs_extra_advisor, unallocated_mobiles
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            invoice_number,
            metadata.get('account_number'),
            'Vodafone',
            metadata.get('invoice_date'),
            metadata.get('payment_due_date'),
            summary.get('total_mobiles', 0),
            summary.get('total_before_vat', 0),
            vat_amount,
            metadata.get('total_amount', 0),
            summary.get('ecs_extra_advisor', 0),
            summary.get('unallocated_mobiles', 0)
        ))
        
        invoice_id = cursor.lastrowid
        print(f"✅ Created invoice record (ID: {invoice_id})")
        
        # Insert mobile lines
        if data['mobiles']:
            mobile_records = [
                (
                    invoice_id,
                    mobile['mobile_number'],
                    mobile['user_name'],
                    mobile['cost_centre'],
                    mobile['service_charge'],
                    mobile['usage_charge'],
                    mobile['additional_charge'],
                    mobile['total_charge']
                )
                for mobile in data['mobiles']
            ]
            
            cursor.executemany('''
                INSERT INTO mobile_lines (
                    invoice_id, mobile_number, user_name, cost_centre,
                    service_charge, usage_charge, additional_charge, total_charge
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', mobile_records)
            print(f"✅ Imported {len(data['mobiles'])} mobile lines")
        
        # Insert cost centres
        if data['cost_centres']:
            cc_records = [
                (
                    invoice_id,
                    cc_id,
                    len(cc_data['mobiles']),
                    cc_data['total_service'],
                    cc_data['total_usage'],
                    cc_data['total_additional'],
                    cc_data['total_amount']
                )
                for cc_id, cc_data in data['cost_centres'].items()
            ]
            
            cursor.executemany('''
                INSERT INTO cost_centres (
                    invoice_id, cost_centre, mobile_count,
                    total_service, total_usage, total_additional, total_amount
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', cc_records)
            print(f"✅ Imported {len(data['cost_centres'])} cost centres")
        
        self.conn.commit()
        print(f"✅ Successfully imported invoice {invoice_number}")
        
        return invoice_id
    
    def get_invoice_summary(self, invoice_id=None):
        """Get summary of imported invoices"""
        if invoice_id:
            query = '''
                SELECT * FROM invoices WHERE id = ?
            '''
            return pd.read_sql_query(query, self.conn, params=(invoice_id,))
        else:
            query = '''
                SELECT * FROM invoices ORDER BY invoice_date DESC
            '''
            return pd.read_sql_query(query, self.conn)
    
    def get_mobile_lines(self, invoice_id):
        """Get all mobile lines for an invoice"""
        query = '''
            SELECT * FROM mobile_lines WHERE invoice_id = ?
        '''
        return pd.read_sql_query(query, self.conn, params=(invoice_id,))
    
    def get_cost_centres(self, invoice_id):
        """Get cost centre breakdown for an invoice"""
        query = '''
            SELECT * FROM cost_centres WHERE invoice_id = ?
        '''
        return pd.read_sql_query(query, self.conn, params=(invoice_id,))
    
    def get_monthly_trends(self):
        """Get monthly cost trends"""
        query = '''
            SELECT 
                strftime('%Y-%m', invoice_date) as month,
                provider,
                SUM(total_before_vat) as total_before_vat,
                SUM(total_amount) as total_amount,
                AVG(total_amount * 1.0 / NULLIF(total_mobiles, 0)) as avg_per_mobile,
                SUM(total_mobiles) as total_mobiles
            FROM invoices
            GROUP BY month, provider
            ORDER BY month
        '''
        return pd.read_sql_query(query, self.conn)
    
    def get_comparison_data(self):
        """Get Three vs Vodafone comparison"""
        query = '''
            SELECT 
                provider,
                COUNT(*) as invoice_count,
                SUM(total_mobiles) as total_mobiles,
                SUM(total_amount) as total_amount,
                AVG(total_amount * 1.0 / NULLIF(total_mobiles, 0)) as avg_per_mobile_per_month
            FROM invoices
            GROUP BY provider
        '''
        return pd.read_sql_query(query, self.conn)
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


def main():
    """Example usage"""
    importer = InvoiceImporter()
    
    # Import the test PDF
    pdf_path = "/mnt/user-data/uploads/BL_670241213_00001_00005__1__removed.pdf"
    
    if os.path.exists(pdf_path):
        invoice_id = importer.import_pdf(pdf_path, overwrite=True)
        
        print("\n" + "="*60)
        print("📊 IMPORT SUMMARY")
        print("="*60)
        
        # Show invoice summary
        summary = importer.get_invoice_summary(invoice_id)
        print("\n📄 Invoice Details:")
        print(summary[['invoice_number', 'invoice_date', 'total_mobiles', 'total_amount']].to_string(index=False))
        
        # Show cost centre breakdown
        cost_centres = importer.get_cost_centres(invoice_id)
        print(f"\n💼 Cost Centres ({len(cost_centres)}):")
        print(cost_centres[['cost_centre', 'mobile_count', 'total_amount']].head(10).to_string(index=False))
        
        # Show sample mobile lines
        mobiles = importer.get_mobile_lines(invoice_id)
        print(f"\n📱 Mobile Lines (showing 10 of {len(mobiles)}):")
        print(mobiles[['mobile_number', 'user_name', 'cost_centre', 'total_charge']].head(10).to_string(index=False))
    
    importer.close()


if __name__ == "__main__":
    main()
