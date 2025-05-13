import os
from io import BytesIO
from datetime import datetime
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import xlsxwriter

def export_to_excel(candidates, filename="matching_candidates"):
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet()

    # Header format
    header_format = workbook.add_format({
        'bold': True,
        'align': 'center',
        'valign': 'vcenter',
        'fg_color': '#4472C4',
        'font_color': 'white',
        'border': 1
    })

    # Data formats
    even_row = workbook.add_format({'bg_color': '#E9E9E9', 'border': 1})
    odd_row = workbook.add_format({'bg_color': '#FFFFFF', 'border': 1})
    high_score = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100', 'border': 1})
    medium_score = workbook.add_format({'bg_color': '#FFEB9C', 'font_color': '#9C5700', 'border': 1})
    low_score = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006', 'border': 1})

    # Write headers
    headers = [
        "Rank", "Candidate Name", "Match Score (%)", 
        "Experience (Years)", "Matched Skills", "Missing Skills"
    ]
    for col, header in enumerate(headers):
        worksheet.write(0, col, header, header_format)

    # Write data
    for row, candidate in enumerate(candidates, start=1):
        # Determine row format based on score
        if candidate['score'] >= 65:
            row_format = high_score
        elif candidate['score'] >= 30:
            row_format = medium_score
        else:
            row_format = low_score

        # Apply alternating row colors
        if row % 2 == 0:
            row_format.set_bg_color('#E9E9E9')
        else:
            row_format.set_bg_color('#FFFFFF')

        data = [
            row,  # Rank
            candidate.get('name', 'N/A'),
            candidate.get('score', 0),
            candidate.get('experience', 0),
            ', '.join(candidate.get('matched_skills', []) or 'None'),
            ', '.join(candidate.get('missing_skills', []) or 'None')
        ]

        for col, value in enumerate(data):
            worksheet.write(row, col, value, row_format)

    # Adjust column widths
    worksheet.set_column(0, 0, 8)   # Rank
    worksheet.set_column(1, 1, 25)  # Name
    worksheet.set_column(2, 2, 15)  # Score
    worksheet.set_column(3, 3, 15)  # Experience
    worksheet.set_column(4, 4, 40)  # Matched Skills
    worksheet.set_column(5, 5, 40)  # Missing Skills

    # Add filters
    worksheet.autofilter(0, 0, row, len(headers)-1)

    workbook.close()
    output.seek(0)
    
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}_{datetime.now().date()}.xlsx"'
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
        data.append([
            str(idx),
            candidate.get('name', 'N/A'),
            f"{candidate.get('score', 0):.1f}",
            str(candidate.get('experience', 0)),
            ', '.join(candidate.get('matched_skills', []) or 'None'),
            ', '.join(candidate.get('missing_skills', []) or 'None')
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