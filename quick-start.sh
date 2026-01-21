#!/bin/bash

# Vodafone Dashboard - Quick Start Script

echo "🚀 Vodafone Dashboard - PDF Edition Setup"
echo "=========================================="
echo ""

echo "Step 1: Installing Python dependencies..."
pip install -r requirements.txt --break-system-packages

echo ""
echo "Step 2: Testing PDF parser..."
python pdf_parser.py

echo ""
echo "Step 3: Testing database import..."
python import_from_pdf.py

echo ""
echo "Step 4: Installing Node.js dependencies..."
npm install

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 To run the application:"
echo ""
echo "Terminal 1 - Start Backend:"
echo "  python api.py"
echo ""
echo "Terminal 2 - Start Frontend:"
echo "  npm run dev"
echo ""
echo "Then open: http://localhost:3000"
echo ""
