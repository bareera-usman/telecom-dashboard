
"""
FastAPI Backend for Telecom Dashboard with PDF and Excel Upload
DEBUG VERSION with logging
"""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import tempfile
import sqlite3

# Import our parsers and importer
import sys
sys.path.append(os.path.dirname(__file__))

from pdf_parser import VodafoneInvoiceParser
from three_pdf_parser import ThreePDFParser

app = FastAPI(title="Telecom Dashboard API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://telecom-dashboard.vercel.app",
        "https://telecom-dashboard-bareera-usmans-projects.vercel.app",
        "https://*.vercel.app",
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection
DB_PATH = 'telecom_dashboard.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize database with tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
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
            total_for_mobiles REAL,
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
            recurring_charge REAL,
            oneoff_charge REAL,
            adjustment_charge REAL,
            total_charge REAL,
            location TEXT,
            FOREIGN KEY (invoice_id) REFERENCES invoices(id)
        )
    ''')
    
    # Cost centres table
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
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

# Initialize database on startup
init_database()

@app.get("/")
async def root():
    return {"message": "Telecom Dashboard API", "version": "2.1 - DEBUGGED"}

@app.post("/api/upload-invoice")
async def upload_invoice(file: UploadFile = File(...), overwrite: bool = False):
    """Upload and process a Vodafone or Three PDF invoice"""
    file_extension = file.filename.lower().split('.')[-1]
    
    print(f"\n{'='*60}")
    print(f"📤 UPLOAD REQUEST: {file.filename}")
    print(f"   Extension: {file_extension}")
    print(f"{'='*60}")
    
    # Accept only PDFs now
    if file_extension not in ['pdf']:
        raise HTTPException(
            status_code=400, 
            detail="Only PDF files are accepted (Vodafone or Three invoices)"
        )
    
    try:
        # Save uploaded file to temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_extension}') as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        print(f"💾 Saved to temp: {tmp_path}")
        
        # Parse based on PDF content - detect provider
        try:
            import PyPDF2
            with open(tmp_path, 'rb') as pdf_file:
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                first_page = pdf_reader.pages[0].extract_text()
                
                # Detect provider
                if 'Vodafone' in first_page or 'vodafone' in first_page.lower():
                    provider = 'Vodafone'
                    print("📄 Detected: Vodafone PDF")
                    parser = VodafoneInvoiceParser(tmp_path)
                elif 'Three' in first_page or 'Hutchison 3G' in first_page:
                    provider = 'Three'
                    print("📄 Detected: Three PDF")
                    parser = ThreePDFParser(tmp_path)
                else:
                    raise ValueError("Could not detect provider. Please upload a Vodafone or Three invoice PDF.")
            
            data = parser.parse()
            
            # DEBUG: Print what we parsed
            print(f"\n🔍 PARSED DATA:")
            print(f"   Invoice: {data['metadata'].get('invoice_number')}")
            print(f"   Date: {data['metadata'].get('invoice_date')}")
            print(f"   Mobiles: {data['summary'].get('total_mobiles')}")
            print(f"   Before VAT: £{data['summary'].get('total_before_vat', 0):,.2f}")
            print(f"   VAT: £{data['summary'].get('vat_20_amount', 0) + data['summary'].get('vat_0_amount', 0):,.2f}")
            print(f"   TOTAL (metadata): £{data['metadata'].get('total_amount', 0):,.2f}")
            print(f"   TOTAL (summary): £{data['summary'].get('total_amount', 0):,.2f}")
            
            # Import to database
            invoice_id = import_invoice_to_db(data, provider, overwrite)
            
            # Get the imported invoice details
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM invoices WHERE id = ?', (invoice_id,))
            invoice = dict(cursor.fetchone())
            conn.close()
            
            print(f"\n💾 SAVED TO DATABASE:")
            print(f"   ID: {invoice['id']}")
            print(f"   Total Amount: £{invoice['total_amount']:,.2f}")
            print(f"{'='*60}\n")
            
            return {
                "success": True,
                "message": f"Successfully imported {provider} invoice {invoice['invoice_number']}",
                "invoice_id": invoice_id,
                "invoice": invoice
            }
        finally:
            # Clean up temp file
            os.unlink(tmp_path)
            
    except ValueError as e:
        print(f"❌ ValueError: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

def import_invoice_to_db(data, provider, overwrite=False):
    """Import parsed invoice data to database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    metadata = data['metadata']
    summary = data['summary']
    invoice_number = metadata.get('invoice_number')
    
    if not invoice_number:
        raise ValueError("Could not extract invoice number")
    
    # Check if exists
    cursor.execute('SELECT id FROM invoices WHERE invoice_number = ?', (invoice_number,))
    existing = cursor.fetchone()
    
    if existing and not overwrite:
        conn.close()
        raise ValueError(f"Invoice {invoice_number} already exists")
    
    if existing and overwrite:
        invoice_id = existing[0]
        cursor.execute('DELETE FROM mobile_lines WHERE invoice_id = ?', (invoice_id,))
        cursor.execute('DELETE FROM cost_centres WHERE invoice_id = ?', (invoice_id,))
        cursor.execute('DELETE FROM invoices WHERE id = ?', (invoice_id,))
        print(f"♻️  Deleted existing invoice {invoice_number}")
    
    # Calculate values
    vat_amount = summary.get('vat_20_amount', 0) + summary.get('vat_0_amount', 0)
    before_vat = summary.get('total_before_vat', 0)
    
    # Get total_amount - try metadata first, then summary, then calculate
    total_amount = metadata.get('total_amount')
    if not total_amount or total_amount == 0:
        total_amount = summary.get('total_amount', 0)
    if not total_amount or total_amount == 0:
        total_amount = before_vat + vat_amount
    
    print(f"\n💰 AMOUNTS TO INSERT:")
    print(f"   Before VAT: £{before_vat:,.2f}")
    print(f"   VAT: £{vat_amount:,.2f}")
    print(f"   TOTAL: £{total_amount:,.2f}")
    
    # Insert invoice
    cursor.execute('''
        INSERT INTO invoices (
            invoice_number, account_number, provider, invoice_date,
            payment_due_date, total_mobiles, total_for_mobiles, total_before_vat, 
            total_vat, total_amount, ecs_extra_advisor, unallocated_mobiles
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        invoice_number,
        metadata.get('account_number'),
        provider,
        metadata.get('invoice_date'),
        metadata.get('payment_due_date'),
        summary.get('total_mobiles', 0),
        summary.get('total_for_mobiles', before_vat),
        before_vat,
        vat_amount,
        total_amount,
        summary.get('ecs_extra_advisor', 0),
        summary.get('unallocated_mobiles', 0)
    ))
    
    invoice_id = cursor.lastrowid
    print(f"✅ Inserted invoice with ID: {invoice_id}")
    
    # Insert mobile lines
    if data['mobiles']:
        for mobile in data['mobiles']:
            cursor.execute('''
                INSERT INTO mobile_lines (
                    invoice_id, mobile_number, user_name, cost_centre,
                    service_charge, usage_charge, additional_charge,
                    recurring_charge, oneoff_charge, adjustment_charge,
                    total_charge, location
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                invoice_id,
                mobile['mobile_number'],
                mobile.get('user_name'),
                mobile.get('cost_centre'),
                mobile.get('service_charge', 0),
                mobile.get('usage_charge', 0),
                mobile.get('additional_charge', 0),
                mobile.get('recurring_charge', 0),
                mobile.get('oneoff_charge', 0),
                mobile.get('adjustment_charge', 0),
                mobile['total_charge'],
                mobile.get('location')
            ))
        print(f"✅ Inserted {len(data['mobiles'])} mobile lines")
    
    # Insert cost centres
    if data['cost_centres']:
        cc_count = 0
        for cc_id, cc_data in data['cost_centres'].items():
            if isinstance(cc_data, dict):
                cursor.execute('''
                    INSERT INTO cost_centres (
                        invoice_id, cost_centre, mobile_count,
                        total_service, total_usage, total_additional, total_amount
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    invoice_id,
                    cc_id,
                    len(cc_data.get('mobiles', [])),
                    cc_data.get('total_service', 0),
                    cc_data.get('total_usage', 0),
                    cc_data.get('total_additional', 0),
                    cc_data.get('total_amount', 0)
                ))
                cc_count += 1
        print(f"✅ Inserted {cc_count} cost centres")
    
    conn.commit()
    conn.close()
    
    return invoice_id

@app.get("/api/invoices")
async def get_invoices():
    """Get list of all imported invoices"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM invoices ORDER BY invoice_date DESC')
        invoices = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return {
            "success": True,
            "invoices": invoices
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/invoice/{invoice_id}")
async def get_invoice(invoice_id: int):
    """Get detailed invoice information"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM invoices WHERE id = ?', (invoice_id,))
        invoice = cursor.fetchone()
        
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        
        cursor.execute('SELECT * FROM mobile_lines WHERE invoice_id = ?', (invoice_id,))
        mobile_lines = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute('SELECT * FROM cost_centres WHERE invoice_id = ?', (invoice_id,))
        cost_centres = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            "success": True,
            "invoice": dict(invoice),
            "mobile_lines": mobile_lines,
            "cost_centres": cost_centres
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/monthly-trends")
async def get_monthly_trends():
    """Get monthly cost trends"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
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
        ''')
        trends = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return {
            "success": True,
            "trends": trends
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/cost-centres")
async def get_cost_centre_analytics():
    """Get cost centre analytics across all invoices"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                cc.cost_centre,
                COUNT(DISTINCT cc.invoice_id) as months_active,
                SUM(cc.mobile_count) as total_mobiles,
                AVG(cc.total_amount) as avg_monthly_cost,
                SUM(cc.total_amount) as total_cost
            FROM cost_centres cc
            JOIN invoices i ON cc.invoice_id = i.id
            GROUP BY cc.cost_centre
            ORDER BY total_cost DESC
        ''')
        cost_centres = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return {
            "success": True,
            "cost_centres": cost_centres
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/top-vodafone-spenders")
async def get_top_vodafone_spenders():
    """
    Get top 10 cost centres spending with Vodafone (OLD LOGIC restored).
    This aggregates by cost centre across Vodafone invoices.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                cc.cost_centre,
                COUNT(DISTINCT cc.invoice_id) AS invoice_count,
                SUM(cc.mobile_count) AS total_mobiles,
                SUM(cc.total_amount) AS total_spent,
                AVG(cc.total_amount * 1.0 / NULLIF(cc.mobile_count, 0)) AS avg_cost_per_mobile
            FROM cost_centres cc
            JOIN invoices i ON cc.invoice_id = i.id
            WHERE i.provider = 'Vodafone'
            GROUP BY cc.cost_centre
            ORDER BY total_spent DESC
            LIMIT 10
        ''')
        
        top_spenders = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return {
            "success": True,
            "top_spenders": top_spenders
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/provider-comparison")
async def get_provider_comparison():
    """Get detailed comparison using last 4 months of each provider for fair comparison"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get ALL invoices for each provider, sorted by date
        cursor.execute('''
            SELECT 
                provider,
                invoice_number,
                invoice_date,
                total_mobiles,
                total_amount,
                total_before_vat,
                total_vat,
                (total_amount * 1.0 / NULLIF(total_mobiles, 0)) AS cost_per_mobile
            FROM invoices
            ORDER BY provider, invoice_date DESC
        ''')
        
        all_invoices = [dict(row) for row in cursor.fetchall()]
        
        # Group by provider
        provider_invoices = {}
        for invoice in all_invoices:
            provider = invoice['provider']
            provider_invoices.setdefault(provider, []).append(invoice)
        
        # Calculate stats for each provider
        providers = {}
        comparison_data = {}
        
        for provider, invoices in provider_invoices.items():
            # Get LAST 4 months for fair comparison
            last_4_invoices = sorted(invoices, key=lambda x: x['invoice_date'], reverse=True)[:4]
            last_4_invoices = sorted(last_4_invoices, key=lambda x: x['invoice_date'])  # Re-sort chronologically
            
            # Calculate per-mobile costs for each of the last 4 months
            per_mobile_costs = [inv['cost_per_mobile'] for inv in last_4_invoices if inv['cost_per_mobile']]
            avg_cost_per_mobile_last_4 = (sum(per_mobile_costs) / len(per_mobile_costs)) if per_mobile_costs else 0.0
            
            # Calculate average monthly cost for last 4 months
            monthly_totals = [inv['total_amount'] for inv in last_4_invoices]
            avg_monthly_cost_last_4 = (sum(monthly_totals) / len(monthly_totals)) if monthly_totals else 0.0
            
            # Get current mobile count from most recent invoice
            latest_invoice = sorted(invoices, key=lambda x: x['invoice_date'], reverse=True)[0]
            current_mobile_count = latest_invoice['total_mobiles']
            
            # Total spent across ALL invoices (for info)
            total_spent_all = sum(inv['total_amount'] for inv in invoices)
            
            providers[provider] = {
                'provider': provider,
                'total_invoices': len(invoices),
                'invoices_in_comparison': len(last_4_invoices),
                'current_mobile_count': current_mobile_count,
                'total_spent_all_time': total_spent_all,
                'avg_monthly_cost_last_4': avg_monthly_cost_last_4,
                'avg_cost_per_mobile_last_4': avg_cost_per_mobile_last_4,
                'first_invoice': min(invoices, key=lambda x: x['invoice_date'])['invoice_date'],
                'last_invoice': latest_invoice['invoice_date'],
                'comparison_period_start': last_4_invoices[0]['invoice_date'] if last_4_invoices else None,
                'comparison_period_end': last_4_invoices[-1]['invoice_date'] if last_4_invoices else None,
                'last_4_invoices': last_4_invoices,
                'all_invoices': invoices
            }
            
            comparison_data[provider] = {
                'per_mobile_costs': per_mobile_costs,
                'monthly_costs': monthly_totals,
                'invoices': last_4_invoices
            }
        
        # Calculate savings if both providers exist
        savings = None
        predictions = None
        if 'Vodafone' in providers and 'Three' in providers:
            vodafone_per_mobile = providers['Vodafone']['avg_cost_per_mobile_last_4']
            three_per_mobile = providers['Three']['avg_cost_per_mobile_last_4']
            
            vodafone_monthly = providers['Vodafone']['avg_monthly_cost_last_4']
            three_monthly = providers['Three']['avg_monthly_cost_last_4']
            
            # Savings calculations
            savings_per_mobile_monthly = three_per_mobile - vodafone_per_mobile
            savings_per_mobile_annual = savings_per_mobile_monthly * 12
            
            savings_monthly = three_monthly - vodafone_monthly
            savings_annual = savings_monthly * 12
            
            savings_percentage = (savings_monthly / three_monthly) * 100 if three_monthly > 0 else 0
            
            # Calculate what you'd pay with Three vs what you actually pay
            current_vodafone_mobiles = providers['Vodafone']['current_mobile_count']
            would_pay_with_three = three_per_mobile * current_vodafone_mobiles
            actual_vodafone_cost = vodafone_monthly
            
            savings = {
                'per_mobile_monthly': savings_per_mobile_monthly,
                'per_mobile_annual': savings_per_mobile_annual,
                'total_monthly': savings_monthly,
                'total_annual': savings_annual,
                'percentage': savings_percentage,
                'vodafone_avg_per_mobile': vodafone_per_mobile,
                'three_avg_per_mobile': three_per_mobile,
                'vodafone_avg_monthly_cost': vodafone_monthly,
                'three_avg_monthly_cost': three_monthly,
                'based_on_mobiles': current_vodafone_mobiles,
                'would_pay_with_three': would_pay_with_three,
                'actually_paying_vodafone': actual_vodafone_cost,
                'comparison_months': 4,
                'three_comparison_period': f"{providers['Three']['comparison_period_start']} to {providers['Three']['comparison_period_end']}" if providers['Three']['comparison_period_start'] else None,
                'vodafone_comparison_period': f"{providers['Vodafone']['comparison_period_start']} to {providers['Vodafone']['comparison_period_end']}" if providers['Vodafone']['comparison_period_start'] else None
            }
            
            # PREDICTIONS AND FORECASTS (based on historical averages)
            three_total_historical = providers['Three']['total_spent_all_time']
            three_months_count = providers['Three']['total_invoices']
            three_avg_monthly_historical = (three_total_historical / three_months_count) if three_months_count > 0 else 0
            
            vodafone_avg_monthly = providers['Vodafone']['avg_monthly_cost_last_4']
            three_annualized_historical = three_avg_monthly_historical * 12
            vodafone_projected_annual = vodafone_avg_monthly * 12
            if_continued_three_annual = three_avg_monthly_historical * 12
            projected_annual_savings = if_continued_three_annual - vodafone_projected_annual
            
            predictions = {
                'three_historical_total': three_total_historical,
                'three_historical_months': three_months_count,
                'three_avg_monthly_historical': three_avg_monthly_historical,
                'three_annualized_historical': three_annualized_historical,
                'vodafone_avg_monthly_current': vodafone_avg_monthly,
                'vodafone_projected_annual': vodafone_projected_annual,
                'if_continued_three_annual': if_continued_three_annual,
                'projected_annual_savings': projected_annual_savings,
                'three_period': f"{providers['Three']['first_invoice']} to {providers['Three']['last_invoice']}",
                'vodafone_period': f"{providers['Vodafone']['first_invoice']} to {providers['Vodafone']['last_invoice']}"
            }
        
        # Get monthly breakdown for ALL invoices
        cursor.execute('''
            SELECT 
                strftime('%Y-%m', invoice_date) AS month,
                provider,
                invoice_number,
                total_mobiles,
                total_amount,
                total_before_vat,
                total_vat,
                (total_amount * 1.0 / NULLIF(total_mobiles, 0)) AS cost_per_mobile
            FROM invoices
            ORDER BY invoice_date, provider
        ''')
        
        monthly_breakdown = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            "success": True,
            "providers": providers,
            "savings": savings,
            "predictions": predictions,
            "monthly_breakdown": monthly_breakdown,
            "comparison_data": comparison_data
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def get_dashboard_stats():
    """Get overall dashboard statistics with CORRECT logic"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Overall stats
        cursor.execute('''
            SELECT 
                COUNT(DISTINCT id) AS total_invoices,
                SUM(total_amount) AS total_spent,
                AVG(total_amount * 1.0 / NULLIF(total_mobiles, 0)) AS avg_cost_per_mobile,
                MIN(invoice_date) AS earliest_invoice,
                MAX(invoice_date) AS latest_invoice
            FROM invoices
        ''')
        stats = dict(cursor.fetchone())
        
        # Get CURRENT mobile count from most recent invoice (not sum!)
        cursor.execute('''
            SELECT total_mobiles 
            FROM invoices 
            ORDER BY invoice_date DESC 
            LIMIT 1
        ''')
        latest = cursor.fetchone()
        stats['current_mobile_lines'] = latest['total_mobiles'] if latest else 0
        
        # Provider breakdown
        cursor.execute('''
            SELECT 
                provider,
                COUNT(*) AS invoice_count,
                SUM(total_amount) AS total_cost,
                AVG(total_amount * 1.0 / NULLIF(total_mobiles, 0)) AS avg_per_mobile
            FROM invoices
            GROUP BY provider
        ''')
        providers = []
        for row in cursor.fetchall():
            provider_data = dict(row)
            
            # Get current mobile count for this provider
            cursor.execute('''
                SELECT total_mobiles 
                FROM invoices 
                WHERE provider = ? 
                ORDER BY invoice_date DESC 
                LIMIT 1
            ''', (row['provider'],))
            latest_prov = cursor.fetchone()
            provider_data['current_mobiles'] = latest_prov['total_mobiles'] if latest_prov else 0
            
            providers.append(provider_data)
        
        conn.close()
        
        return {
            "success": True,
            "stats": stats,
            "by_provider": providers
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/invoice/{invoice_id}")
async def delete_invoice(invoice_id: int):
    """Delete an invoice and all associated data"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT invoice_number FROM invoices WHERE id = ?', (invoice_id,))
        invoice = cursor.fetchone()
        
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        
        cursor.execute('DELETE FROM mobile_lines WHERE invoice_id = ?', (invoice_id,))
        cursor.execute('DELETE FROM cost_centres WHERE invoice_id = ?', (invoice_id,))
        cursor.execute('DELETE FROM invoices WHERE id = ?', (invoice_id,))
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "message": f"Successfully deleted invoice {invoice[0]}"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("🚀 TELECOM DASHBOARD API - DEBUG MODE")
    print("="*60 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
