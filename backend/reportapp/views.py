from django.shortcuts import render
from django.http import HttpResponse
from openai import AzureOpenAI
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from io import BytesIO
import os
from reportapp.cosmos_db import container  # Cosmos DB 컨테이너 직접 사용

# 밀도 및 배출계수 테이블 (골판지만)
DENSITY_TABLE = {"골판지": 250}
EMISSION_FACTOR_TABLE = {"골판지": 1.9}

# 영어 변환 테이블
MATERIAL_ENGLISH = {"골판지": "Corrugated Cardboard", "PE필름": "PE Film", "EPS": "EPS"}

client = AzureOpenAI(
    api_key="02phmGcnRkWa0RqPUGrR0pg4sRe7pspjHF908ptIoNqHW3ch9j1RJQQJ99BFACHYHv6XJ3w3AAAAACOGk3Tr",
    api_version="2024-12-01-preview", 
    azure_endpoint="https://student038-5202-resource.cognitiveservices.azure.com/openai/deployments/o4-mini/chat/completions?api-version=2025-01-01-preview/" 
)

def calculate_carbon_saving(old_v, new_v, material):
    density = DENSITY_TABLE[material]
    ef = EMISSION_FACTOR_TABLE[material]
    old_mass = old_v * density
    new_mass = new_v * density
    
    # 절댓값으로 계산 (감축량이므로 항상 양수)
    mass_reduction = abs(old_mass - new_mass)
    emission_reduction = mass_reduction * ef
    
    return {
        "material": material,
        "old_volume": old_v,
        "new_volume": new_v,
        "saved_mass": mass_reduction,
        "saved_emission": emission_reduction
    }

def generate_gpt_report(result):
    prompt = f"""
    포장재: {result['material']}
    기존 부피: {result['old_volume']} m³
    최적화 부피: {result['new_volume']} m³
    감축 질량: {result['saved_mass']:.2f} kg
    감축 탄소배출량: {result['saved_emission']:.2f} kg CO2-eq

    위 데이터를 바탕으로 물류 포장 최적화에 따른 탄소 절감 리포트를 작성해줘. 그리고 이산화탄소 쓸 때는 2를 아래첨자 절대 쓰지말고 그냥 2로 **CO2-eq**로 표기해줘.
    """

    response = client.chat.completions.create(
        model="o4-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

def translate_korean_to_english_simple(korean_text):
    """간단한 한글->영어 변환 (GPT 리포트용)"""
    try:
        # OpenAI로 번역
        response = client.chat.completions.create(
            model="o4-mini",
            messages=[
                {"role": "system", "content": "Translate the following Korean text to English. Keep the professional tone and technical terms."},
                {"role": "user", "content": korean_text}
            ]
        )
        return response.choices[0].message.content
    except:
        return "This report analyzes packaging optimization for carbon emission reduction. The analysis shows significant environmental benefits through optimized packaging design."

def generate_pdf_report(result, gpt_report):
    """PDF 리포트 생성 함수"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=50, bottomMargin=50)
    
    # 기본 폰트 사용
    font_name = 'Helvetica'
    
    # 스타일 정의
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', 
                                parent=styles['Heading1'], 
                                fontName=font_name, 
                                fontSize=20, 
                                alignment=1, 
                                spaceAfter=30)
    
    heading_style = ParagraphStyle('Heading', 
                                  parent=styles['Heading2'], 
                                  fontName=font_name, 
                                  fontSize=14, 
                                  spaceAfter=15,
                                  spaceBefore=20)
    
    normal_style = ParagraphStyle('Normal', 
                                 parent=styles['Normal'], 
                                 fontName=font_name, 
                                 fontSize=11,
                                 spaceAfter=10,
                                 leading=14)
    
    # 문서 내용
    story = []
    
    # 제목
    story.append(Paragraph("Carbon Reduction Report", title_style))
    story.append(Spacer(1, 20))
    
    # 결과 테이블
    story.append(Paragraph("Calculation Results", heading_style))
    
    # 영어로 변환된 데이터
    material_eng = MATERIAL_ENGLISH.get(result['material'], result['material'])
    
    data = [
        ['Item', 'Value'],
        ['Material Type', material_eng],
        ['Original Volume', f"{result['old_volume']} m³"],
        ['Optimized Volume', f"{result['new_volume']} m³"],
        ['Mass Reduction', f"{result['saved_mass']:.2f} kg"],
        ['Carbon Emission Reduction', f"{result['saved_emission']:.2f} kg CO2-eq"]
    ]
    
    table = Table(data, colWidths=[2.5*inch, 3*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))
    
    story.append(table)
    story.append(Spacer(1, 30))
    
    # GPT 리포트 번역 및 추가
    story.append(Paragraph("AI Analysis Report", heading_style))
    
    # GPT 리포트를 영어로 번역
    english_report = translate_korean_to_english_simple(gpt_report)
    
    # 문단별로 나누어 추가
    paragraphs = english_report.split('\n\n')
    for paragraph in paragraphs:
        if paragraph.strip():
            # 긴 텍스트를 적절히 나누어 처리
            clean_paragraph = paragraph.strip().replace('\n', ' ')
            story.append(Paragraph(clean_paragraph, normal_style))
            story.append(Spacer(1, 10))
    
    # 요약 섹션 추가
    story.append(Spacer(1, 20))
    story.append(Paragraph("Summary", heading_style))
    summary_text = f"This packaging optimization analysis demonstrates a potential reduction of {result['saved_mass']:.2f} kg in material usage, resulting in {result['saved_emission']:.2f} kg CO2-eq emission savings. The transition from {material_eng} packaging volume of {result['old_volume']} m³ to {result['new_volume']} m³ represents a significant environmental improvement."
    story.append(Paragraph(summary_text, normal_style))
    
    # PDF 생성
    doc.build(story)
    buffer.seek(0)
    return buffer

# Cosmos DB에서 userId가 'yuni'인 모든 데이터의 부피(cm³) 합산
def get_total_volume_for_yuni():
    query = "SELECT c.volume FROM c WHERE c.userId = 'yuni'"
    items = list(container.query_items(query=query, enable_cross_partition_query=True))
    total_volume = 0
    for item in items:
        try:
            total_volume += float(item["volume"])
        except Exception:
            continue
    return total_volume

def get_yuni_record_count():
    query = "SELECT VALUE COUNT(1) FROM c WHERE c.userId = 'yuni'"
    items = list(container.query_items(query=query, enable_cross_partition_query=True))
    return items[0] if items else 0

@csrf_exempt
def report_view(request):
    old_v = 119040 * get_yuni_record_count()/1000000
    new_v = get_total_volume_for_yuni()/1000000
    material = "골판지"

    result = calculate_carbon_saving(old_v, new_v, material)
    report = generate_gpt_report(result)

    if request.method == "POST":
        try:
            pdf_buffer = generate_pdf_report(result, report)
            filename = f"carbon_report_{material}_{result['saved_emission']:.0f}kg.pdf"
            response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename=\"{filename}\"'
            return response
        except Exception as e:
            return HttpResponse(f"PDF 생성 중 오류가 발생했습니다: {str(e)}", status=500)

    # GET도 stats_report.html만 렌더링
    return render(request, "status_report.html", {"result": result, "report": report})