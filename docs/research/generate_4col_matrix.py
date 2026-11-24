#!/usr/bin/env python3
import sys
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
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
        self.drawString(36, 612 - 24, "MNC AI AGENT REPLACEMENT & DISRUPTION MATRIX | 4-COLUMN BENCHMARK")
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawRightString(792 - 36, 612 - 24, "ENTERPRISE INTELLIGENCE REPORT")

        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.6)
        self.line(36, 612 - 28, 792 - 36, 612 - 28)

        self.line(36, 28, 792 - 36, 28)
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawString(36, 18, "CONFIDENTIAL & PROPRIETARY — MNC STRATEGIC WORKFORCE PLANNING (2026)")
        self.setFont("Helvetica-Bold", 7.5)
        self.setFillColor(colors.HexColor("#334155"))
        self.drawRightString(792 - 36, 18, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()

def build_pdf():
    pdf_path = "/Users/shivam/Documents/Mave/MNC_AI_Agent_Replacement_Matrix.pdf"
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
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#0F172A')
    )
    c_body = ParagraphStyle(
        'CBody',
        fontName='Helvetica',
        fontSize=7.2,
        leading=9.5,
        textColor=colors.HexColor('#1E293B')
    )
    c_startups = ParagraphStyle(
        'CStartup',
        fontName='Helvetica',
        fontSize=7.2,
        leading=9.5,
        textColor=colors.HexColor('#0369A1')
    )
    c_model = ParagraphStyle(
        'CModel',
        fontName='Helvetica',
        fontSize=7.2,
        leading=9.5,
        textColor=colors.HexColor('#047857')
    )

    story = []

    # Title Banner
    t_p = Paragraph("<b>MNC AI Agent Replacement & Disruption Matrix</b>", title_style)
    s_p = Paragraph("4-Column Executive Taxonomy: Designation Replaced/Augmented | Autonomous Work Handled | Startups Commercializing | Optimal Foundation Model", sub_style)
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
        # Engineering & IT
        ("Junior / Mid Software Engineer",
         "Writes boilerplate APIs, auto-generates unit/integration tests, fixes stack trace bugs, refactors legacy codebases, and executes AST migrations.",
         "Cognition (Devin), Cursor (Anysphere), Factory.ai, Augment Code, Magic.dev, Poolside",
         "Claude 3.5 / 3.7 Sonnet (Industry benchmark for coding, tool-calling, and AST repo manipulation)"),

        ("QA & Test Automation Engineer",
         "Autonomously authors Playwright/Cypress end-to-end tests from natural language specs, self-heals broken web locators, and runs synthetic exploratory runs.",
         "QA Wolf, Mabl, Testim, BlinqIO, Octomind, Applitools",
         "Claude 3.5 Sonnet & GPT-4o (Superior DOM understanding, visual inspection & robust code synthesis)"),

        ("Site Reliability Engineer (SRE) / Incident Responder",
         "Ingests telemetry & Datadog logs, pinpoints root-cause commits, drains traffic from unhealthy pods, executes auto-remediation runbooks, and drafts post-mortems.",
         "Resolve AI, PagerDuty AI, Kindo, BigPanda, Transposit",
         "OpenAI o3-mini & Claude 3.5 Sonnet (Rapid multi-hop causal reasoning across log topologies)"),

        ("Cybersecurity Tier-1 SOC Analyst",
         "Triages SIEM/SOAR alert noise, correlates telemetry across endpoints, quarantines compromised devices, blocks malicious IPs, and verifies phishing emails.",
         "Dropzone AI, Radiant Security, Prophet Security, Torq, Wiz",
         "GPT-4o & Claude 3.5 Sonnet (Rapid regex extraction, low latency, and robust structured JSON actions)"),

        ("IT Helpdesk & Systems Administrator",
         "Resolves 80%+ of internal IT tickets: resets passwords, manages MFA, provisions software access via Okta/Workday, and fixes MDM laptop configurations.",
         "Moveworks, Leena AI, Ema, Aisera, Rezolve.ai",
         "GPT-4o (Fast conversational tool-calling, enterprise API plugins, and multilingual IT support)"),

        ("Database Administrator (DBA)",
         "Analyzes slow SQL execution plans (EXPLAIN), recommends indexes, detects lock deadlocks, auto-optimizes cloud warehouse partitions, and generates schema migrations.",
         "DBtune, Ottertune, Redgate AI, EverSQL",
         "DeepSeek-R1 & Claude 3.5 Sonnet (Mathematical query optimization & complex SQL syntax precision)"),

        # Sales & Marketing
        ("Sales Development Representative (SDR / BDR)",
         "Finds accounts matching ICP, scrapes signals, verifies work emails, writes hyper-personalized 4-step outreach emails, and books meetings on calendar.",
         "11x.ai (Alice), Artisan (Ava), Regie.ai, Apollo.io, Clay.com, Common Room",
         "GPT-4o & Claude 3.5 Sonnet (High creative personalization, persona adaptation, and email deliverability tone)"),

        ("Enterprise Account Executive (Research / CRM Prep)",
         "Reads 10-Ks, earnings calls, and executive news to compile account dossiers, updates CRM fields (MEDDPICC) from Gong calls, and drafts follow-up agreements.",
         "Gong.io, Scratchpad, Clay, Attention.tech, Sybill.ai",
         "Claude 3.5 Sonnet & Gemini 1.5 Pro (Massive context window for full 10-K & call transcripts)"),

        ("Content Marketer & SEO Copywriter",
         "Performs programmatic SEO keyword clustering, writes comprehensive industry articles, adapts whitepapers into tweets/LinkedIn posts, and refreshes stale blogs.",
         "Writer.com, Jasper.ai, Copy.ai, Typeface, MarketMuse",
         "Claude 3.5 Sonnet (Exceptional prose quality, human-like voice, zero fluff, and strong editorial tone)"),

        ("Performance Marketing / Paid Ads Specialist",
         "Generates 50+ ad headline variations, runs automated A/B tests, shifts budget across Meta/Google campaigns based on ROAS, and detects ad fatigue.",
         "AdCreative.ai, Madgicx, Albert.ai, Pencil, Smartly.io",
         "GPT-4o (Multimodal image/copy analysis, fast ad mutation generation, and structured API hooks)"),

        ("Product Marketing Manager (Competitive Battlecards)",
         "Monitors competitor websites, pricing pages, and changelogs; synthesizes win/loss interviews; updates sales battlecards; and writes feature release notes.",
         "Klue, Crayon, Highspot AI, Seismic, Kompyte",
         "Claude 3.5 Sonnet (Nuanced strategic differentiation, tone control, and concise competitive briefs)"),

        # Customer Support & Operations
        ("Customer Support Representative (Tier 1 & 2)",
         "Autonomously answers 75%+ of customer tickets over chat/email, executes account actions (refunds, order updates), reads error logs, and triages bugs.",
         "Sierra.ai (Bret Taylor), Decagon, Maven AGI, Forethought, Ada",
         "GPT-4o & Claude 3.5 Sonnet (High empathy, tool-calling safety, and multi-turn conversational memory)"),

        ("Customer Success Manager (Account Health & QBR)",
         "Tracks product telemetry to calculate churn risk, flags power-user drop-offs, pre-builds quarterly business review (QBR) slide decks, and prompts check-ins.",
         "Gainsight AI, ChurnZero, Hook.co, Planhat",
         "GPT-4o (Multimodal chart analysis, quantitative telemetry interpretation, and CRM syncing)"),

        # Legal & Governance
        ("Contract Paralegal & Junior Legal Counsel",
         "Performs initial redline reviews on NDAs/MSAs, flags deviation from corporate fallback clauses, audits liability caps, and extracts structured contract data.",
         "Harvey.ai, Robin AI, Leya, Spellbook, Ironclad AI",
         "Claude 3.5 Sonnet & GPT-4o (Precise legal statutory reasoning, non-hallucinatory clause extraction)"),

        ("Compliance & Security Questionnaire Analyst",
         "Fills out 200-question enterprise vendor security questionnaires (SOC2, ISO 27001, GDPR) by retrieving verified corporate policies and compliance records.",
         "Conveyor, Vanta AI, Drata AI, Hypercomply, TrustCloud",
         "Claude 3.5 Sonnet & GPT-4o (Accurate retrieval-augmented synthesis from policy repositories)"),

        # Finance & Accounting
        ("Accounts Payable / Receivable Clerk",
         "Extracts line items from invoices (PDF/images), performs 3-way matching against purchase orders and receipts, detects duplicate billing, and schedules ERP payments.",
         "Vic.ai, Stampli, Trullion, Tipalti, AppZen, Klarity",
         "OpenAI o1 / o3-mini & GPT-4o Vision (High-precision OCR extraction & strict mathematical reconciliation)"),

        ("FP&A Analyst (Budget vs. Actuals)",
         "Aggregates departmental spend across ERP ledgers, computes budget variances, builds multi-scenario cash-flow forecasts, and drafts executive commentary.",
         "Numeric, Datarails, Runway Financial, Pigment, Cube Software",
         "OpenAI o1 & DeepSeek-R1 (Complex multi-variable spreadsheet modeling and mathematical verification)"),

        ("Internal Auditor & Travel Expense Reviewer",
         "Scans 100% of employee expense receipts, flags out-of-policy spending (alcohol, luxury flights), cross-references flight prices, and detects expense fraud.",
         "AppZen, MindBridge, Oversight, Glean",
         "GPT-4o Vision & o3-mini (High-throughput receipt vision parsing and rule-matching logic)"),

        # Human Resources
        ("Technical & Talent Sourcing Specialist",
         "Scans LinkedIn, GitHub, and academic papers for candidate profiles matching niche criteria, scores project seniority, and crafts personalized outreach blurbs.",
         "Moonhub, Findem, Fetcher.ai, SeekOut, Gem",
         "GPT-4o & Claude 3.5 Sonnet (Boolean parsing, project portfolio evaluation, and tailored outreach)"),

        ("Initial Screening Recruiter",
         "Conducts asynchronous voice/video technical screening interviews, transcribes answers, rates responses against hiring rubrics, and submits structured scorecards.",
         "Metaview, Apriora, Humanly, ModernLoop",
         "GPT-4o Realtime Audio & Claude 3.5 Sonnet (Low-latency conversational voice + rubric evaluation)"),

        ("HR Operations & Total Rewards Coordinator",
         "Calculates salary band competitiveness against Radford/Mercer data, runs pay-equity regression checks, and answers employee benefits/pension queries.",
         "Pave AI, OpenComp, Culture Amp AI, ChartHop",
         "OpenAI o3-mini & GPT-4o (Statistical regression auditing and conversational benefits policy Q&A)"),

        # Product, Design & Strategy
        ("Associate Product Manager / Product Ops",
         "Aggregates customer support tickets and Gong calls into feature clusters, writes initial PRD drafts, breaks epics into Jira user stories, and monitors releases.",
         "ChatPRD, Productboard AI, Kraftful, Collato",
         "Claude 3.5 Sonnet (Superior structured PRD markdown generation, edge-case user story breakdown)"),

        ("Junior UI Designer / Asset Production Specialist",
         "Generates responsive web screen mockups from design tokens, checks WCAG color contrast, creates icon variations, and converts Figma components to React code.",
         "Galileo AI, v0 by Vercel, Uizard, Relume, Musho",
         "Claude 3.5 Sonnet & GPT-4o (Flawless frontend React/Tailwind code generation and design-token understanding)"),

        ("Technical Documentation Specialist",
         "Reads git commit diffs to update API documentation, validates code snippets for syntax errors, creates interactive endpoint tutorials, and cleans changelogs.",
         "Mintlify, Swimm, GitBook AI, ReadMe",
         "Claude 3.5 Sonnet (Unmatched accuracy in code syntax validation and technical documentation clarity)"),

        # Supply Chain, Procurement & Admin
        ("Executive Assistant (Calendar & Travel Coordinator)",
         "Manages executive calendars, coordinates across external timezones, books multi-city travel itineraries based on flight preferences, and compiles daily agendas.",
         "Lindy.ai, Clara, Motion, Reclaim.ai, MultiOn",
         "GPT-4o (Real-time conversational tool-calling, calendar conflict resolution, and email agent hooks)"),

        ("Enterprise Procurement Sourcing Specialist",
         "Drafts standard RFQs/RFPs, compares incoming supplier bids side-by-side, benchmarks commodity pricing, and alerts procurement managers to contract renewals.",
         "Omnea, Zip, Keel, SpendHQ, Globality",
         "Claude 3.5 Sonnet & OpenAI o1 (Long-form bid comparison, contract synthesis, and procurement rule checks)"),

        ("Freight & Customs Logistics Coordinator",
         "Tracks global container shipments, classifies products under Harmonized System (HS) tariff codes, verifies customs manifests, and detects freight invoice overcharges.",
         "Freightify, Flexport AI, Kestrel, Dronamics",
         "GPT-4o & Claude 3.5 Sonnet (Multimodal shipping document OCR parsing and tariff classification taxonomy)")
    ]

    table_data = [[
        Paragraph("<b>Designation Replaced / Transformed</b>", th_style),
        Paragraph("<b>Work It Autonomously Does</b>", th_style),
        Paragraph("<b>Startups Already Doing It</b>", th_style),
        Paragraph("<b>Best Foundation Model & Reason</b>", th_style)
    ]]

    for role, work, startups, model in raw_data:
        table_data.append([
            Paragraph(f"<b>{role}</b>", c_role),
            Paragraph(work, c_body),
            Paragraph(startups, c_startups),
            Paragraph(model, c_model)
        ])

    col_widths = [135, 255, 155, 175]
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t)

    doc.build(story, canvasmaker=NumberedCanvasLandscape)
    print("4-Column PDF generated successfully at:", pdf_path)

if __name__ == "__main__":
    build_pdf()
