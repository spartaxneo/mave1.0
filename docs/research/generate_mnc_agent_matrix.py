#!/usr/bin/env python3
"""
MNC Professions, Human Skillsets, and Autonomous AI Agents Guide
Enterprise PDF Generator using ReportLab Platypus.
"""

import sys
import os
import re
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

# --- Numbered Canvas for Running Headers and Footers ---
class NumberedCanvas(canvas.Canvas):
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
        # Suppress running header on cover page (Page 1)
        if self._pageNumber > 1:
            # Header line and text
            self.setFont("Helvetica-Bold", 7.5)
            self.setFillColor(colors.HexColor("#475569"))
            self.drawString(36, 792 - 24, "ENTERPRISE INTELLIGENCE REPORT | MNC PROFESSIONS & AI AGENT ARCHITECTURE")
            self.setFont("Helvetica", 7.5)
            self.setFillColor(colors.HexColor("#64748B"))
            self.drawRightString(612 - 36, 792 - 24, "GLOBAL MNC WORKFORCE FRAMEWORK")

            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.6)
            self.line(36, 792 - 28, 612 - 36, 792 - 28)

            # Footer line and text
            self.line(36, 30, 612 - 36, 30)
            self.setFont("Helvetica", 7.5)
            self.setFillColor(colors.HexColor("#64748B"))
            self.drawString(36, 20, "CONFIDENTIAL & PROPRIETARY — FOR ENTERPRISE STRATEGIC WORKFORCE PLANNING")
            self.setFont("Helvetica-Bold", 7.5)
            self.setFillColor(colors.HexColor("#334155"))
            self.drawRightString(612 - 36, 20, f"Page {self._pageNumber} of {page_count}")

        self.restoreState()


def build_pdf(filename="MNC_Professions_and_AI_Agents_Guide.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # --- Typography Styles ---
    # Cover Styles
    cover_tag_style = ParagraphStyle(
        'CoverTag',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#2563EB')
    )
    cover_title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=colors.HexColor('#0F172A')
    )
    cover_sub_style = ParagraphStyle(
        'CoverSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#334155')
    )
    cover_body_style = ParagraphStyle(
        'CoverBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#1E293B')
    )
    tier_title_style = ParagraphStyle(
        'TierTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor('#0F172A')
    )
    tier_desc_style = ParagraphStyle(
        'TierDesc',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#334155')
    )

    # Department & Section Styles
    dept_title_style = ParagraphStyle(
        'DeptTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11.5,
        leading=14,
        textColor=colors.white
    )
    dept_sub_style = ParagraphStyle(
        'DeptSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor('#93C5FD')
    )

    # Profession Card Styles
    card_title_style = ParagraphStyle(
        'CardTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor('#0F172A')
    )
    card_meta_style = ParagraphStyle(
        'CardMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#475569'),
        alignment=2 # Right align
    )
    cell_head_style = ParagraphStyle(
        'CellHead',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor('#0F172A')
    )
    cell_body_style = ParagraphStyle(
        'CellBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.2,
        leading=9.4,
        textColor=colors.HexColor('#1E293B')
    )

    # Appendix & Framework Styles
    h2_style = ParagraphStyle(
        'Header2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#0F172A')
    )
    h3_style = ParagraphStyle(
        'Header3',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#1E3A8A')
    )
    body_p_style = ParagraphStyle(
        'BodyP',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#1E293B')
    )

    story = []

    # =========================================================================
    # PAGE 1: EXECUTIVE COVER & AUTONOMY FRAMEWORK
    # =========================================================================
    tag_p = Paragraph("GLOBAL MNC STRATEGY & AI TRANSFORMATION WHITE PAPER | 2026 EDITION", cover_tag_style)
    title_p = Paragraph("MNC Professions, Human Skillsets,<br/>& Autonomous AI Agents", cover_title_style)
    subtitle_p = Paragraph(
        "A Comprehensive Taxonomy of Corporate Functions, Essential Human Competencies, "
        "Autonomous Agent Delegation, and Multi-Agent Collaboration in Global Enterprises",
        cover_sub_style
    )

    header_table = Table([[tag_p], [title_p], [subtitle_p]], colWidths=[540])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
        ('LINEBELOW', (0,0), (-1,0), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 14),
        ('RIGHTPADDING', (0,0), (-1,-1), 14),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))

    # Metadata & Scope Bar
    meta_p = Paragraph(
        "<b>Audience:</b> Executive Leadership (CEO, CTO, CIO, CHRO), Enterprise Architects, BU VPs & Transformation PMOs<br/>"
        "<b>Scope:</b> 11 Core Corporate Divisions, 33 Specialized Professions, 65+ AI Agent Archetypes, and End-to-End Governance",
        cover_body_style
    )
    meta_table = Table([[meta_p]], colWidths=[540])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#EFF6FF')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#BFDBFE')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # Executive Summary Paragraph
    exec_text = Paragraph(
        "<b>Executive Summary & Paradigm Shift:</b> The modern multinational corporation is undergoing a structural shift from passive SaaS tools to "
        "proactive, autonomous AI agent ecosystems. AI agents do not merely answer user prompts; they possess persistent memory, reason over multi-step goals, "
        "execute API tool calls across enterprise platforms (SAP, Salesforce, Workday, GitHub, Snowflake), self-heal runtime errors, and collaborate via "
        "specialized agent swarms. In this new operating model, corporate professions are not replaced, but elevated: routine cognitive heavy-lifting is offloaded to "
        "autonomous agents, allowing human specialists to focus on high-stakes judgment, architectural ethics, ambiguous negotiations, and cross-functional leadership.",
        cover_body_style
    )
    story.append(exec_text)
    story.append(Spacer(1, 10))

    # The 3-Tier Enterprise Agent Autonomy Model
    tier1_head = Paragraph("<font color='#047857'><b>TIER 1: DIRECT AUTONOMY (AUTO-PILOT)</b></font>", tier_title_style)
    tier1_body = Paragraph(
        "<b>Pattern:</b> Self-Directed Execution with Passive Telemetry<br/>"
        "<b>Characteristics:</b> Standardized workflows, deterministic inputs, automated rollbacks. The agent autonomously plans, triggers APIs, and verifies results.<br/>"
        "<b>Examples:</b> CI/CD test generation, Tier-1 helpdesk deflection, continuous invoice 3-way matching, log anomaly detection.",
        tier_desc_style
    )

    tier2_head = Paragraph("<font color='#B45309'><b>TIER 2: SUPERVISED AUTONOMY (HITL GATE)</b></font>", tier_title_style)
    tier2_body = Paragraph(
        "<b>Pattern:</b> Human-in-the-Loop Sign-Off<br/>"
        "<b>Characteristics:</b> High-impact operational workflows. Agent prepares 95% of analysis, synthesizes documents, and stages transactions, pausing at a human gate.<br/>"
        "<b>Examples:</b> Enterprise code PR merge, contract redline approval, employee promotion modeling, vendor RFQ shortlisting.",
        tier_desc_style
    )

    tier3_head = Paragraph("<font color='#1D4ED8'><b>TIER 3: STRATEGIC COPILOT (ADVISORY)</b></font>", tier_title_style)
    tier3_body = Paragraph(
        "<b>Pattern:</b> Human-Led Strategy with Agent Simulation<br/>"
        "<b>Characteristics:</b> Extreme ambiguity, political nuance, fiduciary liability. Humans govern strategy while agents act as deep research analysts and scenario modelers.<br/>"
        "<b>Examples:</b> M&A target valuation, corporate crisis PR strategy, enterprise architectural re-platforming, regulatory litigation.",
        tier_desc_style
    )

    tier_table = Table([
        [tier1_head, tier2_head, tier3_head],
        [tier1_body, tier2_body, tier3_body]
    ], colWidths=[180, 180, 180])
    tier_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#F0FDF4')),
        ('BACKGROUND', (1,0), (1,-1), colors.HexColor('#FFFBEB')),
        ('BACKGROUND', (2,0), (2,-1), colors.HexColor('#F0F9FF')),
        ('BOX', (0,0), (0,-1), 1, colors.HexColor('#BBF7D0')),
        ('BOX', (1,0), (1,-1), 1, colors.HexColor('#FDE68A')),
        ('BOX', (2,0), (2,-1), 1, colors.HexColor('#BAE6FD')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(tier_table)
    story.append(Spacer(1, 10))

    # Document Structure Guide Box
    guide_p = Paragraph(
        "<b>How to Navigate this Document:</b> Pages 3 to 13 provide granular profiles for 33 essential MNC professions across 11 corporate divisions. "
        "Each role profile dissects: (1) Core Human Expertise, (2) AI Agent Delegated Capabilities, and (3) Specialized Agent Archetypes & Governance Gates. "
        "Pages 14 and 15 detail enterprise multi-agent swarm architectures and security/compliance frameworks.",
        cover_body_style
    )
    guide_table = Table([[guide_p]], colWidths=[540])
    guide_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(guide_table)

    story.append(PageBreak())

    # =========================================================================
    # PAGE 2: THE ENTERPRISE WORKFORCE TRANSFORMATION MATRIX
    # =========================================================================
    p2_title = Paragraph("<b>Enterprise Transformation Matrix: Division Automation Readiness</b>", h2_style)
    p2_desc = Paragraph(
        "A cross-functional comparative benchmark analyzing automation potential, human core value, "
        "and primary agent archetypes across all 11 global enterprise divisions.",
        cover_body_style
    )
    story.append(p2_title)
    story.append(Spacer(1, 4))
    story.append(p2_desc)
    story.append(Spacer(1, 8))

    # Benchmark Table
    bench_data = [
        [
            Paragraph("<b>Corporate Division</b>", cell_head_style),
            Paragraph("<b>Automation Potential</b>", cell_head_style),
            Paragraph("<b>Primary Agent Delegated Tasks</b>", cell_head_style),
            Paragraph("<b>Indispensable Human Domain</b>", cell_head_style),
            Paragraph("<b>Lead Archetype</b>", cell_head_style),
        ],
        [
            Paragraph("<b>Software & Cloud</b>", cell_body_style),
            Paragraph("<font color='#047857'><b>70% - 80%</b></font>", cell_body_style),
            Paragraph("PR reviews, unit tests, code migration, CI/CD telemetry", cell_body_style),
            Paragraph("System design, trade-offs, architecture ethics", cell_body_style),
            Paragraph("<i>CodeReviewAgent</i>", cell_body_style),
        ],
        [
            Paragraph("<b>QA & IT Ops</b>", cell_body_style),
            Paragraph("<font color='#047857'><b>75% - 85%</b></font>", cell_body_style),
            Paragraph("E2E test synthesis, access provisioning, ticket triage", cell_body_style),
            Paragraph("Disaster recovery planning, vendor SLA governance", cell_body_style),
            Paragraph("<i>AutoTriageAgent</i>", cell_body_style),
        ],
        [
            Paragraph("<b>Data Science & AI</b>", cell_body_style),
            Paragraph("<font color='#047857'><b>65% - 75%</b></font>", cell_body_style),
            Paragraph("SQL writing, pipeline healing, feature drift monitoring", cell_body_style),
            Paragraph("Business hypothesis design, causal inference, data ethics", cell_body_style),
            Paragraph("<i>PipelineHealer</i>", cell_body_style),
        ],
        [
            Paragraph("<b>Product & Design</b>", cell_body_style),
            Paragraph("<font color='#B45309'><b>50% - 60%</b></font>", cell_body_style),
            Paragraph("PRD scaffolding, user feedback clustering, design tokens", cell_body_style),
            Paragraph("Customer empathy, 0-to-1 strategy, stakeholder consensus", cell_body_style),
            Paragraph("<i>PRDScaffolder</i>", cell_body_style),
        ],
        [
            Paragraph("<b>Human Resources</b>", cell_body_style),
            Paragraph("<font color='#B45309'><b>55% - 65%</b></font>", cell_body_style),
            Paragraph("Candidate sourcing, screening transcripts, FAQ self-service", cell_body_style),
            Paragraph("Talent negotiation, culture, conflict arbitration", cell_body_style),
            Paragraph("<i>TalentSourcer</i>", cell_body_style),
        ],
        [
            Paragraph("<b>Finance & Accounting</b>", cell_body_style),
            Paragraph("<font color='#047857'><b>70% - 80%</b></font>", cell_body_style),
            Paragraph("3-way invoice matching, variance analysis, reconciliations", cell_body_style),
            Paragraph("Capital allocation, audit judgment, investor relations", cell_body_style),
            Paragraph("<i>ReconBot</i>", cell_body_style),
        ],
        [
            Paragraph("<b>Sales & RevOps</b>", cell_body_style),
            Paragraph("<font color='#047857'><b>65% - 75%</b></font>", cell_body_style),
            Paragraph("ICP prospecting, CRM hygiene, dynamic proposal drafting", cell_body_style),
            Paragraph("Executive relationship building, complex contract closing", cell_body_style),
            Paragraph("<i>SalesProspector</i>", cell_body_style),
        ],
        [
            Paragraph("<b>Marketing & Comms</b>", cell_body_style),
            Paragraph("<font color='#047857'><b>70% - 80%</b></font>", cell_body_style),
            Paragraph("Content multi-formatting, SEO optimization, ad variations", cell_body_style),
            Paragraph("Brand positioning, authentic narrative, crisis communications", cell_body_style),
            Paragraph("<i>ContentEngine</i>", cell_body_style),
        ],
        [
            Paragraph("<b>Customer Success</b>", cell_body_style),
            Paragraph("<font color='#047857'><b>75% - 85%</b></font>", cell_body_style),
            Paragraph("L1/L2 autonomous resolution, churn scoring, health check", cell_body_style),
            Paragraph("Executive QBRs, high-touch escalations, retention deals", cell_body_style),
            Paragraph("<i>ResolutionAgent</i>", cell_body_style),
        ],
        [
            Paragraph("<b>Legal, Risk & GRC</b>", cell_body_style),
            Paragraph("<font color='#B45309'><b>55% - 65%</b></font>", cell_body_style),
            Paragraph("Contract clause extraction, compliance scans, vendor risks", cell_body_style),
            Paragraph("Litigation strategy, regulatory representation, board counsel", cell_body_style),
            Paragraph("<i>ContractReviewer</i>", cell_body_style),
        ],
        [
            Paragraph("<b>Supply Chain & Ops</b>", cell_body_style),
            Paragraph("<font color='#047857'><b>70% - 80%</b></font>", cell_body_style),
            Paragraph("Demand forecasting, freight tracking, customs document check", cell_body_style),
            Paragraph("Geopolitical contingency planning, supplier partnerships", cell_body_style),
            Paragraph("<i>LogisticsRouter</i>", cell_body_style),
        ]
    ]

    bench_table = Table(bench_data, colWidths=[90, 65, 175, 130, 80])
    bench_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(bench_table)
    story.append(Spacer(1, 10))

    # Analytical Commentary Box
    analysis_p = Paragraph(
        "<b>Strategic Observation: The 'Hourglass' Workforce Transformation:</b><br/>"
        "AI agents are predominantly compressing the middle tier of corporate activity: routine data aggregation, repetitive code synthesis, "
        "initial documentation drafts, and rule-based workflow execution. What remains highly prioritized for humans are two poles: "
        "<b>(1) Strategic Conceptualization</b> (setting the vision, determining risk appetite, defining business architecture) and "
        "<b>(2) Relationship & Ethical Governance</b> (stakeholder negotiation, trust preservation, regulatory accountability). "
        "MNCs that thrive in this era transition their workforce from manual producers to <i>Agent Orchestrators</i>.",
        cover_body_style
    )
    analysis_table = Table([[analysis_p]], colWidths=[540])
    analysis_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F1F5F9')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(analysis_table)

    story.append(PageBreak())

    # =========================================================================
    # HELPER FUNCTIONS FOR DEPARTMENT PAGES (PAGES 3 - 13)
    # =========================================================================
    def create_dept_header(dept_num, title, mandate):
        p_title = Paragraph(f"<b>DIVISION {dept_num:02d}: {title.upper()}</b>", dept_title_style)
        p_mandate = Paragraph(f"<b>Enterprise Mandate:</b> {mandate}", dept_sub_style)
        t = Table([[p_title], [p_mandate]], colWidths=[540])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#0F172A')),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#0F172A')),
        ]))
        return t

    def create_profession_card(role, band, tier_badge, auto_index, human_skills, agent_caps, archetypes):
        left_h = Paragraph(f"<b>{role}</b> &nbsp;|&nbsp; <font color='#475569'>{band}</font>", card_title_style)
        right_h = Paragraph(f"{tier_badge} &nbsp;|&nbsp; <b>Automation:</b> {auto_index}", card_meta_style)

        col1 = Paragraph(f"<b>Core Human Expertise:</b><br/>{human_skills}", cell_body_style)
        col2 = Paragraph(f"<b>AI Agent Capabilities (What Agent Handles):</b><br/>{agent_caps}", cell_body_style)
        col3 = Paragraph(f"<b>Archetypes & Governance:</b><br/>{archetypes}", cell_body_style)

        data = [
            [left_h, '', right_h],
            [col1, col2, col3]
        ]
        t = Table(data, colWidths=[155, 240, 145])
        t.setStyle(TableStyle([
            ('SPAN', (0,0), (1,0)),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
            ('BACKGROUND', (0,1), (0,1), colors.white),
            ('BACKGROUND', (1,1), (1,1), colors.HexColor('#F8FAFC')),
            ('BACKGROUND', (2,1), (2,1), colors.white),
            ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#CBD5E1')),
            ('LINEBELOW', (0,0), (-1,0), 0.75, colors.HexColor('#CBD5E1')),
            ('INNERGRID', (0,1), (-1,1), 0.4, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0,0), (-1,-1), 3.5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),
            ('LEFTPADDING', (0,0), (-1,-1), 5),
            ('RIGHTPADDING', (0,0), (-1,-1), 5),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        return t

    # =========================================================================
    # DEPARTMENT 1: SOFTWARE ENGINEERING & CLOUD ARCHITECTURE
    # =========================================================================
    story.append(create_dept_header(
        1, "Software Engineering & Cloud Architecture",
        "Digital core engineering, scalable distributed backends, resilient cloud fabric, and application security."
    ))
    story.append(Spacer(1, 5))

    # Role 1
    story.append(create_profession_card(
        role="Senior Full-Stack & Backend Software Engineer",
        band="IC4 - IC6 | Tech",
        tier_badge="<font color='#B45309'><b>Tier 2 (Supervised)</b></font>",
        auto_index="<font color='#047857'><b>70%</b></font>",
        human_skills="• High-level distributed systems design & domain modeling.<br/>"
                     "• Ambiguous architectural trade-offs (CAP theorem, caching).<br/>"
                     "• Cross-team engineering alignment & legacy migration plans.<br/>"
                     "• Code review stewardship, security sign-off, and mentor leadership.",
        agent_caps="• Synthesizes complete unit, integration, and property-based test suites.<br/>"
                   "• Performs automated PR reviews for anti-patterns, OWASP top 10, and style.<br/>"
                   "• Translates user stories & Swagger/OpenAPI schemas into endpoint skeletons.<br/>"
                   "• Autonomously analyzes stack traces and generates verified bug fixes.<br/>"
                   "• Executes major library migrations, AST refactoring, and deprecation fixes.",
        archetypes="• <b>Archetypes:</b> <i>CodeReviewAgent</i>, <i>TestSynthesizer</i>, <i>RefactorBot</i><br/>"
                   "• <b>Tools:</b> GitHub API, SonarQube, Docker, Jira, IDE LSP<br/>"
                   "• <b>HITL Gate:</b> Mandatory Senior Engineer PR sign-off before merge."
    ))
    story.append(Spacer(1, 5))

    # Role 2
    story.append(create_profession_card(
        role="Site Reliability Engineer (SRE) & Cloud Architect",
        band="IC4 - IC7 | Infrastructure",
        tier_badge="<font color='#047857'><b>Tier 1 (Direct Deflection)</b></font>",
        auto_index="<font color='#047857'><b>75%</b></font>",
        human_skills="• Multi-region disaster recovery & fault-tolerance strategy.<br/>"
                     "• Defining enterprise SLAs, SLOs, and error budgets.<br/>"
                     "• Post-mortem crisis root-cause reviews and organizational learning.<br/>"
                     "• Cloud cost governance, FinOps architecture, and vendor contracts.",
        agent_caps="• Monitors Prometheus/Datadog metrics for anomaly detection & threshold drift.<br/>"
                   "• Autonomously runs remediation runbooks (pod restart, cache flush, failover).<br/>"
                   "• Generates Infrastructure-as-Code (Terraform, Pulumi, Kubernetes YAML).<br/>"
                   "• Synthesizes incident timelines and initial post-mortem draft reports.<br/>"
                   "• Continuously identifies under-utilized cloud resources for rightsizing.",
        archetypes="• <b>Archetypes:</b> <i>RunbookAutoHealer</i>, <i>FinOpsOptimizer</i>, <i>SREWatchdog</i><br/>"
                   "• <b>Tools:</b> AWS/GCP API, Datadog, Terraform, PagerDuty, KubeOps<br/>"
                   "• <b>HITL Gate:</b> Destructive infrastructure actions require human approval."
    ))
    story.append(Spacer(1, 5))

    # Role 3
    story.append(create_profession_card(
        role="Cybersecurity SecOps Analyst & Threat Hunter",
        band="IC3 - IC6 | InfoSec",
        tier_badge="<font color='#047857'><b>Tier 1 & 2 (Hybrid)</b></font>",
        auto_index="<font color='#047857'><b>80%</b></font>",
        human_skills="• Threat modeling for novel attack vectors & zero-day exploits.<br/>"
                     "• Law enforcement, forensics, and regulatory breach notification.<br/>"
                     "• Establishing enterprise zero-trust security postures and policies.<br/>"
                     "• Ethical hacking, red-teaming, and executive risk briefings.",
        agent_caps="• Ingests and correlates millions of SIEM/SOAR logs across global endpoints.<br/>"
                   "• Quarantines compromised hosts and revokes hijacked IAM credentials in seconds.<br/>"
                   "• Autonomously simulates attacker penetration paths via automated red-teaming.<br/>"
                   "• Scans software bills of materials (SBOM) and container images for CVEs.<br/>"
                   "• Triages false positives in phishing reports and security alerts.",
        archetypes="• <b>Archetypes:</b> <i>ThreatHunterAgent</i>, <i>AutoSOARResponder</i>, <i>SBOMAuditor</i><br/>"
                   "• <b>Tools:</b> Splunk, Sentinel, CrowdStrike, Okta API, Wiz, Snyk<br/>"
                   "• <b>HITL Gate:</b> Forensic escalation & enterprise-wide shutdown gates."
    ))

    story.append(PageBreak())

    # =========================================================================
    # DEPARTMENT 2: QUALITY ASSURANCE & ENTERPRISE SYSTEMS
    # =========================================================================
    story.append(create_dept_header(
        2, "Quality Assurance, IT Operations & Systems",
        "Deterministic test coverage, corporate IT service desk, identity governance, and enterprise database resilience."
    ))
    story.append(Spacer(1, 5))

    # Role 4
    story.append(create_profession_card(
        role="QA Automation Engineer & Test Architect",
        band="IC3 - IC5 | Engineering",
        tier_badge="<font color='#047857'><b>Tier 1 (Direct Deflection)</b></font>",
        auto_index="<font color='#047857'><b>85%</b></font>",
        human_skills="• Complex business-flow validation & non-functional test strategy.<br/>"
                     "• User experience edge-case evaluation and accessibility audits.<br/>"
                     "• Quality metrics governance across multi-tier supplier systems.<br/>"
                     "• Regulatory compliance test design (HIPAA, SOX validation suites).",
        agent_caps="• Automatically writes Playwright/Cypress end-to-end regression scripts.<br/>"
                   "• Self-heals broken web element locators and UI selectors after front-end changes.<br/>"
                   "• Synthesizes production-like synthetic test datasets with PII masking.<br/>"
                   "• Executes headless browser exploratory testing to discover unexpected crashes.<br/>"
                   "• Validates API response schemas and payloads against OpenAPI specifications.",
        archetypes="• <b>Archetypes:</b> <i>PlaywrightSynthesizer</i>, <i>LocatorHealer</i>, <i>SyntheticDataBot</i><br/>"
                   "• <b>Tools:</b> Playwright, Postman, Selenium, TestRail, k6 LoadTesting<br/>"
                   "• <b>HITL Gate:</b> Sign-off on major version release gating criteria."
    ))
    story.append(Spacer(1, 5))

    # Role 5
    story.append(create_profession_card(
        role="Enterprise Systems Administrator & IT Helpdesk Lead",
        band="IC2 - IC5 | IT Operations",
        tier_badge="<font color='#047857'><b>Tier 1 (Direct Deflection)</b></font>",
        auto_index="<font color='#047857'><b>80%</b></font>",
        human_skills="• Physical hardware lifecycle, data center racks, and network cabling.<br/>"
                     "• High-touch executive VIP desktop support and conference room tech.<br/>"
                     "• Enterprise identity policy design and directory consolidation (M&A).<br/>"
                     "• IT disaster recovery simulation and audit certification.",
        agent_caps="• Deflects 80% of tier-1 employee tickets (passwords, MFA, VPN setup, software).<br/>"
                   "• Autonomously provisions employee access based on HR Workday role changes.<br/>"
                   "• Diagnoses MDM laptop compliance issues and pushes remediation scripts.<br/>"
                   "• Scans SaaS licensing usage to de-provision abandoned accounts (SaaS FinOps).<br/>"
                   "• Generates step-by-step IT troubleshooting guides customized to user OS.",
        archetypes="• <b>Archetypes:</b> <i>HelpdeskDeflectionBot</i>, <i>IdentityProvisioner</i>, <i>MDMScout</i><br/>"
                   "• <b>Tools:</b> ServiceNow, Jira Service Desk, Jamf, Intune, Okta, Slack<br/>"
                   "• <b>HITL Gate:</b> Privileged admin escalation or sensitive mailbox audits."
    ))
    story.append(Spacer(1, 5))

    # Role 6
    story.append(create_profession_card(
        role="Enterprise Database Administrator (DBA) & Storage Architect",
        band="IC4 - IC6 | Data & Infra",
        tier_badge="<font color='#B45309'><b>Tier 2 (Supervised)</b></font>",
        auto_index="<font color='#047857'><b>70%</b></font>",
        human_skills="• Multi-master clustering, sharding topology, and geographic replication.<br/>"
                     "• Disaster recovery recovery point (RPO) and recovery time (RTO) strategy.<br/>"
                     "• Mission-critical schema redesign for transactional enterprise databases.<br/>"
                     "• Complex data sovereignty, GDPR right-to-be-forgotten architecture.",
        agent_caps="• Analyzes slow-query execution plans (EXPLAIN) and suggests optimal indexes.<br/>"
                   "• Detects lock contention, deadlocks, and connection pool exhaustion in real time.<br/>"
                   "• Automates regular database backups, replication lag monitoring, and integrity tests.<br/>"
                   "• Sanitizes production database dumps for local developer sandboxes.<br/>"
                   "• Drafts complex zero-downtime database migration scripts (gh-ost/pt-online-schema).",
        archetypes="• <b>Archetypes:</b> <i>QueryOptimizerAgent</i>, <i>IndexRecommender</i>, <i>SchemaMigrator</i><br/>"
                   "• <b>Tools:</b> PostgreSQL, Oracle, Snowflake, pg_stat_statements, Redgate<br/>"
                   "• <b>HITL Gate:</b> Running DDL/schema migrations in production environments."
    ))

    story.append(PageBreak())

    # =========================================================================
    # DEPARTMENT 3: DATA SCIENCE, ANALYTICS & MACHINE LEARNING
    # =========================================================================
    story.append(create_dept_header(
        3, "Data Science, Analytics & Machine Learning",
        "Enterprise intelligence, automated ETL pipelines, predictive modeling, MLOps, and algorithmic governance."
    ))
    story.append(Spacer(1, 5))

    # Role 7
    story.append(create_profession_card(
        role="Business Intelligence (BI) Analyst & Analytics Engineer",
        band="IC3 - IC5 | Data",
        tier_badge="<font color='#047857'><b>Tier 1 & 2 (Hybrid)</b></font>",
        auto_index="<font color='#047857'><b>75%</b></font>",
        human_skills="• Translating ambiguous C-suite business questions into quantitative models.<br/>"
                     "• Causal inference analysis vs. spurious correlations.<br/>"
                     "• Designing semantic metrics governance (e.g., standardizing ARR definitions).<br/>"
                     "• Executive storytelling and influencing quarterly revenue strategy.",
        agent_caps="• Translates natural language executive questions into optimized SQL queries.<br/>"
                   "• Autonomously builds dbt data transformation models and documentation.<br/>"
                   "• Scans dashboards for statistical anomalies and auto-generates narrative summaries.<br/>"
                   "• Generates automated slide decks and metric scorecards for weekly reviews.<br/>"
                   "• Recommends dashboard consolidation by detecting unused BI reports.",
        archetypes="• <b>Archetypes:</b> <i>TextToSQLBot</i>, <i>dbtModelSynthesizer</i>, <i>MetricAnomalyExplainer</i><br/>"
                   "• <b>Tools:</b> Snowflake, BigQuery, dbt, Looker, Tableau, Metabase<br/>"
                   "• <b>HITL Gate:</b> Formal sign-off on board-level or SEC reporting figures."
    ))
    story.append(Spacer(1, 5))

    # Role 8
    story.append(create_profession_card(
        role="Enterprise Data Pipeline & ETL Engineer",
        band="IC4 - IC6 | Data Engineering",
        tier_badge="<font color='#047857'><b>Tier 1 (Direct Deflection)</b></font>",
        auto_index="<font color='#047857'><b>80%</b></font>",
        human_skills="• Data mesh architecture, domain-driven ownership, and data contracts.<br/>"
                     "• Real-time streaming infrastructure sizing (Kafka/Flink partitioning).<br/>"
                     "• Enterprise data governance and cross-border data transfer compliance.<br/>"
                     "• Vendor negotiations for multi-million dollar data lakehouse platforms.",
        agent_caps="• Detects upstream schema drift and dynamically adapts transformation logic.<br/>"
                   "• Automatically diagnoses failing Airflow DAGs, restarts tasks, or backfills data.<br/>"
                   "• Generates end-to-end data pipelines from source APIs to warehouse tables.<br/>"
                   "• Monitors data freshness, volume anomalies, and null-rate violations.<br/>"
                   "• Optimizes warehouse clustering keys and partition strategies to cut costs.",
        archetypes="• <b>Archetypes:</b> <i>PipelineSelfHealer</i>, <i>SchemaDriftAdapter</i>, <i>DataQualityAuditor</i><br/>"
                   "• <b>Tools:</b> Apache Airflow, Kafka, dbt, Spark, Databricks, Great Expectations<br/>"
                   "• <b>HITL Gate:</b> Changes to production customer master data schemas."
    ))
    story.append(Spacer(1, 5))

    # Role 9
    story.append(create_profession_card(
        role="Machine Learning Engineer & MLOps Specialist",
        band="IC4 - IC7 | AI & Research",
        tier_badge="<font color='#B45309'><b>Tier 2 (Supervised)</b></font>",
        auto_index="<font color='#047857'><b>65%</b></font>",
        human_skills="• Formulation of novel loss functions and domain-specific modeling approaches.<br/>"
                     "• AI fairness, bias auditing, explainability, and regulatory compliance (EU AI Act).<br/>"
                     "• Evaluating build vs. buy vs. fine-tune for proprietary enterprise LLMs.<br/>"
                     "• Designing low-latency inference architectures for mission-critical services.",
        agent_caps="• Automates hyperparameter optimization, model evaluations, and benchmark runs.<br/>"
                   "• Monitors deployed models for concept drift, covariate shift, and latency spikes.<br/>"
                   "• Generates synthetic fine-tuning datasets and evaluates response quality.<br/>"
                   "• Automates quantization, pruning, and ONNX conversion for model deployment.<br/>"
                   "• Runs automated unit tests on model outputs to detect toxic hallucinations.",
        archetypes="• <b>Archetypes:</b> <i>ModelEvalAuditor</i>, <i>DriftSentinel</i>, <i>SyntheticDatasetCurator</i><br/>"
                   "• <b>Tools:</b> PyTorch, Hugging Face, MLflow, Weights & Biases, Triton, vLLM<br/>"
                   "• <b>HITL Gate:</b> Deploying high-risk models to production customer endpoints."
    ))

    story.append(PageBreak())

    # =========================================================================
    # DEPARTMENT 4: PRODUCT MANAGEMENT & EXPERIENCE DESIGN
    # =========================================================================
    story.append(create_dept_header(
        4, "Product Management, UX/UI & Technical Comms",
        "Product vision, customer problem discovery, interface experience, design systems, and enterprise documentation."
    ))
    story.append(Spacer(1, 5))

    # Role 10
    story.append(create_profession_card(
        role="Enterprise Product Manager (Technical / Group PM)",
        band="L5 - L7 | Product",
        tier_badge="<font color='#1D4ED8'><b>Tier 3 (Strategic Advisory)</b></font>",
        auto_index="<font color='#B45309'><b>55%</b></font>",
        human_skills="• Uncovering latent customer pain points via empathetic user interviews.<br/>"
                     "• Multi-year product vision, strategic differentiation, and pricing power.<br/>"
                     "• Executive alignment, engineering trade-off debates, and roadmap buy-in.<br/>"
                     "• Go/no-go product launch decisions and commercial risk mitigation.",
        agent_caps="• Synthesizes thousands of customer support tickets and Gong calls into feature clusters.<br/>"
                   "• Drafts complete initial PRDs (Problem Statement, Acceptance Criteria, User Stories).<br/>"
                   "• Continuously tracks competitor feature releases, pricing shifts, and changelogs.<br/>"
                   "• Generates user impact matrices and pre-populates Jira backlog epics.<br/>"
                   "• Runs automated sanity checks comparing PRD specs against finished staging builds.",
        archetypes="• <b>Archetypes:</b> <i>PRDScaffolder</i>, <i>VoiceOfCustomerSynthesizer</i>, <i>CompetitorRadar</i><br/>"
                   "• <b>Tools:</b> Jira, Confluence, Gong, Canny, Mixpanel, Linear, Figma API<br/>"
                   "• <b>HITL Gate:</b> Final roadmap prioritization and feature scope authorization."
    ))
    story.append(Spacer(1, 5))

    # Role 11
    story.append(create_profession_card(
        role="Senior UI/UX & Product Experience Designer",
        band="IC4 - IC6 | Design",
        tier_badge="<font color='#1D4ED8'><b>Tier 3 (Strategic Advisory)</b></font>",
        auto_index="<font color='#B45309'><b>50%</b></font>",
        human_skills="• Deep empathy for emotional and accessibility needs of diverse users.<br/>"
                     "• Defining signature brand design language and breakthrough interaction patterns.<br/>"
                     "• Running high-fidelity usability testing labs and interpreting subtle user hesitation.<br/>"
                     "• Mentoring design teams and championing WCAG AAA accessibility standards.",
        agent_caps="• Automatically generates responsive screen variants from design system components.<br/>"
                   "• Scans Figma layouts for WCAG color contrast, touch target sizes, and padding.<br/>"
                   "• Generates production-ready design tokens and React/Tailwind frontend code.<br/>"
                   "• Synthesizes realistic UX microcopy and localized translations in 20+ languages.<br/>"
                   "• Generates interactive prototypes from wireframes and design annotations.",
        archetypes="• <b>Archetypes:</b> <i>FigmaToCodeBot</i>, <i>AccessibilityAuditor</i>, <i>DesignTokenSync</i><br/>"
                   "• <b>Tools:</b> Figma, Storybook, Tailwind, Zeroheight, Playwright Component Test<br/>"
                   "• <b>HITL Gate:</b> Visual brand identity approval and design system releases."
    ))
    story.append(Spacer(1, 5))

    # Role 12
    story.append(create_profession_card(
        role="Technical Writer & Enterprise Knowledge Architect",
        band="IC3 - IC5 | Documentation",
        tier_badge="<font color='#047857'><b>Tier 1 & 2 (Hybrid)</b></font>",
        auto_index="<font color='#047857'><b>80%</b></font>",
        human_skills="• Structuring complex cross-product information architecture (IA).<br/>"
                     "• Establishing corporate style guides, tone of voice, and terminology consistency.<br/>"
                     "• Reviewing high-stakes regulatory manuals and developer ecosystem guides.<br/>"
                     "• Interviewing subject matter experts to document tacit organizational knowledge.",
        agent_caps="• Reads code git diffs and auto-generates API reference documentation.<br/>"
                   "• Detects broken code samples, invalid curl requests, and stale hyperlinks.<br/>"
                   "• Formats markdown, openapi.yaml, and documentation tables flawlessly.<br/>"
                   "• Translates developer docs into non-technical customer knowledge base articles.<br/>"
                   "• Answers developer community Slack/Discord questions referencing indexed docs.",
        archetypes="• <b>Archetypes:</b> <i>APIDocGenerator</i>, <i>KnowledgeBaseCurator</i>, <i>LinkChecker</i><br/>"
                   "• <b>Tools:</b> GitBook, ReadMe, Notion, Sphinx, Docusaurus, Swagger/OpenAPI<br/>"
                   "• <b>HITL Gate:</b> Final review of public developer documentation and API changelogs."
    ))

    story.append(PageBreak())

    # =========================================================================
    # DEPARTMENT 5: HUMAN RESOURCES & PEOPLE OPERATIONS
    # =========================================================================
    story.append(create_dept_header(
        5, "Human Resources & People Operations",
        "Global talent acquisition, employee experience, compensation benchmarking, performance cycles, and people analytics."
    ))
    story.append(Spacer(1, 5))

    # Role 13
    story.append(create_profession_card(
        role="Global Talent Acquisition & Technical Recruiter",
        band="IC3 - IC6 | People",
        tier_badge="<font color='#B45309'><b>Tier 2 (Supervised)</b></font>",
        auto_index="<font color='#047857'><b>70%</b></font>",
        human_skills="• Building trust and rapport with senior passive candidates.<br/>"
                     "• Negotiating executive compensation packages and closing competitive offers.<br/>"
                     "• Assessing cultural alignment, emotional intelligence, and leadership grit.<br/>"
                     "• Advising hiring managers on market talent availability and role scoping.",
        agent_caps="• Autonomously sources candidates matching job specifications across LinkedIn/GitHub.<br/>"
                   "• Drafts hyper-personalized cold outreach emails based on candidate project history.<br/>"
                   "• Coordinates multi-stakeholder interview scheduling across global time zones.<br/>"
                   "• Generates comprehensive candidate summaries from resume PDFs and public repos.<br/>"
                   "• Transcribes interview recordings and structures scorecard notes for debriefs.",
        archetypes="• <b>Archetypes:</b> <i>CandidateSourcer</i>, <i>InterviewScheduler</i>, <i>ScorecardSynthesizer</i><br/>"
                   "• <b>Tools:</b> Greenhouse, Lever, LinkedIn Recruiter, GoodTime, Gem, Ashby<br/>"
                   "• <b>HITL Gate:</b> Human candidate interview and formal hiring decision."
    ))
    story.append(Spacer(1, 5))

    # Role 14
    story.append(create_profession_card(
        role="Human Resources Business Partner (HRBP) & People Lead",
        band="IC5 - Director | HR",
        tier_badge="<font color='#1D4ED8'><b>Tier 3 (Strategic Advisory)</b></font>",
        auto_index="<font color='#B45309'><b>45%</b></font>",
        human_skills="• High-stakes interpersonal mediation, employee grievances, and workplace ethics.<br/>"
                     "• Leadership coaching, organizational restructuring, and succession planning.<br/>"
                     "• Navigating complex labor laws, works councils, and severance negotiations.<br/>"
                     "• Shaping organizational culture, psychological safety, and retention strategies.",
        agent_caps="• Analyzes annual employee pulse surveys and synthesizes sentiment trends.<br/>"
                   "• Flags flight-risk patterns by analyzing promotion velocity, tenure, and engagement.<br/>"
                   "• Generates customized performance review templates and manager calibration guides.<br/>"
                   "• Autonomously answers employee questions regarding corporate policies and benefits.<br/>"
                   "• Prepares organizational charts and headcount variance scenario models.",
        archetypes="• <b>Archetypes:</b> <i>OrgPulseAnalyzer</i>, <i>FlightRiskSentinel</i>, <i>HRPolicyBot</i><br/>"
                   "• <b>Tools:</b> Workday, Culture Amp, Lattice, Visier, ChartHop, Slack<br/>"
                   "• <b>HITL Gate:</b> Any termination, disciplinary action, or organizational restructuring."
    ))
    story.append(Spacer(1, 5))

    # Role 15
    story.append(create_profession_card(
        role="Total Rewards, Compensation & Benefits Analyst",
        band="IC3 - IC5 | HR Ops",
        tier_badge="<font color='#047857'><b>Tier 1 & 2 (Hybrid)</b></font>",
        auto_index="<font color='#047857'><b>75%</b></font>",
        human_skills="• Designing global compensation philosophy, equity vesting, and bonus pools.<br/>"
                     "• Presenting executive compensation packages to the Board Compensation Committee.<br/>"
                     "• Navigating complex cross-border taxation, pensions, and local statutory benefits.<br/>"
                     "• Pay equity audit defense and legal compliance (e.g., EU Pay Transparency Directive).",
        agent_caps="• Ingests and benchmarks salary survey data (Radford, Mercer, Pave) against bands.<br/>"
                   "• Performs automated pay-equity regression models to detect ungrounded disparities.<br/>"
                   "• Calculates complex equity grant vesting, dilution models, and tax withholding.<br/>"
                   "• Models financial impact of inflation adjustments across international subsidiaries.<br/>"
                   "• Resolves routine employee benefits inquiries and claims status questions.",
        archetypes="• <b>Archetypes:</b> <i>CompBenchmarkAgent</i>, <i>PayEquityAuditor</i>, <i>BenefitsAdvisor</i><br/>"
                   "• <b>Tools:</b> Workday, Pave, Radford, Carta, Excel/Python, Mercer Data<br/>"
                   "• <b>HITL Gate:</b> Board-level approval of annual compensation band adjustments."
    ))

    story.append(PageBreak())

    # =========================================================================
    # DEPARTMENT 6: FINANCE, ACCOUNTING & TREASURY
    # =========================================================================
    story.append(create_dept_header(
        6, "Finance, Accounting & Treasury",
        "Financial reporting, SOX internal controls, multi-currency treasury, budgeting, tax compliance, and statutory audits."
    ))
    story.append(Spacer(1, 5))

    # Role 16
    story.append(create_profession_card(
        role="Corporate Controller & Financial Accounting Manager",
        band="IC5 - Director | Finance",
        tier_badge="<font color='#B45309'><b>Tier 2 (Supervised)</b></font>",
        auto_index="<font color='#047857'><b>75%</b></font>",
        human_skills="• Technical GAAP/IFRS accounting judgment (revenue recognition ASC 606).<br/>"
                     "• Audit defense with external Big 4 auditors and regulatory accounting boards.<br/>"
                     "• Establishing and certifying Sarbanes-Oxley (SOX) internal control frameworks.<br/>"
                     "• Managing complex cross-border entity consolidation and currency hedging.",
        agent_caps="• Autonomously executes 3-way matching of invoices, POs, and goods receipts.<br/>"
                   "• Reconciles thousands of multi-currency bank accounts, credit ledgers, and ERP entries.<br/>"
                   "• Detects anomalies, duplicate billings, and suspicious transactions in real time.<br/>"
                   "• Generates automated journal entries for accrued revenue and depreciation.<br/>"
                   "• Prepares first-draft consolidated balance sheets and income statement variances.",
        archetypes="• <b>Archetypes:</b> <i>ReconBot</i>, <i>InvoiceMatchingAgent</i>, <i>SOXComplianceAuditor</i><br/>"
                   "• <b>Tools:</b> SAP S/4HANA, Oracle NetSuite, BlackLine, Coupa, FloQast<br/>"
                   "• <b>HITL Gate:</b> Controller signature on monthly book close and SEC 10-Q/K filings."
    ))
    story.append(Spacer(1, 5))

    # Role 17
    story.append(create_profession_card(
        role="Financial Planning & Analysis (FP&A) Manager",
        band="IC4 - Director | Finance",
        tier_badge="<font color='#1D4ED8'><b>Tier 3 (Strategic Advisory)</b></font>",
        auto_index="<font color='#047857'><b>70%</b></font>",
        human_skills="• Capital allocation recommendations to C-suite and Board of Directors.<br/>"
                     "• Challenging department heads on budget assumptions and headcount requests.<br/>"
                     "• Formulating long-term corporate strategic plan and M&A integration models.<br/>"
                     "• Investor Relations guidance and earnings call financial preparation.",
        agent_caps="• Ingests departmental spend and auto-generates Budget vs. Actual (BvA) reports.<br/>"
                   "• Runs automated sensitivity analysis and Monte Carlo simulations on cash flow.<br/>"
                   "• Forecasts quarterly revenue based on pipeline conversion velocity and seasonality.<br/>"
                   "• Summarizes operational drivers behind departmental budget overspends.<br/>"
                   "• Prepares polished board-ready financial charts and executive commentary.",
        archetypes="• <b>Archetypes:</b> <i>BvAAnalyzer</i>, <i>CashFlowForecaster</i>, <i>ScenarioModeler</i><br/>"
                   "• <b>Tools:</b> Anaplan, Adaptive Insights, Pigment, NetSuite, Excel, PowerBI<br/>"
                   "• <b>HITL Gate:</b> Final CFO sign-off on operating budget and public earnings guidance."
    ))
    story.append(Spacer(1, 5))

    # Role 18
    story.append(create_profession_card(
        role="Corporate Tax & Internal Audit Specialist",
        band="IC4 - IC6 | Tax & Audit",
        tier_badge="<font color='#B45309'><b>Tier 2 (Supervised)</b></font>",
        auto_index="<font color='#047857'><b>70%</b></font>",
        human_skills="• Structuring global transfer pricing policies and IP holding entity strategies.<br/>"
                     "• Negotiating tax audit disputes with IRS, HMRC, and global tax authorities.<br/>"
                     "• Evaluating tax implications of corporate mergers, acquisitions, and spin-offs.<br/>"
                     "• Investigating internal fraud, whistleblower claims, and ethical violations.",
        agent_caps="• Continuously monitors cross-border transactions for transfer pricing compliance.<br/>"
                   "• Scans sales transactions across 50 states/international jurisdictions for VAT/GST.<br/>"
                   "• Gathers and organizes supporting documentation for quarterly tax filings.<br/>"
                   "• Runs automated audit sampling across millions of general ledger entries.<br/>"
                   "• Flags transactions that violate travel & expense (T&E) corporate policies.",
        archetypes="• <b>Archetypes:</b> <i>TransferPricingMonitor</i>, <i>VATAuditBot</i>, <i>ExpenseFraudSentinel</i><br/>"
                   "• <b>Tools:</b> Vertex, Thomson Reuters ONESOURCE, SAP, Alteryx, Concur<br/>"
                   "• <b>HITL Gate:</b> Submission of statutory tax returns and formal internal audit opinions."
    ))

    story.append(PageBreak())

    # =========================================================================
    # DEPARTMENT 7: ENTERPRISE SALES & REVENUE OPERATIONS
    # =========================================================================
    story.append(create_dept_header(
        7, "Enterprise Sales, Revenue Operations & Pre-Sales",
        "Pipeline generation, enterprise deal execution, CPQ pricing rules, CRM governance, and solutions architecture."
    ))
    story.append(Spacer(1, 5))

    # Role 19
    story.append(create_profession_card(
        role="Enterprise Account Executive (AE) & Strategic Client Partner",
        band="IC4 - Director | Sales",
        tier_badge="<font color='#1D4ED8'><b>Tier 3 (Strategic Advisory)</b></font>",
        auto_index="<font color='#B45309'><b>50%</b></font>",
        human_skills="• Building trust and executive relationships with Fortune 500 C-level buyers.<br/>"
                     "• Navigating multi-stakeholder corporate politics and buying committees.<br/>"
                     "• High-stakes commercial negotiations, contract structuring, and mutual close plans.<br/>"
                     "• Orchestrating cross-functional deal teams (Legal, Solutions, Security).",
        agent_caps="• Ingests 10-K filings, earnings calls, and news to generate executive account dossiers.<br/>"
                   "• Summarizes Gong call transcripts and automatically drafts personalized follow-up emails.<br/>"
                   "• Pre-populates CRM deal fields, next steps, and MEDDPICC qualification scorecards.<br/>"
                   "• Suggests optimal discounting strategies based on historical win-loss patterns.<br/>"
                   "• Alerts AE to prospect executive job changes and buying signals via LinkedIn.",
        archetypes="• <b>Archetypes:</b> <i>AccountDossierAgent</i>, <i>GongFollowUpBot</i>, <i>DealCoachAgent</i><br/>"
                   "• <b>Tools:</b> Salesforce, Gong, ZoomInfo, LinkedIn Sales Navigator, DocuSign<br/>"
                   "• <b>HITL Gate:</b> Contract pricing negotiation and executive relationship commitments."
    ))
    story.append(Spacer(1, 5))

    # Role 20
    story.append(create_profession_card(
        role="Sales Development Representative (SDR / BDR)",
        band="IC1 - IC3 | Sales",
        tier_badge="<font color='#047857'><b>Tier 1 & 2 (Hybrid)</b></font>",
        auto_index="<font color='#047857'><b>80%</b></font>",
        human_skills="• Cold phone outreach, verbal tonality, and objection handling in live calls.<br/>"
                     "• Creative, out-of-the-box personalized executive gifting and physical touches.<br/>"
                     "• In-person event networking and booth prospect engagement.<br/>"
                     "• Providing qualitative feedback on marketing lead quality and ICP resonance.",
        agent_caps="• Continuously identifies new accounts matching the Ideal Customer Profile (ICP).<br/>"
                   "• Verifies email deliverability and mobile contact numbers via multiple data providers.<br/>"
                   "• Writes personalized 4-step multi-channel email sequences based on prospect role.<br/>"
                   "• Autonomously answers inbound prospect chat inquiries and books calendar meetings.<br/>"
                   "• Cleanses and enriches inbound leads with company revenue, tech stack, and funding.",
        archetypes="• <b>Archetypes:</b> <i>ICPProspector</i>, <i>ColdOutreachCrafter</i>, <i>CalendarBookerBot</i><br/>"
                   "• <b>Tools:</b> Outreach.io, Salesloft, Apollo.io, ZoomInfo, Clay, Drift<br/>"
                   "• <b>HITL Gate:</b> Human review of high-value Tier-1 executive outreach emails."
    ))
    story.append(Spacer(1, 5))

    # Role 21
    story.append(create_profession_card(
        role="Revenue Operations (RevOps) & CRM Architect",
        band="IC3 - IC6 | Operations",
        tier_badge="<font color='#047857'><b>Tier 1 & 2 (Hybrid)</b></font>",
        auto_index="<font color='#047857'><b>75%</b></font>",
        human_skills="• Territory carving, sales compensation design, and commission quota setting.<br/>"
                     "• Sales lifecycle process design and alignment across Marketing, Sales, and CS.<br/>"
                     "• Enterprise vendor selection and consolidation for the end-to-end go-to-market tech stack.<br/>"
                     "• Presenting board-level revenue metrics (CAC, LTV, Magic Number, Net Retention).",
        agent_caps="• Automatically deduplicates leads, merges contacts, and cleans invalid CRM data.<br/>"
                   "• Routes inbound enterprise leads to the appropriate account executive in real time.<br/>"
                   "• Audits CPQ quote calculations and validates non-standard discount approvals.<br/>"
                   "• Forecasts quarterly revenue pipeline using historical conversion decay curves.<br/>"
                   "• Flags stalled pipeline deals with no recent customer activity or email replies.",
        archetypes="• <b>Archetypes:</b> <i>CRMHygieneSentinel</i>, <i>LeadRouterAgent</i>, <i>PipelineDecayMonitor</i><br/>"
                   "• <b>Tools:</b> Salesforce, HubSpot, LeanData, Clari, LeanData, Zapier<br/>"
                   "• <b>HITL Gate:</b> Changes to commission compensation rules or annual territory splits."
    ))

    story.append(PageBreak())

    # =========================================================================
    # DEPARTMENT 8: MARKETING & CORPORATE COMMUNICATIONS
    # =========================================================================
    story.append(create_dept_header(
        8, "Marketing, Growth & Corporate Communications",
        "Brand reputation, product messaging, customer acquisition, multi-channel performance, and crisis public relations."
    ))
    story.append(Spacer(1, 5))

    # Role 22
    story.append(create_profession_card(
        role="Performance & Digital Growth Marketing Lead",
        band="IC3 - IC5 | Marketing",
        tier_badge="<font color='#047857'><b>Tier 1 & 2 (Hybrid)</b></font>",
        auto_index="<font color='#047857'><b>80%</b></font>",
        human_skills="• Multi-million dollar paid media budget allocation across global channels.<br/>"
                     "• Creative campaign strategy, visual direction, and emotional brand resonance.<br/>"
                     "• Attribution modeling and incrementality testing in privacy-first environments.<br/>"
                     "• Negotiating strategic media partnerships, sponsorships, and agency contracts.",
        agent_caps="• Generates dozens of ad copy variations, headlines, and call-to-actions per audience.<br/>"
                   "• Autonomously adjusts PPC bids and reallocates budget based on real-time ROAS.<br/>"
                   "• Conducts programmatic SEO keyword gap analysis and drafts SEO-optimized outlines.<br/>"
                   "• Optimizes landing page elements and analyzes conversion funnels via heatmaps.<br/>"
                   "• Detects ad fatigue, click fraud, and sudden increases in customer acquisition cost.",
        archetypes="• <b>Archetypes:</b> <i>ROASOptimizer</i>, <i>AdCopyGenerator</i>, <i>SEOGapExplorer</i><br/>"
                   "• <b>Tools:</b> Google Ads, Meta Ads Manager, Semrush, Ahrefs, GA4, Optimizely<br/>"
                   "• <b>HITL Gate:</b> Major media budget shifts and brand creative campaign launches."
    ))
    story.append(Spacer(1, 5))

    # Role 23
    story.append(create_profession_card(
        role="Product Marketing Manager (PMM)",
        band="IC4 - IC6 | Marketing",
        tier_badge="<font color='#1D4ED8'><b>Tier 3 (Strategic Advisory)</b></font>",
        auto_index="<font color='#B45309'><b>60%</b></font>",
        human_skills="• Defining product market category, positioning narrative, and value pillars.<br/>"
                     "• Conducting win-loss interviews with enterprise buyers to uncover objections.<br/>"
                     "• Orchestrating cross-functional tier-1 product launches (Sales, PR, Product).<br/>"
                     "• Training global sales teams on competitive battlecards and objection handling.",
        agent_caps="• Scans competitor websites, changelogs, and pricing to update battlecard cards.<br/>"
                   "• Generates first-draft product launch materials (one-pagers, blogs, email announcements).<br/>"
                   "• Synthesizes customer case studies from Gong call transcripts and project metrics.<br/>"
                   "• Adapts technical release notes into business-oriented value propositions.<br/>"
                   "• Monitors social media and forums for customer sentiment surrounding product releases.",
        archetypes="• <b>Archetypes:</b> <i>BattlecardUpdater</i>, <i>LaunchAssetDrafter</i>, <i>WinLossSynthesizer</i><br/>"
                   "• <b>Tools:</b> Klue, Crayon, Highspot, Seismic, Confluence, Figma<br/>"
                   "• <b>HITL Gate:</b> Final positioning approval and public launch messaging."
    ))
    story.append(Spacer(1, 5))

    # Role 24
    story.append(create_profession_card(
        role="Corporate Communications, PR & Brand Reputation Manager",
        band="IC4 - Director | Comms",
        tier_badge="<font color='#1D4ED8'><b>Tier 3 (Strategic Advisory)</b></font>",
        auto_index="<font color='#B45309'><b>50%</b></font>",
        human_skills="• Managing crisis public relations, press conferences, and investigative reporters.<br/>"
                     "• Building long-term relationships with Tier-1 journalists (WSJ, FT, Bloomberg).<br/>"
                     "• Executive speechwriting and ghostwriting for CEO op-eds and keynotes.<br/>"
                     "• Safeguarding corporate brand equity, ESG messaging, and ethical narratives.",
        agent_caps="• Monitors global news, social platforms, and dark web 24/7 for brand mentions.<br/>"
                   "• Drafts initial press release announcements from corporate bullet points.<br/>"
                   "• Identifies relevant industry journalists and podcasts for executive placement.<br/>"
                   "• Prepares Q&A briefing books predicting tough journalist interview questions.<br/>"
                   "• Analyzes press sentiment and coverage volume compared to enterprise peers.",
        archetypes="• <b>Archetypes:</b> <i>MediaRadarSentinel</i>, <i>PressReleaseDrafter</i>, <i>CrisisQABookBot</i><br/>"
                   "• <b>Tools:</b> Cision, Meltwater, Muck Rack, Brandwatch, LexisNexis<br/>"
                   "• <b>HITL Gate:</b> Any public statement, press release, or crisis communication."
    ))

    story.append(PageBreak())

    # =========================================================================
    # DEPARTMENT 9: CUSTOMER SUCCESS & PROFESSIONAL SERVICES
    # =========================================================================
    story.append(create_dept_header(
        9, "Customer Success, Support & Professional Services",
        "Client retention, technical onboarding, tier 1-3 support deflection, enterprise account growth, and SLA enforcement."
    ))
    story.append(Spacer(1, 5))

    # Role 25
    story.append(create_profession_card(
        role="Tier-1 & Tier-2 Enterprise Technical Support Specialist",
        band="IC1 - IC4 | Support",
        tier_badge="<font color='#047857'><b>Tier 1 (Direct Deflection)</b></font>",
        auto_index="<font color='#047857'><b>85%</b></font>",
        human_skills="• De-escalating furious enterprise customers during severe business outages.<br/>"
                     "• Replicating elusive, non-deterministic bugs in bespoke enterprise topologies.<br/>"
                     "• Advocating internally with engineering to prioritize customer bug fixes.<br/>"
                     "• Managing strict SLA compliance for multi-million dollar support contracts.",
        agent_caps="• Autonomously resolves 80%+ of Tier-1 inquiries with accurate, contextual answers.<br/>"
                   "• Analyzes customer logs, HAR files, and error codes to diagnose root causes.<br/>"
                   "• Drafts comprehensive ticket responses incorporating code snippets and docs.<br/>"
                   "• Routes complex tickets to the exact engineering code owner based on git blame.<br/>"
                   "• Summarizes long customer ticket threads into clear executive handover briefs.",
        archetypes="• <b>Archetypes:</b> <i>ResolutionAgent</i>, <i>LogDiagnoser</i>, <i>SmartTicketRouter</i><br/>"
                   "• <b>Tools:</b> Zendesk, Freshdesk, Salesforce Service Cloud, Jira, Datadog<br/>"
                   "• <b>HITL Gate:</b> High-severity (Sev-1) outage responses and SLA breach alerts."
    ))
    story.append(Spacer(1, 5))

    # Role 26
    story.append(create_profession_card(
        role="Enterprise Customer Success Manager (CSM)",
        band="IC3 - IC6 | Customer Success",
        tier_badge="<font color='#1D4ED8'><b>Tier 3 (Strategic Advisory)</b></font>",
        auto_index="<font color='#047857'><b>65%</b></font>",
        human_skills="• Leading executive Quarterly Business Reviews (QBRs) with client champions.<br/>"
                     "• Uncovering organizational changes and executive turnover inside accounts.<br/>"
                     "• Structuring complex contract renewals, multi-year extensions, and upsells.<br/>"
                     "• Driving user adoption change management inside client enterprise teams.",
        agent_caps="• Monitors product telemetry to calculate real-time customer health scores.<br/>"
                   "• Alerts CSM when license utilization drops or key power-users stop logging in.<br/>"
                   "• Pre-populates executive QBR slide decks with client ROI data and usage metrics.<br/>"
                   "• Drafts personalized check-in emails when new product features solve client pain.<br/>"
                   "• Forecasts customer renewal probability and flags early churn warning signs.",
        archetypes="• <b>Archetypes:</b> <i>HealthScoreSentinel</i>, <i>QBRDeckBuilder</i>, <i>ChurnPredictor</i><br/>"
                   "• <b>Tools:</b> Gainsight, ChurnZero, Totango, Salesforce, Mixpanel, Pendo<br/>"
                   "• <b>HITL Gate:</b> Renewal contract terms, pricing concessions, and executive QBR delivery."
    ))
    story.append(Spacer(1, 5))

    # Role 27
    story.append(create_profession_card(
        role="Professional Services & Technical Implementation Consultant",
        band="IC3 - IC6 | Services",
        tier_badge="<font color='#B45309'><b>Tier 2 (Supervised)</b></font>",
        auto_index="<font color='#047857'><b>70%</b></font>",
        human_skills="• Scoping Statements of Work (SOWs) and managing client project scope creep.<br/>"
                     "• Designing custom integration architectures with legacy client mainframes.<br/>"
                     "• Leading on-site client executive workshops and technical steering committees.<br/>"
                     "• Managing billable utilization, project milestones, and delivery margin targets.",
        agent_caps="• Generates standard Statements of Work (SOWs) and implementation project plans.<br/>"
                   "• Writes boilerplate custom API integration scripts and webhook handlers.<br/>"
                   "• Automates data migration, schema mapping, and ETL from client legacy databases.<br/>"
                   "• Generates comprehensive user acceptance testing (UAT) checklists and scripts.<br/>"
                   "• Compiles weekly project milestone status reports comparing planned vs. actual.",
        archetypes="• <b>Archetypes:</b> <i>SOWDrafter</i>, <i>DataMigrationAgent</i>, <i>UATScriptBuilder</i><br/>"
                   "• <b>Tools:</b> Asana, SmartSheet, Jira, MuleSoft, Postman, Python/SQL<br/>"
                   "• <b>HITL Gate:</b> Client SOW sign-off and final production Go-Live approval."
    ))

    story.append(PageBreak())

    # =========================================================================
    # DEPARTMENT 10: LEGAL, GOVERNANCE, RISK & COMPLIANCE (GRC)
    # =========================================================================
    story.append(create_dept_header(
        10, "Legal, Governance, Risk & Regulatory Compliance (GRC)",
        "Commercial contract negotiation, data privacy (GDPR/CCPA), corporate governance, SOX, and enterprise risk management."
    ))
    story.append(Spacer(1, 5))

    # Role 28
    story.append(create_profession_card(
        role="Corporate Legal Counsel & Commercial Contracts Lead",
        band="Legal Counsel - VP | Legal",
        tier_badge="<font color='#B45309'><b>Tier 2 (Supervised)</b></font>",
        auto_index="<font color='#047857'><b>65%</b></font>",
        human_skills="• High-stakes commercial contract negotiation and risk tolerance balancing.<br/>"
                     "• Complex dispute resolution, litigation defense, and courtroom representation.<br/>"
                     "• Structuring multi-jurisdiction M&A transactions, IP assignment, and antitrust.<br/>"
                     "• Advising Board of Directors on fiduciary responsibilities and shareholder rights.",
        agent_caps="• Performs initial redline reviews of incoming vendor MSAs, NDAs, and DPAs.<br/>"
                   "• Extracts non-standard clauses (indemnity, liability caps, warranties) against playbook.<br/>"
                   "• Maintains enterprise contract repository and alerts to upcoming renewal expirations.<br/>"
                   "• Performs legal discovery (e-Discovery) by scanning millions of emails and documents.<br/>"
                   "• Synthesizes case law research and statutory precedents relevant to active matters.",
        archetypes="• <b>Archetypes:</b> <i>ContractRedliner</i>, <i>ClauseAuditor</i>, <i>eDiscoveryScout</i><br/>"
                   "• <b>Tools:</b> Ironclad, LinkSquares, LexisNexis, Westlaw, Relativity, DocuSign<br/>"
                   "• <b>HITL Gate:</b> Attorney signature and execution of any binding legal contract."
    ))
    story.append(Spacer(1, 5))

    # Role 29
    story.append(create_profession_card(
        role="Regulatory Compliance Officer (GDPR, SOX, ESG, HIPAA)",
        band="IC4 - Director | GRC",
        tier_badge="<font color='#047857'><b>Tier 1 & 2 (Hybrid)</b></font>",
        auto_index="<font color='#047857'><b>75%</b></font>",
        human_skills="• Interpreting ambiguous global regulatory mandates (e.g., EU AI Act, CSRD).<br/>"
                     "• Representing the corporation during formal regulatory inquiries and audits.<br/>"
                     "• Designing enterprise-wide compliance culture, whistleblower policies, and ethics.<br/>"
                     "• Assessing geopolitical regulatory divergence between US, EU, and APAC.",
        agent_caps="• Continuously scans databases and cloud storage for unencrypted PII, PHI, or PCI data.<br/>"
                   "• Automates fulfillment of customer GDPR Data Subject Access Requests (DSARs).<br/>"
                   "• Evaluates vendor security questionnaires (SOC2, ISO 27001) using AI verification.<br/>"
                   "• Tracks corporate carbon emissions and ESG metrics across global supply chains.<br/>"
                   "• Generates comprehensive compliance audit reports ready for auditor inspection.",
        archetypes="• <b>Archetypes:</b> <i>DSARAutomator</i>, <i>PIISentinel</i>, <i>VendorRiskReviewer</i><br/>"
                   "• <b>Tools:</b> OneTrust, Vanta, Drata, AuditBoard, MetricStream, ServiceNow GRC<br/>"
                   "• <b>HITL Gate:</b> Submission of statutory regulatory filings and audit certifications."
    ))
    story.append(Spacer(1, 5))

    # Role 30
    story.append(create_profession_card(
        role="Enterprise Risk Management (ERM) & Business Continuity Analyst",
        band="IC4 - IC6 | Risk",
        tier_badge="<font color='#1D4ED8'><b>Tier 3 (Strategic Advisory)</b></font>",
        auto_index="<font color='#B45309'><b>60%</b></font>",
        human_skills="• Designing enterprise risk appetite statements and corporate risk heatmaps.<br/>"
                     "• Formulating multi-scenario business continuity plans for geopolitical conflicts.<br/>"
                     "• Presenting enterprise risk registers to the Board Audit Committee.<br/>"
                     "• Leading enterprise tabletop disaster exercises with executive crisis teams.",
        agent_caps="• Continuously aggregates internal and external risk signals into dynamic heatmaps.<br/>"
                   "• Monitors macroeconomic indicators, currency fluctuations, and supplier health.<br/>"
                   "• Automates quarterly risk assessments across hundreds of enterprise business units.<br/>"
                   "• Simulates supply chain disruptions and financial contagion effects across entities.<br/>"
                   "• Synthesizes executive risk summaries and track remediation action item closure.",
        archetypes="• <b>Archetypes:</b> <i>RiskSignalAggregator</i>, <i>ContagionSimulator</i>, <i>AuditTracker</i><br/>"
                   "• <b>Tools:</b> Archer GRC, MetricStream, SAP Risk, Bloomberg Terminal, Python<br/>"
                   "• <b>HITL Gate:</b> Approval of corporate enterprise risk tolerance thresholds."
    ))

    story.append(PageBreak())

    # =========================================================================
    # DEPARTMENT 11: SUPPLY CHAIN, PROCUREMENT & LOGISTICS
    # =========================================================================
    story.append(create_dept_header(
        11, "Supply Chain, Global Procurement & Logistics",
        "Strategic sourcing, demand forecasting, multi-modal freight operations, customs compliance, and vendor management."
    ))
    story.append(Spacer(1, 5))

    # Role 31
    story.append(create_profession_card(
        role="Strategic Sourcing & Enterprise Procurement Specialist",
        band="IC3 - IC6 | Procurement",
        tier_badge="<font color='#B45309'><b>Tier 2 (Supervised)</b></font>",
        auto_index="<font color='#047857'><b>75%</b></font>",
        human_skills="• High-value supplier commercial negotiations and volume discount structures.<br/>"
                     "• Supplier relationship management (SRM) and strategic joint innovation.<br/>"
                     "• Navigating geopolitical supplier concentration risks and near-shoring strategy.<br/>"
                     "• Managing high-stakes sole-source supplier dependencies.",
        agent_caps="• Scans global supplier databases and pre-qualifies vendors for corporate RFQs.<br/>"
                   "• Analyzes category spend patterns across millions of enterprise purchase orders.<br/>"
                   "• Autonomously drafts standard Request for Proposals (RFPs) and RFQs.<br/>"
                   "• Normalizes and compares vendor bids side-by-side on pricing, SLA, and terms.<br/>"
                   "• Tracks vendor delivery performance and flags SLA delivery delays or cost overruns.",
        archetypes="• <b>Archetypes:</b> <i>RFPBuilder</i>, <i>BidNormalizer</i>, <i>SpendLeakageScout</i><br/>"
                   "• <b>Tools:</b> SAP Ariba, Coupa, Jaggaer, Ivalua, Excel/Tableau<br/>"
                   "• <b>HITL Gate:</b> Final vendor contract award and high-value purchase order approval."
    ))
    story.append(Spacer(1, 5))

    # Role 32
    story.append(create_profession_card(
        role="Global Supply Chain & Demand Planning Analyst",
        band="IC3 - IC5 | Supply Chain",
        tier_badge="<font color='#047857'><b>Tier 1 & 2 (Hybrid)</b></font>",
        auto_index="<font color='#047857'><b>80%</b></font>",
        human_skills="• Sales & Operations Planning (S&OP) consensus building across Sales & Supply.<br/>"
                     "• Managing structural demand shocks (pandemics, trade wars, material shortages).<br/>"
                     "• Setting inventory safety stock policies balancing working capital vs. service levels.<br/>"
                     "• Product end-of-life and phase-out inventory obsolescence management.",
        agent_caps="• Synthesizes point-of-sale data, historical seasonality, and trends to forecast demand.<br/>"
                   "• Calculates dynamic reorder points and triggers automated replenishment orders.<br/>"
                   "• Identifies inventory stock-out risks across regional distribution centers.<br/>"
                   "• Simulates factory capacity bottlenecks and suggests optimal production allocations.<br/>"
                   "• Recommends stock rebalancing transfers between under/over-stocked warehouses.",
        archetypes="• <b>Archetypes:</b> <i>DemandForecaster</i>, <i>ReplenishmentAutoBot</i>, <i>StockBalancer</i><br/>"
                   "• <b>Tools:</b> Blue Yonder, Kinaxis RapidResponse, SAP IBP, o9 Solutions<br/>"
                   "• <b>HITL Gate:</b> Final sign-off on master production schedules and capital commitments."
    ))
    story.append(Spacer(1, 5))

    # Role 33
    story.append(create_profession_card(
        role="Logistics Operations, Freight & Customs Coordinator",
        band="IC2 - IC5 | Logistics",
        tier_badge="<font color='#047857'><b>Tier 1 (Direct Deflection)</b></font>",
        auto_index="<font color='#047857'><b>80%</b></font>",
        human_skills="• Emergency rerouting during port strikes, canal blockages, or geopolitical crises.<br/>"
                     "• Carrier contract negotiations for ocean container fleets and air charters.<br/>"
                     "• Handling contested customs inspections and regulatory dispute resolutions.<br/>"
                     "• Optimizing cold-chain logistics for sensitive pharmaceuticals/perishables.",
        agent_caps="• Tracks global air, ocean, and rail shipments via IoT/AIS telemetry in real time.<br/>"
                   "• Verifies international shipping documentation (Bills of Lading, Invoices, Origin).<br/>"
                   "• Classifies imported goods under correct Harmonized System (HS) tariff codes.<br/>"
                   "• Dispatches automated delay notices to downstream fulfillment distribution hubs.<br/>"
                   "• Audits freight carrier invoices against contracted spot and contract tariffs.",
        archetypes="• <b>Archetypes:</b> <i>FreightTrackerAgent</i>, <i>HSTariffClassifier</i>, <i>FreightInvoiceAuditor</i><br/>"
                   "• <b>Tools:</b> Flexport, project44, FourKites, Descartes, SAP TM<br/>"
                   "• <b>HITL Gate:</b> Authorizing hazardous material shipments or high-cost air-freight diversions."
    ))

    story.append(PageBreak())

    # =========================================================================
    # PAGE 14: ENTERPRISE MULTI-AGENT SWARMS & CROSS-FUNCTIONAL WORKFLOWS
    # =========================================================================
    p14_title = Paragraph("<b>Enterprise Multi-Agent Orchestration Blueprint</b>", h2_style)
    p14_sub = Paragraph(
        "Autonomous agents achieve transformative scale when organized into cross-departmental swarms. "
        "Through shared event buses, tool sandboxes, and message boards, agents collaborate seamlessly to execute complex corporate workflows.",
        cover_body_style
    )
    story.append(p14_title)
    story.append(Spacer(1, 4))
    story.append(p14_sub)
    story.append(Spacer(1, 8))

    # Architecture Overview Box
    arch_head = Paragraph("<b>CORE ENTERPRISE SWARM ARCHITECTURE:</b>", h3_style)
    arch_body = Paragraph(
        "• <b>Shared Message Board / State Broker:</b> Agents post goals, status updates, and artifact handoffs in structured JSON/Markdown.<br/>"
        "• <b>Tool Calling Sandbox:</b> MicroVM isolated containers executing authenticated API calls to SAP, Salesforce, GitHub, Workday.<br/>"
        "• <b>Enterprise Vector Memory & Data Lake:</b> Grounded in proprietary corporate data with fine-grained access control (RBAC).<br/>"
        "• <b>Supervisor / Coordinator Agent:</b> Decomposes high-level executive briefs into DAGs (Directed Acyclic Graphs), assigns sub-agents, and verifies completion.",
        cell_body_style
    )
    arch_table = Table([[arch_head], [arch_body]], colWidths=[540])
    arch_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(arch_table)
    story.append(Spacer(1, 10))

    # 3 Real-World Enterprise Workflows
    wf1_h = Paragraph("<b>WORKFLOW 1: Autonomous Vendor Procurement & Security Onboarding</b>", h3_style)
    wf1_b = Paragraph(
        "<b>1. Business Trigger:</b> Department manager submits software request via Slack/Teams.<br/>"
        "<b>2. Sourcing Agent:</b> Validates existing enterprise software catalog to prevent duplicate SaaS purchases.<br/>"
        "<b>3. SecOps Agent:</b> Fetches vendor SOC2/ISO report, runs automated risk scoring, and probes domain security.<br/>"
        "<b>4. Legal Agent:</b> Compares vendor Terms of Service against corporate indemnity/liability standards, staging redlines.<br/>"
        "<b>5. Finance Agent:</b> Checks budget availability in NetSuite/SAP and generates purchase order draft.<br/>"
        "<b>6. Human Gate:</b> CISO and VP of Finance review unified 1-page risk & financial brief with 1-click approval.",
        cell_body_style
    )

    wf2_h = Paragraph("<b>WORKFLOW 2: Enterprise Production Incident & Self-Healing Swarm</b>", h3_style)
    wf2_b = Paragraph(
        "<b>1. Business Trigger:</b> Datadog alert triggers Sev-1 latency spike on checkout API.<br/>"
        "<b>2. SRE Triage Agent:</b> Correlates telemetry, isolates failing Kubernetes pods, and drains unhealthy traffic.<br/>"
        "<b>3. Code Diagnosis Agent:</b> Analyzes git commits deployed in the last 2 hours, identifies faulty database query.<br/>"
        "<b>4. Patch Agent:</b> Synthesizes hotfix branch, generates passing regression tests, and opens emergency PR.<br/>"
        "<b>5. Comms Agent:</b> Drafts real-time internal status updates and customer-facing status page announcements.<br/>"
        "<b>6. Human Gate:</b> Staff On-Call Engineer approves hotfix PR merge; agent executes automated blue/green canary deploy.",
        cell_body_style
    )

    wf3_h = Paragraph("<b>WORKFLOW 3: Proactive Customer Retention & Churn Intervention</b>", h3_style)
    wf3_b = Paragraph(
        "<b>1. Business Trigger:</b> Product telemetry detects 40% usage drop in $250k enterprise client account.<br/>"
        "<b>2. Telemetry BI Agent:</b> Identifies specific feature drop-off and correlates with 3 recent unresolved support tickets.<br/>"
        "<b>3. Support Triage Agent:</b> Escalates stalled tickets to engineering and generates comprehensive resolution summary.<br/>"
        "<b>4. CSM Assist Agent:</b> Prepares custom executive account recovery proposal with tailored training and roadmap features.<br/>"
        "<b>5. RevOps Agent:</b> Calculates renewal preservation incentive discount within pre-approved boundary conditions.<br/>"
        "<b>6. Human Gate:</b> Enterprise CSM reviews customized outreach, adds personal relationship context, and hosts meeting.",
        cell_body_style
    )

    wf_table = Table([
        [wf1_h], [wf1_b],
        [wf2_h], [wf2_b],
        [wf3_h], [wf3_b],
    ], colWidths=[540])
    wf_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#EFF6FF')),
        ('BACKGROUND', (0,2), (-1,2), colors.HexColor('#F0FDF4')),
        ('BACKGROUND', (0,4), (-1,4), colors.HexColor('#FFFBEB')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(wf_table)

    story.append(PageBreak())

    # =========================================================================
    # PAGE 15: GOVERNANCE, SAFETY, SECURITY & STRATEGIC ROADMAP
    # =========================================================================
    p15_title = Paragraph("<b>Enterprise Agent Governance, Guardrails & Execution Roadmap</b>", h2_style)
    p15_sub = Paragraph(
        "Deploying autonomous agents at multinational scale requires strict cryptographic boundaries, zero-trust permissions, "
        "and verifiable compliance guardrails to eliminate hallucination, security breach, and regulatory non-compliance risks.",
        cover_body_style
    )
    story.append(p15_title)
    story.append(Spacer(1, 4))
    story.append(p15_sub)
    story.append(Spacer(1, 8))

    # The 5 Pillars of Enterprise Agent Governance
    gov1 = Paragraph("<b>1. Zero-Trust Tool Calling & Ephemeral Credentials</b><br/>"
                     "Agents never receive permanent master credentials. Tool calls are brokered via scoped, short-lived OAuth tokens "
                     "restricted by least-privilege role-based access control (RBAC). MicroVM sandboxes isolate all bash/code execution.", cell_body_style)
    gov2 = Paragraph("<b>2. Data Loss Prevention (DLP) & In-Flight PII Masking</b><br/>"
                     "Every prompt and tool input passes through cryptographic sanitization layers that detect and mask PII, PHI, financial "
                     "account numbers, and proprietary intellectual property before transmitting context to model providers.", cell_body_style)
    gov3 = Paragraph("<b>3. Deterministic Verification & Anti-Hallucination Gates</b><br/>"
                     "Probabilistic model outputs must be deterministically verified prior to execution: code must pass linting/test runners, "
                     "SQL must pass explain-plan linters, and financial formulas must balance mathematically against ledger data.", cell_body_style)
    gov4 = Paragraph("<b>4. Non-Repudiation Audit Logs & State Replayability</b><br/>"
                     "Every autonomous agent turn, thought sequence, tool invocation, and API response is logged in an immutable, cryptographically "
                     "signed audit trail, enabling forensic replay and complete SOX/GDPR regulatory compliance audits.", cell_body_style)
    gov5 = Paragraph("<b>5. The Failsafe Human-in-the-Loop (HITL) Circuit Breaker</b><br/>"
                     "High-impact actions (fund disbursement > $10k, production code deployment, employment termination, legal filings) "
                     "require cryptographically verified human approval. An emergency circuit breaker can freeze all agent execution instantaneously.", cell_body_style)

    gov_table = Table([
        [gov1], [gov2], [gov3], [gov4], [gov5]
    ], colWidths=[540])
    gov_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(gov_table)
    story.append(Spacer(1, 10))

    # Strategic 4-Phase Enterprise Implementation Roadmap
    phase_head = Paragraph("<b>4-PHASE MNC AGENTIC TRANSFORMATION ROADMAP:</b>", h3_style)
    
    p_step1 = Paragraph(
        "<b>Phase 1: Pilot & Sandbox (Months 1-3)</b><br/>"
        "• Deploy internal Tier-1 IT helpdesk and developer test-synthesis agents in isolated staging sandboxes.<br/>"
        "• Establish baseline accuracy, token consumption metrics, and human-in-the-loop review speed.",
        cell_body_style
    )
    p_step2 = Paragraph(
        "<b>Phase 2: Supervised Workflows (Months 4-6)</b><br/>"
        "• Expand to Tier-2 supervised operations in Finance (reconciliations) and Sales (account dossiers).<br/>"
        "• Integrate enterprise IAM/SSO, establish audit logging pipelines, and train managers on agent supervision.",
        cell_body_style
    )
    p_step3 = Paragraph(
        "<b>Phase 3: Cross-Functional Swarms (Months 7-12)</b><br/>"
        "• Connect autonomous agents across departments via shared event brokers (Procurement + Legal + SecOps).<br/>"
        "• Achieve 50%+ autonomous deflection of routine operational tasks across the global enterprise.",
        cell_body_style
    )
    p_step4 = Paragraph(
        "<b>Phase 4: Cognitive Mesh & Continuous Learning (Year 2+)</b><br/>"
        "• Full enterprise cognitive mesh where agents continuously optimize supply chains, marketing ROAS, and FinOps.<br/>"
        "• Human workforce operates primarily as strategic directors, ethical stewards, and innovation leaders.",
        cell_body_style
    )

    roadmap_table = Table([
        [phase_head, ''],
        [p_step1, p_step2],
        [p_step3, p_step4]
    ], colWidths=[270, 270])
    roadmap_table.setStyle(TableStyle([
        ('SPAN', (0,0), (1,0)),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('BACKGROUND', (0,1), (-1,-1), colors.white),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0,1), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(roadmap_table)

    # Build the document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Document successfully created: {filename}")

if __name__ == "__main__":
    output_path = "/Users/shivam/Documents/Mave/MNC_Professions_and_AI_Agents_Guide.pdf"
    build_pdf(output_path)
