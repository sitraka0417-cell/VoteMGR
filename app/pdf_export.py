# -*- coding: utf-8 -*-
"""
pdf_export.py — Export des résultats (un poste ou tout le projet) en PDF,
via reportlab.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, PageBreak)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def _styles():
    base = getSampleStyleSheet()
    base.add(ParagraphStyle(name="TitreProjet", parent=base["Title"],
                             fontSize=20, spaceAfter=6))
    base.add(ParagraphStyle(name="TitrePoste", parent=base["Heading2"],
                             fontSize=14, spaceBefore=14, spaceAfter=6,
                             textColor=colors.HexColor("#1a3c6e")))
    return base


def _tableau_poste(poste, styles):
    elements = [Paragraph(poste.nom, styles["TitrePoste"])]
    if poste.nombre_sieges > 1:
        elements.append(Paragraph(
            "Sièges à pourvoir : %d" % poste.nombre_sieges, styles["Normal"]))
    if poste.majorite_absolue:
        elements.append(Paragraph(
            "Mode : majorité absolue (plus de 50%% des voix exprimées requis)",
            styles["Normal"]))
        if poste.majorite_non_atteinte:
            elements.append(Paragraph(
                "⚠ Majorité absolue non atteinte pour tous les sièges — "
                "un tour supplémentaire est nécessaire.", styles["Normal"]))
    total_exprimes = poste.voix_exprimees()
    elements.append(Paragraph(
        "Voix exprimées : %d &nbsp;&nbsp; Bulletins blancs : %d &nbsp;&nbsp; "
        "Bulletins nuls : %d" % (total_exprimes, poste.bulletins_blancs,
                                  poste.bulletins_nuls),
        styles["Normal"]))

    data = [["N°", "Candidat", "Voix", "Élu(e)"]]
    for c in poste.classement():
        est_elu = "OUI" if c.id in poste.elus else ""
        data.append([str(c.numero), c.nom, str(c.votes), est_elu])

    if len(data) == 1:
        elements.append(Paragraph("Aucun candidat.", styles["Normal"]))
        return elements

    table = Table(data, colWidths=[1.5 * cm, 8 * cm, 2.5 * cm, 2.5 * cm])
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c6e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 0), (3, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f3f8")]),
    ]
    for i, c in enumerate(poste.classement(), start=1):
        if c.id in poste.elus:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#d9f2d9")))
            style.append(("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"))
    table.setStyle(TableStyle(style))
    elements.append(table)

    if not poste.vote_termine and poste.egalite_en_attente:
        elements.append(Spacer(1, 4))
        elements.append(Paragraph(
            "⚠ Égalité non départagée entre %d candidat(s)." %
            len(poste.egalite_en_attente), styles["Normal"]))
    return elements


def exporter_pdf(chemin, projet, postes=None):
    """Exporte en PDF les résultats des postes donnés (ou tout le projet
    si postes est None)."""
    styles = _styles()
    doc = SimpleDocTemplate(chemin, pagesize=A4,
                             leftMargin=2 * cm, rightMargin=2 * cm,
                             topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    story = [Paragraph("Résultats — %s" % projet.nom, styles["TitreProjet"])]
    story.append(Paragraph("Généré le %s" %
                            __import__("datetime").datetime.now().strftime("%d/%m/%Y %H:%M"),
                            styles["Normal"]))
    story.append(Spacer(1, 10))

    liste = postes if postes is not None else projet.tous_les_postes()
    if not liste:
        story.append(Paragraph("Aucun poste dans ce projet.", styles["Normal"]))
    for poste in liste:
        story.extend(_tableau_poste(poste, styles))

    # page récapitulative des élus (bureau exécutif complet)
    tous = postes if postes is not None else projet.tous_les_postes()
    postes_avec_elus = [p for p in tous if p.vote_termine and p.elus]
    if postes_avec_elus:
        story.append(PageBreak())
        story.append(Paragraph("Récapitulatif du bureau élu", styles["TitreProjet"]))
        data = [["Poste", "Élu(e)(s)"]]
        for p in postes_avec_elus:
            noms = ", ".join(p.candidat(cid).nom for cid in p.elus if p.candidat(cid))
            data.append([p.nom, noms])
        table = Table(data, colWidths=[6 * cm, 9 * cm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c6e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f3f8")]),
        ]))
        story.append(table)

    doc.build(story)
    return chemin
