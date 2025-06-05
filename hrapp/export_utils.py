import os
from io import BytesIO
from datetime import datetime
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import xlsxwriter


# export_utils.py
import os
from io import BytesIO
from datetime import datetime
from django.http import HttpResponse
from django.conf import settings
import xlsxwriter
import xlwt

import xlsxwriter
from io import BytesIO
from datetime import datetime
from django.http import HttpResponse

def export_to_excel(candidates, filename="matching_candidates"):
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet("Matched Candidates")

    # Define formats
    header_format = workbook.add_format({
        'bold': True,
        'align': 'center',
        'valign': 'vcenter',
        'fg_color': '#4472C4',
        'font_color': 'white',
        'border': 1
    })
    
    text_format = workbook.add_format({'num_format': '@'})  # Force text format
    number_format = workbook.add_format({'num_format': '0.00'})

    # Column configuration
    columns = [
        ('Name', 25),
        ('Match Score (%)', 15),
        ('Experience (Years)', 18),
        ('Email', 30),
        ('Phone', 20),
        ('Matched Skills', 40),
        ('Missing Skills', 40)
    ]

    # Write headers
    for col_idx, (header, width) in enumerate(columns):
        worksheet.set_column(col_idx, col_idx, width)
        worksheet.write(0, col_idx, header, header_format)

    # Data processing with error handling
    for row_idx, candidate in enumerate(candidates, start=1):
        try:
            # Safe value extraction
            def get_value(key, default='N/A'):
                value = candidate.get(key)
                if value is None:
                    return default
                if isinstance(value, str):
                    return value.strip() or default
                return value

            # Process numeric fields
            def get_float(key, default=0.0):
                try:
                    value = candidate.get(key)
                    if isinstance(value, str):
                        # Remove non-numeric characters
                        value = ''.join(c for c in value if c.isdigit() or c in ('.', '-'))
                    return float(value) if value not in (None, '') else default
                except (TypeError, ValueError):
                    return default

            # Extract all values
            name = get_value('name')
            score = get_float('score')
            experience = get_float('experience')
            email = get_value('email')
            phone = get_value('phone')
            
            # Force text format for phone numbers
            if str(phone).strip() not in ('', 'N/A'):
                phone = f"'{phone}"  # Prepend apostrophe to force text format

            # Process skills lists
            matched_skills = ', '.join(map(str, candidate.get('matched_skills', []))) or 'None'
            missing_skills = ', '.join(map(str, candidate.get('missing_skills', []))) or 'None'

            # Write data to worksheet
            worksheet.write(row_idx, 0, name, text_format)
            worksheet.write_number(row_idx, 1, score, number_format)
            worksheet.write_number(row_idx, 2, experience, number_format)
            worksheet.write(row_idx, 3, email, text_format)
            worksheet.write(row_idx, 4, phone, text_format)
            worksheet.write(row_idx, 5, matched_skills, text_format)
            worksheet.write(row_idx, 6, missing_skills, text_format)

        except Exception as e:
            print(f"Error processing row {row_idx}: {str(e)}")
            continue

    workbook.close()
    output.seek(0)
    
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="{filename}_{datetime.now().date()}.xlsx"'}
    )
    return response

def export_to_pdf(candidates, filename="matching_candidates"):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    title = Paragraph("Matching Candidates Report", styles['Title'])
    elements.append(title)

    # Date
    date_text = Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal'])
    elements.append(date_text)

    # Add space
    elements.append(Paragraph("<br/><br/>", styles['Normal']))

    # Prepare data for table
    data = [
        [
            "Rank", "Candidate", "Score (%)", 
            "Experience", "Matched Skills", "Missing Skills"
        ]
    ]

    for idx, candidate in enumerate(candidates, start=1):
        print(f"DEBUG: Candidate matched_skills = {candidate.get('matched_skills')}")

        data.append([
            str(idx),
            candidate.get('name', 'N/A'),
            f"{candidate.get('score', 0):.1f}",
            str(candidate.get('experience', 0)),
            ', '.join(candidate.get('matched_skills', [])) if candidate.get('matched_skills') else 'None',
            ', '.join(candidate.get('missing_skills', [])) if candidate.get('missing_skills') else 'None'

        ])

    # Create table
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    # Add conditional formatting for scores
    for row in range(1, len(data)):
        score = float(data[row][2])
        if score >= 75:
            bg_color = colors.HexColor('#C6EFCE')
            text_color = colors.HexColor('#006100')
        elif score >= 50:
            bg_color = colors.HexColor('#FFEB9C')
            text_color = colors.HexColor('#9C5700')
        else:
            bg_color = colors.HexColor('#FFC7CE')
            text_color = colors.HexColor('#9C0006')
        
        table.setStyle(TableStyle([
            ('BACKGROUND', (2, row), (2, row), bg_color),
            ('TEXTCOLOR', (2, row), (2, row), text_color),
        ]))

    elements.append(table)
    doc.build(elements)
    
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}_{datetime.now().date()}.pdf"'
    return response