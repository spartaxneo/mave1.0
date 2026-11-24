#!/usr/bin/env python3
import sys
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class NumberedCanvasLandscape(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 7.5)
        self.setFillColor(colors.HexColor("#475569"))
        self.drawString(36, 612 - 24, "C-SUITE & CORE PROFESSIONS AI AGENT DISRUPTION MATRIX")
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawRightString(792 - 36, 612 - 24, "EXECUTIVE INTELLIGENCE REPORT | 2026")

        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.6)
        self.line(36, 612 - 28, 792 - 36, 612 - 28)

        self.line(36, 28, 792 - 36, 28)
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawString(36, 18, "CONFIDENTIAL — MNC EXECUTIVE STRATEGY, LEADERSHIP & DISRUPTION BENCHMARK")
        self.setFont("Helvetica-Bold", 7.5)
        self.setFillColor(colors.HexColor("#334155"))
        self.drawRightString(792 - 36, 18, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()

def build_pdf():
    pdf_path = "/Users/shivam/Documents/Mave/Executive_Professions_AI_Agent_Matrix.pdf"
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=landscape(letter),
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#0F172A')
    )
    sub_style = ParagraphStyle(
        'DocSub',
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#475569')
    )
    th_style = ParagraphStyle(
        'TableHead',
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white
    )
    c_role = ParagraphStyle(
        'CRole',
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#0F172A')
    )
    c_body = ParagraphStyle(
        'CBody',
        fontName='Helvetica',
        fontSize=7.3,
        leading=10,
        textColor=colors.HexColor('#1E293B')
    )
    c_startups = ParagraphStyle(
        'CStartup',
        fontName='Helvetica',
        fontSize=7.3,
        leading=10,
        textColor=colors.HexColor('#0369A1')
    )
    c_model = ParagraphStyle(
        'CModel',
        fontName='Helvetica',
        fontSize=7.3,
        leading=10,
        textColor=colors.HexColor('#047857')
    )

    story = []

    # Title Banner
    t_p = Paragraph("<b>Executive & Core Corporate Professions: AI Agent Replacement Matrix</b>", title_style)
    s_p = Paragraph("4-Column Executive Breakdown: Designation Replaced / Augmented | Work It Autonomously Does | Startups Commercializing | Optimal Foundation Model", sub_style)
    banner = Table([[t_p], [s_p]], colWidths=[720])
    banner.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(banner)
    story.append(Spacer(1, 8))

    raw_data = [
        ("CEO (Chief Executive Officer) & Chief of Staff",
         "Continuously aggregates real-time KPI telemetry across all business units; runs Monte Carlo crisis simulations; tracks competitor earnings calls & market shifts; auto-drafts shareholder updates; prepares board Q&A briefing decks.",
         "Ema (Universal AI Employee), Hebbia (Matrix AI), Glean, Lindy.ai, MindOS, Adept",
         "OpenAI o1 & Claude 3.5 Sonnet\n(Deep strategic multi-step reasoning, scenario modeling, and nuanced executive communication)"),

        ("COO (Chief Operating Officer) & Head of Operations",
         "Identifies operational process bottlenecks across ERP, CRM, and Jira; maps workflow inefficiencies; autonomously orchestrates multi-agent tasks between departments; tracks vendor SLA compliance in real time.",
         "Celonis (Process Intelligence AI), Torq, Kindo, Moveworks, Cognigy, Zapier Central",
         "GPT-4o & Claude 3.5 Sonnet\n(Superior cross-system tool calling, JSON schema orchestration, and rapid API execution)"),

        ("CA (Chartered Accountant) & CFO / Controller",
         "Automates month-end book close; audits 100% of journal entries against GAAP/IFRS; reconciles multi-currency bank accounts; calculates cross-border transfer pricing & VAT/GST; prepares statutory tax returns.",
         "Trullion (AI Accounting & Audit), Numeric (Autonomous Close), Vic.ai, Klarity, Datarails, BlackLine AI",
         "OpenAI o1 / o3-mini & DeepSeek-R1\n(Flawless mathematical verification, multi-variable ledger reconciliation, and strict logic)"),

        ("Corporate Lawyer & General Counsel",
         "Performs rapid contract redlining against company playbook; analyzes M&A virtual data rooms; conducts automated case law precedent research; drafts bespoke settlement clauses; scans operations for regulatory liability.",
         "Harvey.ai (backed by OpenAI), Leya, Robin AI, Spellbook, CoCounsel (Thomson Reuters), EvenUp",
         "Claude 3.5 Sonnet & Gemini 1.5 Pro\n(Claude for precise statutory legal reasoning & redlines; Gemini for 2M+ token full M&A data room ingestion)"),

        ("HR (Chief Human Resources Officer / HRBP)",
         "Scans global talent pools; conducts automated first-round conversational voice screening interviews; performs pay-equity disparity regression models; resolves 80%+ of employee benefits/policy queries 24/7.",
         "Mercor, Moonhub, Metaview, Leena AI, Moveworks, Culture Amp AI, Pave",
         "GPT-4o (Realtime Voice) & Claude 3.5 Sonnet\n(Empathy, conversational nuance, low-latency live interview screening, and rubric evaluation)"),

        ("CTO (Chief Technology Officer) & VP of Eng",
         "Audits enterprise code repositories for architectural anti-patterns & CVE vulnerabilities; plans legacy refactoring; orchestrates multi-agent coding swarms; continuously rightsizes multi-cloud FinOps spend.",
         "Cognition (Devin), Augment Code, Factory.ai, Wiz AI, Snyk AI, Qodo (Codium)",
         "Claude 3.5 / 3.7 Sonnet\n(Industry benchmark in codebase navigation, AST refactoring, multi-file engineering, and tool calling)"),

        ("CMO (Chief Marketing Officer)",
         "Formulates multi-channel campaign strategies; generates localized ad variations & creative copy; dynamically shifts ad budgets across Google/Meta based on ROAS; monitors 24/7 global brand sentiment & PR crises.",
         "Writer.com, Typeface, Jasper.ai, Brandwatch AI, Smartly.io, AdCreative.ai",
         "Claude 3.5 Sonnet & GPT-4o\n(Claude for sophisticated brand voice, compelling copy, and thought leadership; GPT-4o for multimodal creative evaluation)"),

        ("CRO (Chief Revenue Officer) & VP of Sales",
         "Deploys autonomous AI SDR fleets; runs pipeline decay analytics; auto-generates tailored MEDDPICC deal qualification dossiers; monitors Gong calls for competitor mentions; predicts quarterly revenue forecast accuracy.",
         "11x.ai (Alice), Artisan (Ava), Gong.io, Clari, Apollo.io, Clay.com",
         "GPT-4o & Claude 3.5 Sonnet\n(Persuasive consultative sales outreach, fast CRM tool calling, and deep customer transcript analysis)"),

        ("Management Consultant & Strategy Partner",
         "Analyzes 500+ competitor balance sheets & market research reports; builds market-sizing (TAM/SAM) models; synthesizes McKinsey/Bain-style executive decks; stress-tests pricing elasticity and operational turnaround plans.",
         "Hebbia (Matrix), AlphaSense, Tegus, Julius AI, Causaly",
         "OpenAI o1 & Gemini 1.5 Pro\n(Multi-step structured strategic reasoning, complex financial decomposition, and multi-thousand page analyst report synthesis)"),

        ("Investment Banker & M&A Associate",
         "Parses thousands of CIMs (Confidential Information Memorandums) in M&A data rooms; extracts financial EBITDA adjustments; builds DCF & LBO valuation models; drafts pitch decks and buyer prospect lists.",
         "Hebbia, Canoe Intelligence, CapIntel, Composer, FinChat.io",
         "OpenAI o1 & Claude 3.5 Sonnet\n(Complex financial statement modeling, mathematical formula accuracy, and structured document table extraction)"),

        ("Chief Compliance Officer (CCO) & Risk Officer",
         "Monitors global regulatory updates (EU AI Act, GDPR, SEC disclosures); continuously scans enterprise data stores for unencrypted PII/PHI; runs automated vendor security risk assessments (SOC2/ISO).",
         "OneTrust AI, Vanta AI, Drata AI, AuditBoard, MetricStream",
         "Claude 3.5 Sonnet & GPT-4o\n(Flawless statutory legal/regulatory interpretation and verifiable RAG policy document matching)"),

        ("Supply Chain Director & Chief Procurement Officer",
         "Predicts global logistics disruptions and container freight bottleneck delays; runs automated RFQ/RFP bid auctions; normalizes supplier quotes; optimizes enterprise inventory safety stock using demand forecasting.",
         "Omnea, Zip, Flexport AI, Project44, Kinaxis, Blue Yonder",
         "OpenAI o1 / o3-mini & Claude 3.5 Sonnet\n(Multi-variable linear optimization, freight document parsing, and vendor contract benchmarking)")
    ]

    table_data = [[
        Paragraph("<b>Designation It Replaces / Transforms</b>", th_style),
        Paragraph("<b>Work It Autonomously Does</b>", th_style),
        Paragraph("<b>Startups Who Already Doing It</b>", th_style),
        Paragraph("<b>What Model Is Best In That & Why</b>", th_style)
    ]]

    for role, work, startups, model in raw_data:
        table_data.append([
            Paragraph(f"<b>{role}</b>", c_role),
            Paragraph(work, c_body),
            Paragraph(startups.replace('\n', '<br/>'), c_startups),
            Paragraph(model.replace('\n', '<br/>'), c_model)
        ])

    col_widths = [135, 255, 155, 175]
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t)

    doc.build(story, canvasmaker=NumberedCanvasLandscape)
    print("Executive PDF generated successfully at:", pdf_path)

if __name__ == "__main__":
    build_pdf()
